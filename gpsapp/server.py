"""Local HTTP API + static UI, bound to 127.0.0.1 on a random free port.

Every /api call must carry the per-session token, so other websites open in
your browser cannot drive the simulator through localhost.
"""

import hmac
import json
import logging
import secrets
import socket
import threading
import time
from typing import Callable, Optional

from flask import Flask, Response, abort, jsonify, request, send_from_directory

from . import __version__, geo
from .device import DeviceManager
from .paths import CONFIG_FILE, EXPORT_DIR, WEB_DIR
from .platform_utils import is_admin, relaunch_as_admin
from .simulator import Route, Simulator
from .store import Favorites, History, read_json

SaveDialog = Callable[[str, str], Optional[str]]  # (default filename, file type label) -> path

DEFAULT_TILES = {
    "map": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "map_attr": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    "sat": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    "sat_attr": "Imagery &copy; Esri, Maxar, Earthstar Geographics",
}


def tile_config() -> dict:
    """Optional MapTiler key in config.json: {"maptiler_key": "..."}."""
    key = str(read_json(CONFIG_FILE, {}).get("maptiler_key") or "").strip()
    if not key:
        return DEFAULT_TILES
    attr = '&copy; <a href="https://www.maptiler.com/copyright/">MapTiler</a> &copy; OpenStreetMap'
    return {
        "map": f"https://api.maptiler.com/maps/streets-v2/256/{{z}}/{{x}}/{{y}}.png?key={key}",
        "map_attr": attr,
        "sat": f"https://api.maptiler.com/tiles/satellite-v2/{{z}}/{{x}}/{{y}}.jpg?key={key}",
        "sat_attr": attr,
    }


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _num(data: dict, key: str, default: float | None = None) -> float | None:
    try:
        return float(data[key])
    except (KeyError, TypeError, ValueError):
        return default


def create_app(sim: Simulator, device: DeviceManager, favorites: Favorites, history: History,
               save_dialog: SaveDialog, quit_app: Callable[[], None]) -> tuple[Flask, str]:
    app = Flask(__name__, static_folder=None)
    token = secrets.token_urlsafe(24)
    started = time.time()

    @app.before_request
    def check_request():
        # Host check blocks DNS-rebinding; the token blocks cross-site requests.
        if request.host.split(":")[0] not in ("127.0.0.1", "localhost"):
            abort(403)
        if request.path.startswith("/api/"):
            sent = request.headers.get("X-Token", "")
            if not hmac.compare_digest(sent, token):
                abort(403)

    def body() -> dict:
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}

    ok = lambda **extra: jsonify({"ok": True, **extra})  # noqa: E731

    # ---------- UI ----------
    @app.get("/")
    def index():
        html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
        config = {"token": token, "tiles": tile_config(), "version": __version__,
                  "start": {"lat": sim.lat, "lon": sim.lon}}
        html = html.replace("/*__CONFIG__*/", "window.APP_CONFIG = " + json.dumps(config) + ";")
        return Response(html, mimetype="text/html", headers={"Cache-Control": "no-store"})

    @app.get("/static/<path:name>")
    def static_files(name):
        return send_from_directory(WEB_DIR, name, max_age=0)

    # ---------- state (single poll endpoint) ----------
    @app.get("/api/state")
    def state():
        return jsonify({"sim": sim.snapshot(), "device": device.status(), "admin": is_admin(),
                        "uptime": round(time.time() - started)})

    # ---------- simulation ----------
    @app.post("/api/start")
    def start():
        d = body()
        lat, lon = _num(d, "lat"), _num(d, "lon")
        if lat is not None and lon is not None:
            sim.move_to(lat, lon)
        sim.set_enabled(True)
        return ok()

    @app.post("/api/stop")
    def stop():
        sim.set_enabled(False)
        return ok()

    @app.post("/api/move")
    def move():
        d = body()
        lat, lon = _num(d, "lat"), _num(d, "lon")
        if lat is None or lon is None or not sim.move_to(lat, lon):
            return jsonify({"ok": False}), 400
        return ok()

    @app.post("/api/nudge")
    def nudge():
        sim.nudge(str(body().get("dir", "")))
        return ok()

    @app.post("/api/step")
    def step():
        sim.step_m = max(1.0, min(1000.0, _num(body(), "meters", 25.0)))
        return ok()

    # ---------- routes ----------
    @app.post("/api/route/start")
    def route_start():
        d = body()
        pts = []
        for p in d.get("points") or []:
            try:
                lat, lon = float(p["lat"]), float(p["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if geo.valid_latlon(lat, lon):
                pts.append((lat, lon))
        stops = {int(i) for i in d.get("stops") or [] if isinstance(i, (int, float))}
        route = Route(pts, stops, max(1.0, _num(d, "speed_kmh", 45.0)), bool(d.get("loop")),
                      bool(d.get("jitter", True)), max(0.0, _num(d, "dwell", 0.0)))
        return ok() if sim.start_route(route) else (jsonify({"ok": False}), 400)

    @app.post("/api/route/config")
    def route_config():
        d = body()
        sim.configure_route(_num(d, "speed_kmh"), d.get("loop"), d.get("jitter"))
        return ok()

    @app.post("/api/route/pause")
    def route_pause():
        sim.toggle_pause()
        return ok()

    @app.post("/api/route/clear")
    def route_clear():
        sim.clear_route()
        return ok()

    # ---------- places ----------
    @app.get("/api/suggest")
    def suggest():
        q = (request.args.get("q") or "").strip()
        if len(q) < 3 or geo.parse_latlon(q) or q.lower().startswith("http"):
            return jsonify({"results": []})
        try:
            return jsonify({"results": list(geo.suggest(q))})
        except Exception:  # noqa: BLE001 - network problems just mean "no suggestions"
            return jsonify({"results": []})

    @app.post("/api/search")
    def search():
        try:
            hit = geo.resolve_query(str(body().get("query", "")))
        except Exception:  # noqa: BLE001
            return jsonify({"ok": False, "error": "network"})
        if not hit:
            return jsonify({"ok": False, "error": "not_found"})
        sim.move_to(*hit)
        return ok(lat=hit[0], lon=hit[1])

    # ---------- favorites / history ----------
    @app.get("/api/favorites")
    def favorites_list():
        return jsonify({"favorites": favorites.all()})

    @app.post("/api/favorites")
    def favorites_add():
        favorites.add(body())
        return jsonify({"favorites": favorites.all()})

    @app.delete("/api/favorites/<fav_id>")
    def favorites_delete(fav_id):
        favorites.delete(fav_id)
        return jsonify({"favorites": favorites.all()})

    @app.post("/api/favorites/import")
    def favorites_import():
        added = favorites.import_many(body().get("favorites"))
        return jsonify({"favorites": favorites.all(), "added": added})

    def save_text(default_name: str, kind: str, text: str):
        path = save_dialog(default_name, kind)
        if not path:
            return jsonify({"ok": False, "cancelled": True})
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError as exc:
            return jsonify({"ok": False, "error": str(exc)})
        return ok(path=path)

    @app.post("/api/favorites/export")
    def favorites_export():
        text = json.dumps(favorites.all(), indent=2, ensure_ascii=False)
        return save_text(time.strftime("favorites_%Y%m%d.json"), "JSON (*.json)", text)

    @app.get("/api/history")
    def history_list():
        return jsonify({"items": history.all()})

    @app.post("/api/gpx/export")
    def gpx_export():
        pts = [p for p in body().get("points") or [] if isinstance(p, dict)]
        try:
            trkpts = "\n".join(f'      <trkpt lat="{float(p["lat"]):.7f}" lon="{float(p["lon"]):.7f}"/>' for p in pts)
        except (KeyError, TypeError, ValueError):
            return jsonify({"ok": False}), 400
        if len(pts) < 2:
            return jsonify({"ok": False}), 400
        gpx = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               f'<gpx version="1.1" creator="iOS GPS Simulator {__version__}" xmlns="http://www.topografix.com/GPX/1/1">\n'
               f'  <trk><name>Ruta / Route</name><trkseg>\n{trkpts}\n  </trkseg></trk>\n</gpx>\n')
        return save_text(time.strftime("route_%Y%m%d_%H%M%S.gpx"), "GPX (*.gpx)", gpx)

    # ---------- app ----------
    @app.post("/api/elevate")
    def elevate():
        if not relaunch_as_admin():
            return jsonify({"ok": False})
        threading.Timer(0.5, quit_app).start()
        return ok()

    return app, token


def serve(app: Flask, port: int) -> None:
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    app.run(host="127.0.0.1", port=port, threaded=True, debug=False, use_reloader=False)


def default_save_path(default_name: str, _kind: str) -> str:
    """Fallback when there is no native dialog (browser mode): save to the data folder."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    return str(EXPORT_DIR / default_name)
