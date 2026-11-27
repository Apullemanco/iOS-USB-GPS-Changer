"""Geodesy helpers and place lookup (Photon for autocomplete, Nominatim for search)."""

import math
import re
import threading
import time
from functools import lru_cache
from typing import Optional
from urllib.parse import urlparse

import requests

from . import __version__

EARTH_RADIUS_M = 6_371_000.0
USER_AGENT = f"iOS-GPS-Simulator/{__version__} (open-source desktop app)"

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT

LatLon = tuple[float, float]


def valid_latlon(lat: float, lon: float) -> bool:
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0 and not (math.isnan(lat) or math.isnan(lon))


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (haversine) in meters."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from point 1 to point 2, 0-360 degrees clockwise from north."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def offset_m(lat: float, lon: float, north_m: float, east_m: float) -> LatLon:
    """Move a point by a number of meters north/east (accurate for short distances)."""
    dlat = north_m / 111_320.0
    dlon = east_m / (111_320.0 * max(0.01, math.cos(math.radians(lat))))
    new_lon = (lon + dlon + 180.0) % 360.0 - 180.0
    return max(-90.0, min(90.0, lat + dlat)), new_lon


_COORD_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)\s*$")


def parse_latlon(text: str) -> Optional[LatLon]:
    """Parse '25.68, -100.31' / '25.68 -100.31' into (lat, lon)."""
    m = _COORD_RE.match(text)
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    return (lat, lon) if valid_latlon(lat, lon) else None


_MAP_HOSTS = ("goo.gl", "apple.com", "openstreetmap.org")
_GOOGLE_HOST_RE = re.compile(r"(^|\.)google\.(com|[a-z]{2})(\.[a-z]{2})?$")
_LINK_PATTERNS = (
    re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)"),
    re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)"),
    re.compile(r"[?&#](?:ll|q|center|sll|daddr|destination|coordinate|map=\d+)=(-?\d+\.\d+)(?:,|%2C|/)(-?\d+\.\d+)"),
)


def _is_map_host(host: str) -> bool:
    host = host.lower().split(":")[0]
    return bool(_GOOGLE_HOST_RE.search(host)) or any(host == h or host.endswith("." + h) for h in _MAP_HOSTS)


def parse_map_link(url: str) -> Optional[LatLon]:
    """Extract coordinates from a Google Maps / Apple Maps / OSM share link."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not _is_map_host(parsed.netloc):
        return None
    candidates = [url]
    try:  # short links (maps.app.goo.gl/...) must be resolved first
        resolved = _session.get(url, timeout=6, allow_redirects=True).url
        if _is_map_host(urlparse(resolved).netloc):
            candidates.insert(0, resolved)
    except requests.RequestException:
        pass
    for candidate in candidates:
        for pattern in _LINK_PATTERNS:
            m = pattern.search(candidate)
            if m:
                lat, lon = float(m.group(1)), float(m.group(2))
                if valid_latlon(lat, lon):
                    return lat, lon
    return None


@lru_cache(maxsize=256)
def suggest(query: str, limit: int = 5) -> tuple[dict, ...]:
    """Search-as-you-type suggestions via Photon (Nominatim forbids autocomplete use)."""
    resp = _session.get("https://photon.komoot.io/api/", params={"q": query, "limit": limit}, timeout=6)
    resp.raise_for_status()
    out = []
    for feat in resp.json().get("features", []):
        props, coords = feat.get("properties", {}), feat.get("geometry", {}).get("coordinates")
        if not coords:
            continue
        parts = [props.get("name"), props.get("street"), props.get("city"), props.get("state"), props.get("country")]
        label = ", ".join(dict.fromkeys(p for p in parts if p))
        out.append({"label": label or query, "lat": float(coords[1]), "lon": float(coords[0])})
    return tuple(out)


_nominatim_lock = threading.Lock()
_nominatim_last = 0.0


@lru_cache(maxsize=256)
def geocode(query: str) -> Optional[LatLon]:
    """Resolve a free-text address with Nominatim (max 1 request/second per its usage policy)."""
    global _nominatim_last
    with _nominatim_lock:
        wait = 1.05 - (time.monotonic() - _nominatim_last)
        if wait > 0:
            time.sleep(wait)
        try:
            resp = _session.get("https://nominatim.openstreetmap.org/search",
                                params={"q": query, "format": "jsonv2", "limit": 1}, timeout=8)
        finally:
            _nominatim_last = time.monotonic()
    resp.raise_for_status()
    items = resp.json()
    return (float(items[0]["lat"]), float(items[0]["lon"])) if items else None


def resolve_query(query: str) -> Optional[LatLon]:
    """Coordinates, a maps link or an address -> (lat, lon)."""
    query = query.strip()
    if not query:
        return None
    if query.lower().startswith(("http://", "https://")):
        return parse_map_link(query)
    return parse_latlon(query) or geocode(query)
