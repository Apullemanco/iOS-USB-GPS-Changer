"""Small thread-safe JSON stores for favorites, history and config."""

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .geo import distance_m, valid_latlon


def read_json(path: Path, default: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, type(default)) else default
    except (OSError, ValueError):
        return default


def write_json(path: Path, data: Any) -> None:
    """Atomic write: a crash mid-save never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def clean_favorite(raw: Any) -> dict | None:
    """Validate an untrusted favorite (from the UI or an imported file)."""
    try:
        lat, lon = float(raw["lat"]), float(raw["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not valid_latlon(lat, lon):
        return None
    return {
        "id": str(raw.get("id") or uuid.uuid4().hex[:12]),
        "name": str(raw.get("name") or "").strip()[:120] or f"{lat:.5f}, {lon:.5f}",
        "folder": str(raw.get("folder") or "").strip()[:60],
        "lat": lat,
        "lon": lon,
    }


class Favorites:
    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        loaded = read_json(path, [])
        self._items = [f for f in map(clean_favorite, loaded) if f]
        if loaded and any("id" not in f for f in loaded if isinstance(f, dict)):
            self._save()  # give v1 favorites stable ids

    def _save(self) -> None:
        write_json(self._path, self._items)

    def all(self) -> list[dict]:
        with self._lock:
            return list(self._items)

    def add(self, raw: Any) -> bool:
        fav = clean_favorite({**raw, "id": None}) if isinstance(raw, dict) else None
        if not fav:
            return False
        with self._lock:
            self._items.append(fav)
            self._save()
        return True

    def delete(self, fav_id: str) -> None:
        with self._lock:
            self._items = [f for f in self._items if f["id"] != fav_id]
            self._save()

    def import_many(self, items: Any) -> int:
        if not isinstance(items, list):
            return 0
        with self._lock:
            seen = {(f["name"], round(f["lat"], 6), round(f["lon"], 6)) for f in self._items}
            added = 0
            for raw in items:
                fav = clean_favorite({**raw, "id": None}) if isinstance(raw, dict) else None
                if not fav:
                    continue
                key = (fav["name"], round(fav["lat"], 6), round(fav["lon"], 6))
                if key not in seen:
                    seen.add(key)
                    self._items.append(fav)
                    added += 1
            if added:
                self._save()
        return added


class Settings:
    """User preferences kept in config.json (also holds the optional maptiler_key)."""

    DEFAULTS = {"history_enabled": True, "history_max": 20}
    HISTORY_SIZES = (10, 20, 50, 100)

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()

    def all(self) -> dict:
        data = read_json(self._path, {})
        return {k: data.get(k, v) for k, v in self.DEFAULTS.items()}

    def update(self, changes: Any) -> dict:
        if not isinstance(changes, dict):
            return self.all()
        with self._lock:
            data = read_json(self._path, {})
            if "history_enabled" in changes:
                data["history_enabled"] = bool(changes["history_enabled"])
            if changes.get("history_max") in self.HISTORY_SIZES:
                data["history_max"] = int(changes["history_max"])
            write_json(self._path, data)
        return self.all()


class History:
    """Recently visited places (newest first), skipping points closer than MIN_GAP_M.

    Recording can be paused and the size limit changed from the UI (see Settings)."""

    MIN_GAP_M = 25.0

    def __init__(self, path: Path, settings: Settings):
        self._path = path
        self._settings = settings
        self._lock = threading.Lock()
        loaded = [h for h in read_json(path, []) if isinstance(h, dict) and "lat" in h and "lon" in h]
        self._items = [{**h, "id": str(h.get("id") or uuid.uuid4().hex[:12]), "t": int(h.get("t") or 0)} for h in loaded]
        self._items = self._items[: self._settings.all()["history_max"]]
        if any("id" not in h for h in loaded):
            self._save()  # give v1 entries stable ids so they can be deleted one by one

    def _save(self) -> None:
        try:
            write_json(self._path, self._items)
        except OSError:
            pass

    def all(self) -> list[dict]:
        with self._lock:
            return list(self._items)

    def push(self, lat: float, lon: float) -> None:
        cfg = self._settings.all()
        if not cfg["history_enabled"]:
            return
        with self._lock:
            if self._items and distance_m(self._items[0]["lat"], self._items[0]["lon"], lat, lon) < self.MIN_GAP_M:
                return
            self._items.insert(0, {"id": uuid.uuid4().hex[:12], "lat": lat, "lon": lon, "t": int(time.time())})
            del self._items[cfg["history_max"]:]
            self._save()

    def delete(self, entry_id: str) -> None:
        with self._lock:
            self._items = [h for h in self._items if h["id"] != entry_id]
            self._save()

    def clear(self) -> None:
        with self._lock:
            self._items = []
            self._save()

    def trim(self) -> None:
        """Apply a smaller size limit right away."""
        with self._lock:
            del self._items[self._settings.all()["history_max"]:]
            self._save()
