# PyInstaller build file.   Build with:   pyinstaller GPS_Simulador.spec
# Debug build with a console window:  set GPS_DEBUG_CONSOLE=1 before building.
# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all, copy_metadata

datas = [("gpsapp/web", "gpsapp/web")]
binaries = []
hiddenimports = []

# pymobiledevice3 loads many modules (and its tunnel/network stack) dynamically.
for pkg in ("pymobiledevice3", "pmd_pytcp", "pytun_pmd3", "pyimg4", "qh3", "uvicorn", "webview"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
datas += copy_metadata("pymobiledevice3", recursive=True)

a = Analysis(
    ["GPS_App.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GPS_Simulador",
    console=os.environ.get("GPS_DEBUG_CONSOLE") == "1",  # normally no terminal; logs go to %APPDATA%\iOS-GPS-Simulator\app.log
    upx=False,              # UPX-packed executables trigger far more antivirus false positives
    uac_admin=False,        # admin is only needed for iOS 17.0-17.3; the app can relaunch itself
)
