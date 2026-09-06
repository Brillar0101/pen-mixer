"""Bluetooth LE reader for the nRF52840 pen board.

The board advertises as "PenMixer" with a Nordic UART service and notifies
the same "tilt,roll,energy" lines the USB path produces. This reader scans,
connects, and reconnects on its own, emitting the same signals as the
serial reader so the rest of the app does not care where frames come from.
"""

import asyncio
import re

from PySide6.QtCore import QThread, Signal

from .frames import parse_line

DEVICE_NAME = "PenMixer"
NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
ANSI = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-9;]*[A-Za-z]")


class BleReader(QThread):
    frame_received = Signal(object)
    status_changed = Signal(str)
    connected_changed = Signal(bool)

    def __init__(self, name: str = DEVICE_NAME) -> None:
        super().__init__()
        self._name = name
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        try:
            asyncio.run(self._main())
        except Exception as exc:  # noqa: BLE001 - surfaced on the banner, not swallowed
            self.connected_changed.emit(False)
            self.status_changed.emit(f"Bluetooth error: {exc}")

    async def _main(self) -> None:
        try:
            from bleak import BleakClient, BleakScanner
        except ImportError:
            self.connected_changed.emit(False)
            self.status_changed.emit("Bluetooth needs bleak: pip install bleak")
            return

        while not self._stop:
            self.connected_changed.emit(False)
            self.status_changed.emit(f'scanning for "{self._name}" over Bluetooth...')
            device = await BleakScanner.find_device_by_name(self._name, timeout=10.0)
            if self._stop:
                return
            if device is None:
                self.status_changed.emit(
                    f'pen board "{self._name}" not found (is code_ble.py running?)'
                )
                await asyncio.sleep(2.0)
                continue

            buffer = ""

            def handle(_: object, data: bytearray) -> None:
                nonlocal buffer
                buffer += data.decode("utf-8", "ignore")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    frame = parse_line(ANSI.sub("", line))
                    if frame is not None:
                        self.frame_received.emit(frame)

            try:
                async with BleakClient(device) as client:
                    await client.start_notify(NUS_TX, handle)
                    self.connected_changed.emit(True)
                    self.status_changed.emit(f"pen board connected over Bluetooth ({device.address})")
                    while client.is_connected and not self._stop:
                        await asyncio.sleep(0.2)
            except Exception as exc:  # noqa: BLE001 - reconnect loop handles radio errors
                self.status_changed.emit(f"Bluetooth link dropped: {exc}")
            if not self._stop:
                self.connected_changed.emit(False)
                self.status_changed.emit("pen board disconnected, rescanning...")
                await asyncio.sleep(1.0)
