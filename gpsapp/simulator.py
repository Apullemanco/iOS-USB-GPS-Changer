"""Simulated position + route playback engine (thread-safe, independent of the device)."""

import math
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from .geo import bearing_deg, distance_m, offset_m, valid_latlon

ACCEL_MPS2 = 2.5       # how fast we speed up
BRAKE_MPS2 = 3.0       # comfortable braking before stops / the end of the route
MIN_SPEED_MPS = 0.5
JITTER = 0.14          # +-14 % natural speed variation
TICK_S = 0.2

NUDGE = {"n": (1, 0), "s": (-1, 0), "e": (0, 1), "w": (0, -1)}


@dataclass
class Route:
    points: list[tuple[float, float]]
    stops: set[int] = field(default_factory=set)   # path indices where we dwell
    speed_kmh: float = 45.0
    loop: bool = False
    jitter: bool = True
    dwell_s: float = 0.0
    cum: list[float] = field(default_factory=list)  # cumulative distance per point

    def __post_init__(self):
        self.cum = [0.0]
        for (a_lat, a_lon), (b_lat, b_lon) in zip(self.points, self.points[1:]):
            self.cum.append(self.cum[-1] + distance_m(a_lat, a_lon, b_lat, b_lon))

    @property
    def length_m(self) -> float:
        return self.cum[-1]


class Simulator:
    def __init__(self, lat: float, lon: float, on_move: Optional[Callable[[float, float], None]] = None):
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._on_move = on_move           # e.g. record history
        self.enabled = False              # True => the device should be spoofed
        self.lat, self.lon = lat, lon
        self.heading = 0.0
        self.step_m = 25.0                # keyboard / D-pad step
        self.version = 0                  # bumps on every position change
        self._route: Optional[Route] = None
        self._route_state = "none"        # none | running | paused | done
        self._seg = 0
        self._v = 0.0
        self._dwell_until = 0.0
        self._t0 = time.monotonic()

    # ---------- position ----------
    def _set_pos(self, lat: float, lon: float) -> None:
        if distance_m(self.lat, self.lon, lat, lon) > 0.5:
            self.heading = bearing_deg(self.lat, self.lon, lat, lon)
        self.lat, self.lon = lat, lon
        self.version += 1

    def position(self) -> tuple[float, float, int]:
        with self._lock:
            return self.lat, self.lon, self.version

    def move_to(self, lat: float, lon: float) -> bool:
        if not valid_latlon(lat, lon):
            return False
        with self._lock:
            self._set_pos(lat, lon)
            routing = self._route_state == "running"
        if self._on_move and not routing:
            self._on_move(lat, lon)
        return True

    def nudge(self, direction: str) -> None:
        dn, de = NUDGE.get(direction, (0, 0))
        with self._lock:
            lat, lon = offset_m(self.lat, self.lon, dn * self.step_m, de * self.step_m)
            self._set_pos(lat, lon)

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self.enabled = enabled
            if not enabled and self._route_state == "running":
                self._route_state = "paused"

    # ---------- routes ----------
    def start_route(self, route: Route) -> bool:
        if len(route.points) < 2 or route.length_m < 1:
            return False
        if route.loop and distance_m(*route.points[0], *route.points[-1]) > 1:
            route = Route(route.points + [route.points[0]], route.stops, route.speed_kmh,
                          True, route.jitter, route.dwell_s)  # drive back to the start
        with self._lock:
            self._route, self._seg, self._v, self._dwell_until = route, 0, 0.0, 0.0
            self._set_pos(*route.points[0])
            self._route_state = "running"
            self.enabled = True
        self._wake.set()
        return True

    def configure_route(self, speed_kmh=None, loop=None, jitter=None) -> None:
        with self._lock:
            if self._route:
                if speed_kmh is not None:
                    self._route.speed_kmh = max(1.0, min(300.0, float(speed_kmh)))
                if loop is not None:
                    self._route.loop = bool(loop)
                if jitter is not None:
                    self._route.jitter = bool(jitter)

    def toggle_pause(self) -> None:
        with self._lock:
            if self._route_state == "running":
                self._route_state = "paused"
            elif self._route_state == "paused" and self._route:
                self._route_state, self._v, self.enabled = "running", 0.0, True
        self._wake.set()

    def clear_route(self) -> None:
        with self._lock:
            self._route, self._route_state = None, "none"

    # ---------- snapshot for the UI ----------
    def snapshot(self) -> dict:
        with self._lock:
            r = self._route
            done_m = 0.0
            if r:
                nxt = r.points[min(self._seg + 1, len(r.points) - 1)]
                done_m = max(0.0, r.cum[min(self._seg + 1, len(r.cum) - 1)] - distance_m(self.lat, self.lon, *nxt))
            return {
                "enabled": self.enabled,
                "lat": self.lat,
                "lon": self.lon,
                "heading": round(self.heading, 1),
                "version": self.version,
                "route": {
                    "state": self._route_state,
                    "speed_kmh": round(self._v * 3.6, 1),
                    "done_m": round(done_m),
                    "total_m": round(r.length_m) if r else 0,
                    "dwell_s": max(0, math.ceil(self._dwell_until - time.monotonic())),
                },
            }

    # ---------- engine ----------
    def run_forever(self) -> None:
        last = time.monotonic()
        while True:
            if self._route_state != "running":
                self._wake.wait()
                self._wake.clear()
                last = time.monotonic()
                continue
            time.sleep(TICK_S)
            now = time.monotonic()
            with self._lock:
                self._tick(min(now - last, 1.0), now)
            last = now

    def _brake_distance(self, r: Route) -> float:
        """Distance to the next point where we must stand still (a stop or the route end)."""
        nxt = r.points[self._seg + 1]
        to_next = distance_m(self.lat, self.lon, *nxt)
        end_idx = None if r.loop else len(r.points) - 1
        if r.dwell_s > 0:
            upcoming = [i for i in r.stops if i > self._seg]
            if upcoming:
                end_idx = min(upcoming) if end_idx is None else min(min(upcoming), end_idx)
        if end_idx is None:
            return math.inf
        return r.cum[end_idx] - r.cum[self._seg + 1] + to_next

    def _tick(self, dt: float, now: float) -> None:
        r = self._route
        if self._route_state != "running" or not r or now < self._dwell_until:
            return
        factor = 1.0 + JITTER * math.sin((now - self._t0) * 0.9) if r.jitter else 1.0
        target_v = max(MIN_SPEED_MPS, r.speed_kmh / 3.6 * factor)
        target_v = min(target_v, max(MIN_SPEED_MPS * 2, math.sqrt(2 * BRAKE_MPS2 * self._brake_distance(r))))
        if self._v < target_v:
            self._v = min(target_v, self._v + ACCEL_MPS2 * dt)
        else:
            self._v = max(target_v, self._v - 2 * BRAKE_MPS2 * dt)
        self._v = max(MIN_SPEED_MPS, self._v)

        # Advance along the polyline, crossing as many vertices as the distance allows.
        remaining = self._v * dt
        lat, lon = self.lat, self.lon
        while remaining > 0:
            t_lat, t_lon = r.points[self._seg + 1]
            d = distance_m(lat, lon, t_lat, t_lon)
            if d > remaining:
                f = remaining / d
                lat, lon = lat + (t_lat - lat) * f, lon + (t_lon - lon) * f
                break
            lat, lon = t_lat, t_lon
            remaining -= d
            self._seg += 1
            if r.dwell_s > 0 and self._seg in r.stops:
                self._dwell_until, self._v = now + r.dwell_s, 0.0
                remaining = 0
            if self._seg >= len(r.points) - 1:
                if r.loop:
                    self._seg = 0
                else:
                    self._route_state, self._v = "done", 0.0
                    break
        heading_target = r.points[min(self._seg + 1, len(r.points) - 1)]
        self._set_pos(lat, lon)
        if distance_m(lat, lon, *heading_target) > 0.5:
            self.heading = bearing_deg(lat, lon, *heading_target)
