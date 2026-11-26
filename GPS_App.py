import asyncio
import ctypes
import importlib
import inspect
import io
import json
import math
import os
import pkgutil
import sys
import threading
import time
import webbrowser

class DummyStream(io.TextIOBase):
    def write(self, s):
        return len(s)
    def flush(self):
        pass
    def isatty(self):
        return False

if sys.stdout is None:
    sys.stdout = DummyStream()
if sys.stderr is None:
    sys.stderr = DummyStream()

import requests
import webview
from flask import Flask, jsonify, render_template_string, request
import pymobiledevice3.services as pmd3_services
from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService

app = Flask(__name__)

FAVORITES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "favoritos.json")

def load_favorites():
    if os.path.exists(FAVORITES_FILE):
        try:
            with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []

def save_favorites(items):
    try:
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

HTML_PAGE = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <title>GPS Simulador</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    body { margin: 0; font-family: 'Segoe UI', sans-serif; background: #121212; color: #fff; user-select: none; }
    #bar { padding: 10px 14px; background: #1b1b1f; display: flex; gap: 8px; align-items: center; border-bottom: 1px solid #2c2c35; flex-wrap: wrap; }
    .group { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
    button { padding: 7px 12px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 12px; background: #2c2c35; color: #f4f4f5; }
    button:hover { filter: brightness(1.1); }
    input, select { padding: 7px 10px; border-radius: 6px; border: 1px solid #32323d; background: #121215; color: #fff; font-size: 12px; }
    #btn-start { background: #22c55e; color: #052e16; }
    #btn-stop { background: #ef4444; color: #fff; }
    #btn-route-mode.active-mode { background: #3b82f6; color: #fff; }
    #btn-route-run { background: #10b981; color: #052e16; }
    #btn-route-pause { background: #f59e0b; color: #1c1917; }
    #coords { font-family: monospace; font-size: 12px; color: #a1a1aa; }
    #status-badge { font-size: 12px; font-weight: 600; color: #fbbf24; }
    #err { color: #f87171; font-size: 12px; }
    #map { height: calc(100vh - 98px); width: 100%; }
  </style>
</head>
<body>
  <div id="bar">
    <div class="group">
      <button id="btn-start">Iniciar Simulacion</button>
      <button id="btn-stop">Detener</button>
      <span id="coords">Lat: 25.686600, Lon: -100.316100</span>
      <span id="status-badge">Detenido</span>
    </div>
    <div class="group">
      <input id="search-input" type="text" placeholder="Direccion o lat, lon" style="width: 210px;" />
      <button id="btn-search">Buscar</button>
    </div>
    <div class="group">
      <input id="fav-name" type="text" placeholder="Nombre favorito" style="width: 130px;" />
      <button id="btn-fav-save">Guardar</button>
      <select id="fav-select" style="width: 160px;">
        <option value="">Favoritos...</option>
      </select>
      <button id="btn-fav-go">Ir</button>
      <button id="btn-fav-del">Borrar</button>
    </div>
  </div>
  <div id="bar" style="padding-top: 8px; padding-bottom: 8px;">
    <div class="group">
      <button id="btn-route-mode">Agregar puntos ruta</button>
      <button id="btn-route-run">Iniciar ruta</button>
      <button id="btn-route-pause">Pausar ruta</button>
      <button id="btn-route-clear">Limpiar ruta</button>
      <label style="font-size: 12px; color: #d4d4d8;">Velocidad (km/h):</label>
      <input id="route-speed" type="number" min="1" max="250" value="15" style="width: 68px;" />
      <label style="font-size: 12px; color: #d4d4d8;"><input id="route-loop" type="checkbox" /> Bucle</label>
      <span id="route-info" style="font-size: 12px; color: #93c5fd;">Puntos: 0</span>
    </div>
    <span id="err"></span>
  </div>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    let lat = 25.6866, lon = -100.3161;
    let addingWaypoints = false;
    let waypoints = [];
    let waypointMarkers = [];
    let routeLine = null;
    let favorites = [];

    const map = L.map("map").setView([lat, lon], 15);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(map);
    const marker = L.marker([lat, lon], { draggable: true }).addTo(map);

    function updateLabel() {
      document.getElementById("coords").textContent = `Lat: ${lat.toFixed(6)}, Lon: ${lon.toFixed(6)}`;
    }

    function sendMove(syncRemote = true) {
      marker.setLatLng([lat, lon]);
      updateLabel();
      if (syncRemote) {
        fetch("/move", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lat, lon })
        });
      }
    }

    function redrawRoute() {
      waypointMarkers.forEach(m => map.removeLayer(m));
      waypointMarkers = [];
      if (routeLine) {
        map.removeLayer(routeLine);
        routeLine = null;
      }
      waypoints.forEach((pt, idx) => {
        const wm = L.circleMarker([pt.lat, pt.lon], { radius: 6, color: "#60a5fa", fillOpacity: 0.9 }).addTo(map);
        wm.bindTooltip(`${idx + 1}`);
        waypointMarkers.push(wm);
      });
      if (waypoints.length >= 2) {
        routeLine = L.polyline(waypoints.map(p => [p.lat, p.lon]), { color: "#3b82f6", weight: 3 }).addTo(map);
      }
      document.getElementById("route-info").textContent = `Puntos: ${waypoints.length}`;
    }

    function renderFavorites() {
      const sel = document.getElementById("fav-select");
      sel.innerHTML = '<option value="">Favoritos...</option>';
      favorites.forEach((f, i) => {
        const opt = document.createElement("option");
        opt.value = String(i);
        opt.textContent = f.name;
        sel.appendChild(opt);
      });
    }

    function loadFavoritesFromServer() {
      fetch("/favorites").then(r => r.json()).then(d => {
        favorites = d.favorites || [];
        renderFavorites();
      }).catch(() => {});
    }

    map.on("click", (e) => {
      lat = e.latlng.lat;
      lon = e.latlng.lng;
      sendMove(true);
      if (addingWaypoints) {
        waypoints.push({ lat, lon });
        redrawRoute();
      }
    });

    marker.on("dragend", (e) => {
      const p = e.target.getLatLng();
      lat = p.lat;
      lon = p.lng;
      sendMove(true);
    });

    document.getElementById("btn-start").onclick = () => {
      fetch("/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat, lon })
      });
    };

    document.getElementById("btn-stop").onclick = () => {
      fetch("/stop", { method: "POST" });
    };

    document.getElementById("btn-search").onclick = () => {
      const q = document.getElementById("search-input").value.trim();
      if (!q) return;
      fetch("/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q })
      }).then(r => r.json()).then(d => {
        if (d.ok) {
          lat = d.lat;
          lon = d.lon;
          map.setView([lat, lon], 16);
          sendMove(true);
        }
      }).catch(() => {});
    };

    document.getElementById("btn-fav-save").onclick = () => {
      const name = document.getElementById("fav-name").value.trim() || `Punto ${favorites.length + 1}`;
      fetch("/favorites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, lat, lon })
      }).then(r => r.json()).then(d => {
        favorites = d.favorites || [];
        renderFavorites();
        document.getElementById("fav-name").value = "";
      }).catch(() => {});
    };

    document.getElementById("btn-fav-go").onclick = () => {
      const idx = parseInt(document.getElementById("fav-select").value, 10);
      if (!isNaN(idx) && favorites[idx]) {
        lat = favorites[idx].lat;
        lon = favorites[idx].lon;
        map.setView([lat, lon], 16);
        sendMove(true);
      }
    };

    document.getElementById("btn-fav-del").onclick = () => {
      const idx = parseInt(document.getElementById("fav-select").value, 10);
      if (isNaN(idx)) return;
      fetch(`/favorites/${idx}`, { method: "DELETE" }).then(r => r.json()).then(d => {
        favorites = d.favorites || [];
        renderFavorites();
      }).catch(() => {});
    };

    document.getElementById("btn-route-mode").onclick = () => {
      addingWaypoints = !addingWaypoints;
      const btn = document.getElementById("btn-route-mode");
      btn.classList.toggle("active-mode", addingWaypoints);
    };

    document.getElementById("btn-route-run").onclick = () => {
      if (waypoints.length < 2) return;
      addingWaypoints = false;
      document.getElementById("btn-route-mode").classList.remove("active-mode");
      const speedKmh = parseFloat(document.getElementById("route-speed").value) || 15;
      const loop = document.getElementById("route-loop").checked;
      fetch("/route/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ waypoints, speed_kmh: speedKmh, loop })
      });
    };

    document.getElementById("btn-route-pause").onclick = () => {
      fetch("/route/pause", { method: "POST" });
    };

    document.getElementById("btn-route-clear").onclick = () => {
      waypoints = [];
      redrawRoute();
      fetch("/route/clear", { method: "POST" });
    };

    document.addEventListener("keydown", (e) => {
      const tag = document.activeElement ? document.activeElement.tagName : "";
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      const step = 0.0002;
      if (e.key === "w" || e.key === "W") { lat += step; sendMove(true); }
      if (e.key === "s" || e.key === "S") { lat -= step; sendMove(true); }
      if (e.key === "a" || e.key === "A") { lon -= step; sendMove(true); }
      if (e.key === "d" || e.key === "D") { lon += step; sendMove(true); }
    });

    loadFavoritesFromServer();

    setInterval(() => {
      fetch("/status").then(r => r.json()).then(d => {
        const badge = document.getElementById("status-badge");
        badge.textContent = d.status_text;
        badge.style.color = d.active ? "#4ade80" : "#fbbf24";
        document.getElementById("err").textContent = d.error ? " | " + d.error : "";
        if (d.route_running && typeof d.lat === "number" && typeof d.lon === "number") {
          lat = d.lat;
          lon = d.lon;
          marker.setLatLng([lat, lon]);
          updateLabel();
        }
      }).catch(() => {});
    }, 500);
  </script>
</body>
</html>
"""

state = {
    "running": False,
    "active": False,
    "status_text": "Detenido",
    "lat": 25.6866,
    "lon": -100.3161,
    "error": None,
    "tunnel_err": None,
    "route_running": False,
    "route_waypoints": [],
    "route_seg_idx": 0,
    "route_speed_kmh": 15.0,
    "route_loop": False,
    "favorites": load_favorites(),
}

def distance_meters(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def route_worker():
    tick = 0.25
    while True:
        if state["route_running"] and state["running"]:
            pts = state["route_waypoints"]
            idx = state["route_seg_idx"]
            if len(pts) >= 2 and idx < len(pts) - 1:
                target = pts[idx + 1]
                cur_lat = state["lat"]
                cur_lon = state["lon"]
                dist = distance_meters(cur_lat, cur_lon, target["lat"], target["lon"])
                speed_mps = max(0.5, (float(state["route_speed_kmh"]) * 1000.0) / 3600.0)
                step_m = speed_mps * tick
                if dist <= step_m or dist < 1e-6:
                    state["lat"] = float(target["lat"])
                    state["lon"] = float(target["lon"])
                    if idx + 1 < len(pts) - 1:
                        state["route_seg_idx"] = idx + 1
                    elif state["route_loop"]:
                        state["route_seg_idx"] = 0
                        state["lat"] = float(pts[0]["lat"])
                        state["lon"] = float(pts[0]["lon"])
                    else:
                        state["route_running"] = False
                else:
                    ratio = step_m / dist
                    state["lat"] = cur_lat + (float(target["lat"]) - cur_lat) * ratio
                    state["lon"] = cur_lon + (float(target["lon"]) - cur_lon) * ratio
            else:
                state["route_running"] = False
        time.sleep(tick)

def _load_dvt_tools():
    dvt_cls = None
    loc_cls = None
    mounter_fn = None
    try:
        from pymobiledevice3.services.dvt.dvt_secure_socket_proxy import DvtSecureSocketProxyService
        dvt_cls = DvtSecureSocketProxyService
    except Exception:
        pass
    try:
        from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation
        loc_cls = LocationSimulation
    except Exception:
        pass
    try:
        from pymobiledevice3.services.mobile_image_mounter import auto_mount
        mounter_fn = auto_mount
    except Exception:
        pass
    if not (dvt_cls and loc_cls and mounter_fn):
        for _, modname, _ in pkgutil.walk_packages(pmd3_services.__path__, pmd3_services.__name__ + "."):
            if any(k in modname for k in ("dvt", "mounter", "location")):
                try:
                    mod = importlib.import_module(modname)
                    if dvt_cls is None:
                        dvt_cls = getattr(mod, "DvtSecureSocketProxyService", None) or getattr(mod, "DvtProvider", None)
                    if loc_cls is None:
                        loc_cls = getattr(mod, "LocationSimulation", None)
                    if mounter_fn is None:
                        mounter_fn = getattr(mod, "auto_mount", None)
                except Exception:
                    pass
    return dvt_cls, loc_cls, mounter_fn

def start_tunnel_daemon():
    from pymobiledevice3.__main__ import main as pmd3_main
    sys.argv = ["pymobiledevice3", "remote", "tunneld", "--port", "49155"]
    try:
        pmd3_main()
    except (Exception, SystemExit) as e:
        state["tunnel_err"] = str(e)

def get_tunnel_rsd():
    resp = requests.get("http://127.0.0.1:49155/", timeout=3)
    data = resp.json()
    for udid, info in data.items():
        if isinstance(info, list) and len(info) > 0:
            info = info[0]
        if isinstance(info, dict) and info.get("tunnel-address") and info.get("tunnel-port"):
            return info["tunnel-address"], int(info["tunnel-port"])
    return None, None

async def _maybe_await(val):
    if inspect.isawaitable(val):
        return await val
    return val

async def _open_obj(obj):
    if hasattr(obj, "__aenter__"):
        res = await obj.__aenter__()
        return res if res is not None else obj
    if hasattr(obj, "connect"):
        await _maybe_await(obj.connect())
        return obj
    if hasattr(obj, "__enter__"):
        res = obj.__enter__()
        return res if res is not None else obj
    return obj

async def _close_obj(obj):
    if obj is None:
        return
    try:
        if hasattr(obj, "__aexit__"):
            await obj.__aexit__(None, None, None)
        elif hasattr(obj, "close"):
            await _maybe_await(obj.close())
        elif hasattr(obj, "__exit__"):
            obj.__exit__(None, None, None)
    except Exception:
        pass

async def _run_dvt_session(addr, port):
    dvt_cls, loc_cls, mounter_fn = _load_dvt_tools()
    if not dvt_cls or not loc_cls:
        raise RuntimeError("No se encontro el modulo DVT en pymobiledevice3.")
    rsd = await _open_obj(RemoteServiceDiscoveryService((addr, port)))
    dvt = None
    sim = None
    try:
        try:
            dvt = await _open_obj(dvt_cls(rsd))
        except Exception:
            if mounter_fn is not None:
                state["status_text"] = "Montando imagen de desarrollador..."
                await _maybe_await(mounter_fn(rsd))
            dvt = await _open_obj(dvt_cls(rsd))
        sim = await _open_obj(loc_cls(dvt))
        set_fn = getattr(sim, "set", None) or getattr(sim, "simulate_location", None)
        while state["running"]:
            await _maybe_await(set_fn(state["lat"], state["lon"]))
            state["active"] = True
            state["status_text"] = "GPS Activo en iPhone"
            state["error"] = None
            await asyncio.sleep(0.5)
        clear_fn = getattr(sim, "clear", None) or getattr(sim, "stop", None)
        if clear_fn is not None:
            await _maybe_await(clear_fn())
    finally:
        await _close_obj(sim)
        await _close_obj(dvt)
        await _close_obj(rsd)
        state["active"] = False
        if not state["running"]:
            state["status_text"] = "Detenido"

def location_loop():
    while True:
        if state["running"]:
            try:
                addr, port = get_tunnel_rsd()
                if addr and port:
                    asyncio.run(_run_dvt_session(addr, port))
                else:
                    state["active"] = False
                    state["status_text"] = "Buscando iPhone..."
                    state["error"] = "iPhone no detectado. Revisa el cable USB."
            except requests.exceptions.ConnectionError:
                state["active"] = False
                state["status_text"] = "Iniciando tunel..."
                state["error"] = ("Error de tunel: " + state["tunnel_err"]) if state["tunnel_err"] else "Iniciando tunel interno..."
            except Exception as e:
                state["active"] = False
                state["status_text"] = "Error"
                msg = str(e)
                if "DeveloperMode" in msg or "InvalidService" in msg:
                    msg += " (Activa Modo de desarrollador en iPhone > Configuracion > Privacidad y seguridad)"
                state["error"] = msg
        time.sleep(1)

@app.route("/")
def index():
    return render_template_string(HTML_PAGE)

@app.route("/status")
def status():
    return jsonify({
        "running": state["running"],
        "active": state["active"],
        "status_text": state["status_text"],
        "lat": state["lat"],
        "lon": state["lon"],
        "error": state["error"],
        "route_running": state["route_running"],
    })

@app.route("/start", methods=["POST"])
def start():
    data = request.get_json(silent=True) or {}
    if "lat" in data and "lon" in data:
        state["lat"] = float(data["lat"])
        state["lon"] = float(data["lon"])
    state["running"] = True
    state["status_text"] = "Conectando..."
    return jsonify({"ok": True})

@app.route("/stop", methods=["POST"])
def stop():
    state["running"] = False
    state["route_running"] = False
    state["status_text"] = "Deteniendo..."
    return jsonify({"ok": True})

@app.route("/move", methods=["POST"])
def move():
    data = request.get_json(silent=True) or {}
    if "lat" in data and "lon" in data:
        state["lat"] = float(data["lat"])
        state["lon"] = float(data["lon"])
    return jsonify({"ok": True})

@app.route("/search", methods=["POST"])
def search_place():
    data = request.get_json(silent=True) or {}
    q = (data.get("query") or "").strip()
    if not q:
        return jsonify({"ok": False})
    if "," in q:
        parts = [p.strip() for p in q.split(",")]
        if len(parts) == 2:
            try:
                rlat = float(parts[0])
                rlon = float(parts[1])
                state["lat"] = rlat
                state["lon"] = rlon
                return jsonify({"ok": True, "lat": rlat, "lon": rlon})
            except ValueError:
                pass
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "json", "limit": 1},
            headers={"User-Agent": "GPS-Simulador/1.0"},
            timeout=6,
        )
        items = resp.json()
        if items:
            rlat = float(items[0]["lat"])
            rlon = float(items[0]["lon"])
            state["lat"] = rlat
            state["lon"] = rlon
            return jsonify({"ok": True, "lat": rlat, "lon": rlon})
    except Exception:
        pass
    return jsonify({"ok": False})

@app.route("/favorites", methods=["GET", "POST"])
def favorites_endpoint():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "Favorito").strip()
        try:
            flat = float(data["lat"])
            flon = float(data["lon"])
            state["favorites"].append({"name": name, "lat": flat, "lon": flon})
            save_favorites(state["favorites"])
        except Exception:
            pass
    return jsonify({"favorites": state["favorites"]})

@app.route("/favorites/<int:idx>", methods=["DELETE"])
def delete_favorite(idx):
    if 0 <= idx < len(state["favorites"]):
        state["favorites"].pop(idx)
        save_favorites(state["favorites"])
    return jsonify({"favorites": state["favorites"]})

@app.route("/route/start", methods=["POST"])
def route_start():
    data = request.get_json(silent=True) or {}
    pts = data.get("waypoints") or []
    if len(pts) >= 2:
        state["route_waypoints"] = pts
        state["route_seg_idx"] = 0
        state["route_speed_kmh"] = float(data.get("speed_kmh") or 15.0)
        state["route_loop"] = bool(data.get("loop"))
        state["lat"] = float(pts[0]["lat"])
        state["lon"] = float(pts[0]["lon"])
        state["route_running"] = True
        state["running"] = True
    return jsonify({"ok": True})

@app.route("/route/pause", methods=["POST"])
def route_pause():
    state["route_running"] = False
    return jsonify({"ok": True})

@app.route("/route/clear", methods=["POST"])
def route_clear():
    state["route_running"] = False
    state["route_waypoints"] = []
    state["route_seg_idx"] = 0
    return jsonify({"ok": True})

def run_flask():
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    try:
        threading.Thread(target=start_tunnel_daemon, daemon=True).start()
        threading.Thread(target=location_loop, daemon=True).start()
        threading.Thread(target=route_worker, daemon=True).start()
        threading.Thread(target=run_flask, daemon=True).start()
        time.sleep(1.5)
        try:
            webview.create_window("GPS Simulador", "http://127.0.0.1:5000", width=1150, height=740)
            webview.start()
        except Exception:
            webbrowser.open("http://127.0.0.1:5000")
            while True:
                time.sleep(1)
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(0, str(e), "Error GPS Simulador", 16)