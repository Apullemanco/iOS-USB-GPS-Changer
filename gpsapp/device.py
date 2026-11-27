"""iPhone/iPad connection: tunnel, Developer Mode, disk image and location push.

Connection strategy (pymobiledevice3 11.x):
  * iOS 17.4+  -> in-process userspace tunnel (no administrator rights needed)
  * iOS 17.0-17.3 -> pymobiledevice3 "tunneld" (needs administrator / root)
  * iOS <= 16  -> plain lockdown (no tunnel) - experimental

Everything device-related runs on ONE asyncio loop in ONE background thread,
because pymobiledevice3 objects are bound to the loop that created them.
"""

import asyncio
import contextlib
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

from pymobiledevice3 import usbmux
from pymobiledevice3.exceptions import (
    AlreadyMountedError,
    ConnectionFailedToUsbmuxdError,
    NoDeviceConnectedError,
    PairingDialogResponsePendingError,
    PasswordRequiredError,
    UserDeniedPairingError,
    UserspaceTunnelUnavailableError,
)
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.amfi import AmfiService
from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation
from pymobiledevice3.services.mobile_image_mounter import auto_mount

from .platform_utils import is_admin
from .simulator import Simulator

log = logging.getLogger(__name__)

TUNNELD_ADDRESS = ("127.0.0.1", 49151)
KEEPALIVE_S = 5.0      # re-send the position even if unchanged
PUSH_INTERVAL_S = 0.2  # max rate we push positions to the device
RETRY_S = 2.0


class DeviceError(Exception):
    """An expected problem the UI explains to the user (code -> translated message)."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code)
        self.code, self.detail = code, detail


@dataclass
class DeviceStatus:
    phase: str = "idle"         # idle | connecting | tunnel | mounting | active | error
    connected: bool = False     # a device is visible over USB
    name: str = ""
    ios: str = ""
    error: Optional[dict] = field(default=None)


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split(".")[:3] if p.isdigit())


def classify_error(exc: BaseException) -> DeviceError:
    if isinstance(exc, DeviceError):
        return exc
    if isinstance(exc, ConnectionFailedToUsbmuxdError):
        return DeviceError("no_usbmuxd")
    if isinstance(exc, NoDeviceConnectedError):
        return DeviceError("no_device")
    if isinstance(exc, PairingDialogResponsePendingError):
        return DeviceError("trust_pending")
    if isinstance(exc, UserDeniedPairingError):
        return DeviceError("trust_denied")
    if isinstance(exc, PasswordRequiredError):
        return DeviceError("locked")
    text = f"{type(exc).__name__}: {exc}"
    if "DeveloperMode" in text:
        return DeviceError("dev_mode_off")
    return DeviceError("unknown", text[:300])


class DeviceManager:
    def __init__(self, sim: Simulator):
        self.sim = sim
        self._status = DeviceStatus()
        self._status_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._tunneld_started = False

    # ---------- public (thread-safe) ----------
    def status(self) -> dict:
        with self._status_lock:
            return asdict(self._status)

    def start(self) -> None:
        self._thread = threading.Thread(target=lambda: asyncio.run(self._main()), name="device", daemon=True)
        self._thread.start()

    def shutdown(self, timeout: float = 4.0) -> None:
        """Stop spoofing (restores the real GPS) and wait for the device thread."""
        self.sim.set_enabled(False)
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)

    # ---------- internals ----------
    def _set(self, **kw) -> None:
        with self._status_lock:
            for k, v in kw.items():
                setattr(self._status, k, v)

    async def _main(self) -> None:
        while not self._stop.is_set():
            if not self.sim.enabled:
                await self._probe()
                await self._sleep(RETRY_S)
                continue
            try:
                await self._session()
                self._set(phase="idle", error=None)
            except Exception as exc:  # noqa: BLE001 - every failure is reported to the UI
                err = classify_error(exc)
                if err.code == "unknown":
                    log.exception("Device session failed")
                self._set(phase="error", error={"code": err.code, "detail": err.detail})
                await self._sleep(RETRY_S)

    async def _sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end and not self._stop.is_set():
            await asyncio.sleep(0.1)

    async def _probe(self) -> None:
        """Cheap idle check: is any device plugged in? (no pairing, no tunnel)"""
        try:
            devices = [d for d in await usbmux.list_devices() if d.is_usb]
            if not devices:
                self._set(connected=False, name="", ios="")
            err = None
        except Exception as exc:  # noqa: BLE001
            devices, err = [], classify_error(exc)
        self._set(connected=bool(devices),
                  phase="idle" if err is None else "error",
                  error=None if err is None else {"code": err.code, "detail": err.detail})

    async def _session(self) -> None:
        async with contextlib.AsyncExitStack() as stack:
            self._set(phase="connecting", error=None)
            lockdown = await create_using_usbmux(autopair=True, connection_type="USB")
            stack.push_async_callback(lockdown.close)
            ios = lockdown.product_version
            self._set(connected=True, ios=ios, name=lockdown.all_values.get("DeviceName") or lockdown.display_name or "iPhone")
            version = _version_tuple(ios)

            if version >= (16,) and not await lockdown.get_developer_mode_status():
                with contextlib.suppress(Exception):  # makes the toggle visible in Settings
                    await AmfiService(lockdown).reveal_developer_mode_option_in_ui()
                raise DeviceError("dev_mode_off")

            provider = lockdown
            if version >= (17,):
                self._set(phase="tunnel")
                provider = await self._open_tunnel(stack, lockdown.udid)

            location = await self._open_location(stack, provider)
            await self._push_loop(location)

    async def _open_tunnel(self, stack: contextlib.AsyncExitStack, udid: str):
        from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel

        try:
            tunnel = UserspaceRsdTunnel(serial=udid, remotepairing_fallback=False)
            rsd = await tunnel.aopen()
            stack.push_async_callback(tunnel.aclose)
            return rsd
        except UserspaceTunnelUnavailableError:
            pass  # iOS 17.0-17.3: no CoreDeviceProxy, needs the privileged tunneld

        if not is_admin():
            raise DeviceError("needs_admin")
        self._ensure_tunneld()
        from pymobiledevice3.tunneld.api import get_tunneld_device_by_udid

        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not self._stop.is_set():
            with contextlib.suppress(Exception):
                rsd = await get_tunneld_device_by_udid(udid, TUNNELD_ADDRESS)
                if rsd:
                    stack.push_async_callback(rsd.close)
                    return rsd
            await asyncio.sleep(1)
        raise DeviceError("tunnel_failed")

    def _ensure_tunneld(self) -> None:
        if self._tunneld_started:
            return
        self._tunneld_started = True

        def run() -> None:
            from pymobiledevice3.tunneld.server import TunneldRunner
            try:
                TunneldRunner.create(*TUNNELD_ADDRESS, wifi_monitor=False, mobdev2_monitor=False)
            except (Exception, SystemExit):  # noqa: BLE001 - e.g. another tunneld already owns the port
                log.warning("tunneld could not start (an existing one will be used if running)", exc_info=True)

        threading.Thread(target=run, name="tunneld", daemon=True).start()

    async def _open_location(self, stack: contextlib.AsyncExitStack, provider) -> LocationSimulation:
        async def open_once() -> LocationSimulation:
            dvt = await stack.enter_async_context(DvtProvider(provider))
            return await stack.enter_async_context(LocationSimulation(dvt))

        try:
            return await open_once()
        except Exception:  # noqa: BLE001 - usually "service not found" until the image is mounted
            log.info("Developer services unavailable, mounting the Developer Disk Image")
        self._set(phase="mounting")
        try:
            await auto_mount(provider)
        except AlreadyMountedError:
            pass
        except Exception as exc:  # noqa: BLE001
            raise DeviceError("mount_failed", str(exc)[:300]) from exc
        return await open_once()

    async def _push_loop(self, location: LocationSimulation) -> None:
        last_version, last_sent = -1, 0.0
        try:
            while self.sim.enabled and not self._stop.is_set():
                lat, lon, version = self.sim.position()
                now = time.monotonic()
                if version != last_version or now - last_sent >= KEEPALIVE_S:
                    await location.set(lat, lon)
                    last_version, last_sent = version, now
                    self._set(phase="active", error=None)
                await asyncio.sleep(PUSH_INTERVAL_S)
        finally:
            # Restore the real GPS whenever we leave (Stop pressed, app closing, cable pulled...).
            with contextlib.suppress(Exception):
                await asyncio.wait_for(location.clear(), timeout=3)
