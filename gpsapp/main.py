"""Application entry point: wires the simulator, device thread, API and window together."""

import faulthandler
import logging
import os
import sys
import threading
import time
import webbrowser

from . import APP_NAME, __version__
from .device import DeviceManager
from .paths import DATA_DIR, FAVORITES_FILE, HISTORY_FILE, WEBVIEW_STORAGE, migrate_legacy_files
from .platform_utils import show_error, start_global_hotkeys
from .server import create_app, default_save_path, free_port, serve
from .simulator import Simulator
from .store import Favorites, History

log = logging.getLogger("gpsapp")
_crash_file = None


def _setup_logging() -> None:
    # --noconsole builds have no stdout/stderr; log to a file in the data folder instead.
    global _crash_file
    handlers = [logging.FileHandler(DATA_DIR / "app.log", mode="w", encoding="utf-8")]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    # force=True: pymobiledevice3 configures the root logger on import, which would
    # otherwise silently disable this configuration.
    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Record native crashes (e.g. inside WebView2) that Python logging cannot see.
    _crash_file = open(DATA_DIR / "crash.log", "w", encoding="utf-8")
    faulthandler.enable(_crash_file)
    sys.excepthook = lambda *exc: logging.getLogger("gpsapp").critical("Uncaught exception", exc_info=exc)
    threading.excepthook = lambda a: logging.getLogger("gpsapp").critical(
        "Uncaught exception in thread %s", a.thread.name if a.thread else "?",
        exc_info=(a.exc_type, a.exc_value, a.exc_traceback))
    for noisy in ("pymobiledevice3", "urllib3", "asyncio", "quic", "werkzeug"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _wait_for_port(port: int, timeout: float = 10.0) -> None:
    import socket
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)


def main() -> None:
    _setup_logging()
    migrate_legacy_files()
    log.info("%s %s starting, data folder: %s", APP_NAME, __version__, DATA_DIR)

    history = History(HISTORY_FILE)
    favorites = Favorites(FAVORITES_FILE)
    last = history.all()[0] if history.all() else {"lat": 25.6866, "lon": -100.3161}
    sim = Simulator(last["lat"], last["lon"], on_move=history.push)
    device = DeviceManager(sim)
    window = None

    def save_dialog(default_name: str, kind: str):
        if window is None:
            return default_save_path(default_name, kind)
        import webview
        result = window.create_file_dialog(webview.FileDialog.SAVE, save_filename=default_name, file_types=(kind,))
        if isinstance(result, (list, tuple)):
            result = result[0] if result else None
        return result or None

    def quit_app() -> None:
        device.shutdown()
        os._exit(0)

    def on_hotkey(action: str) -> None:
        if action == "pause":
            sim.toggle_pause()
        elif action == "restore":
            sim.set_enabled(False)
        else:
            sim.nudge(action)

    app, _token = create_app(sim, device, favorites, history, save_dialog, quit_app)
    port = free_port()
    url = f"http://127.0.0.1:{port}/"

    threading.Thread(target=sim.run_forever, name="route", daemon=True).start()
    device.start()
    threading.Thread(target=serve, args=(app, port), name="http", daemon=True).start()
    start_global_hotkeys(on_hotkey)
    _wait_for_port(port)
    log.info("UI ready at %s", url)

    try:
        import webview
        window = webview.create_window(APP_NAME, url, width=1200, height=780, min_size=(760, 520))
        WEBVIEW_STORAGE.mkdir(parents=True, exist_ok=True)
        # private_mode=False keeps localStorage (language, "help seen") between launches.
        webview.start(private_mode=False, storage_path=str(WEBVIEW_STORAGE))
    except Exception:  # noqa: BLE001 - no webview runtime: fall back to the default browser
        log.warning("pywebview unavailable, opening the browser instead", exc_info=True)
        window = None
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    finally:
        log.info("Window closed, shutting down")
        device.shutdown()  # restores the device's real location before exiting


def run() -> None:
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("gpsapp").exception("Fatal error")
        show_error("La aplicación no pudo iniciar / The app could not start:\n\n"
                   f"{type(exc).__name__}: {exc}\n\n"
                   f"Registro / Log: {DATA_DIR / 'app.log'}")
        raise


if __name__ == "__main__":
    run()
