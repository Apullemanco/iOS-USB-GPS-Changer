import asyncio
import ctypes
import importlib
import inspect
import io
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
HTML_PAGE = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <title>GPS Simulador</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    body { margin: 0; font-family: 'Segoe UI', sans-serif; background: #121212; color: #fff; user-select: none; }
    #bar { padding: 12px 16px; background: #1b1b1f; display: flex; gap: 12px; align-items: center; border-bottom: 1px solid #2c2c35; flex-wrap: wrap; }
    button { padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 13px; }
    #btn-start { background: #22c55e; color: #052e16; }
    #btn-stop { background: #ef4444; color: #fff; }
    #coords { font-family: monospace; font-size: 13px; color: #a1a1aa; }
    #status-badge { font-size: 12px; font-weight: 600; color: #fbbf24; }
    #err { color: #f87171; font-size: 12px; }
    #map { height: calc(100vh - 57px); width: 100%; }
  </style>
</head>
<body>
  <div id="bar">
    <button id="btn-start">Iniciar Simulacion</button>
    <button id="btn-stop">Detener</button>
    <span id="coords">Lat: 25.686600, Lon: -100.316100</span>
    <span id="status-badge">Detenido</span>
    <span id="err"></span>
  </div>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    let lat = 25.6866, lon = -100.3161;
    const map = L.map("map").setView([lat, lon], 15);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(map);
    const marker = L.marker([lat, lon], { draggable: true }).addTo(map);
    function updateLabel() { document.getElementById("coords").textContent = `Lat: ${lat.toFixed(6)}, Lon: ${lon.toFixed(6)}`; }
    function sendMove() {
      marker.setLatLng([lat, lon]);
      updateLabel();
      fetch("/move", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lat, lon }) });
    }
    map.on("click", (e) => { lat = e.latlng.lat; lon = e.latlng.lng; sendMove(); });
    marker.on("dragend", (e) => { const p = e.target.getLatLng(); lat = p.lat; lon = p.lng; sendMove(); });
    document.getElementById("btn-start").onclick = () => {
      fetch("/start", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lat, lon }) });
    };
    document.getElementById("btn-stop").onclick = () => { fetch("/stop", { method: "POST" }); };
    document.addEventListener("keydown", (e) => {
      const step = 0.0002;
      if (e.key === "w" || e.key === "W") { lat += step; sendMove(); }
      if (e.key === "s" || e.key === "S") { lat -= step; sendMove(); }
      if (e.key === "a" || e.key === "A") { lon -= step; sendMove(); }
      if (e.key === "d" || e.key === "D") { lon += step; sendMove(); }
    });
    setInterval(() => {
      fetch("/status").then(r => r.json()).then(d => {
        const badge = document.getElementById("status-badge");
        badge.textContent = d.status_text;
        badge.style.color = d.active ? "#4ade80" : "#fbbf24";
        document.getElementById("err").textContent = d.error ? " | " + d.error : "";
      }).catch(() => {});
    }, 1000);
  </script>
</body>
</html>
"""
state = {"running": False, "active": False, "status_text": "Detenido", "lat": 25.6866, "lon": -100.3161, "error": None, "tunnel_err": None}

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
    return jsonify(state)

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
    state["status_text"] = "Deteniendo..."
    return jsonify({"ok": True})

@app.route("/move", methods=["POST"])
def move():
    data = request.get_json(silent=True) or {}
    if "lat" in data and "lon" in data:
        state["lat"] = float(data["lat"])
        state["lon"] = float(data["lon"])
    return jsonify({"ok": True})

def run_flask():
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    try:
        threading.Thread(target=start_tunnel_daemon, daemon=True).start()
        threading.Thread(target=location_loop, daemon=True).start()
        threading.Thread(target=run_flask, daemon=True).start()
        time.sleep(1.5)
        try:
            webview.create_window("GPS Simulador", "http://127.0.0.1:5000", width=1050, height=700)
            webview.start()
        except Exception:
            webbrowser.open("http://127.0.0.1:5000")
            while True:
                time.sleep(1)
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(0, str(e), "Error GPS Simulador", 16)

