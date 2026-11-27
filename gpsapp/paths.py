"""Filesystem locations.

User data (favorites, history, config) lives in a per-user folder, NOT next to the
script: a PyInstaller --onefile build runs from a temporary folder that is deleted
on exit, so anything saved there would be lost.
"""

import os
import shutil
import sys
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent / "web"


def _default_data_dir() -> Path:
    override = os.environ.get("GPS_SIM_DATA_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home())
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "iOS-GPS-Simulator"


DATA_DIR = _default_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)

FAVORITES_FILE = DATA_DIR / "favorites.json"
HISTORY_FILE = DATA_DIR / "history.json"
CONFIG_FILE = DATA_DIR / "config.json"
EXPORT_DIR = DATA_DIR / "exports"
WEBVIEW_STORAGE = DATA_DIR / "webview"


def migrate_legacy_files() -> None:
    """Copy data files written by v1 (Spanish names, next to the script/exe) once."""
    legacy_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else WEB_DIR.parent.parent
    pairs = {
        "favoritos.json": FAVORITES_FILE,
        "historial.json": HISTORY_FILE,
        "config.json": CONFIG_FILE,
    }
    for old_name, new_path in pairs.items():
        old_path = legacy_dir / old_name
        if old_path.is_file() and not new_path.exists():
            try:
                shutil.copy2(old_path, new_path)
            except OSError:
                pass
