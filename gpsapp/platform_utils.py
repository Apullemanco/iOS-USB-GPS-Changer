"""OS-specific helpers. Everything degrades gracefully outside Windows."""

import ctypes
import logging
import os
import sys
import threading
from typing import Callable

log = logging.getLogger(__name__)
IS_WINDOWS = sys.platform == "win32"


def is_admin() -> bool:
    try:
        if IS_WINDOWS:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        return os.geteuid() == 0
    except Exception:  # noqa: BLE001
        return False


def relaunch_as_admin() -> bool:
    """Windows: restart this program through the UAC prompt. Returns False if refused."""
    if not IS_WINDOWS:
        return False
    if getattr(sys, "frozen", False):
        exe, params = sys.executable, ""
    else:
        exe, params = sys.executable, f'"{os.path.abspath(sys.argv[0])}"'
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    return rc > 32


def show_error(message: str, title: str = "Simulador GPS · iOS GPS Simulator") -> None:
    if IS_WINDOWS:
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    else:
        print(f"{title}: {message}", file=sys.stderr)


# ---------- global hotkeys (work while the window is not focused) ----------
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
WM_HOTKEY = 0x0312
HOTKEYS = {  # id: (modifiers, virtual key, action)
    1: (MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, 0x50, "pause"),    # Ctrl+Alt+P
    2: (MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, 0x52, "restore"),  # Ctrl+Alt+R
    3: (MOD_CONTROL | MOD_ALT, 0x26, "n"),                       # Ctrl+Alt+Up
    4: (MOD_CONTROL | MOD_ALT, 0x28, "s"),                       # Ctrl+Alt+Down
    5: (MOD_CONTROL | MOD_ALT, 0x25, "w"),                       # Ctrl+Alt+Left
    6: (MOD_CONTROL | MOD_ALT, 0x27, "e"),                       # Ctrl+Alt+Right
}


def start_global_hotkeys(handler: Callable[[str], None]) -> None:
    """Register Ctrl+Alt shortcuts via the Win32 API (no extra dependencies)."""
    if not IS_WINDOWS:
        return

    def loop() -> None:
        import ctypes.wintypes as wt
        user32 = ctypes.windll.user32
        for hk_id, (mods, vk, _) in HOTKEYS.items():
            if not user32.RegisterHotKey(None, hk_id, mods, vk):
                log.warning("Hotkey %s is already used by another program", hk_id)
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam in HOTKEYS:
                try:
                    handler(HOTKEYS[msg.wParam][2])
                except Exception:  # noqa: BLE001
                    log.exception("Hotkey handler failed")

    threading.Thread(target=loop, name="hotkeys", daemon=True).start()
