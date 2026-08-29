"""Bluetooth LE input for the Pen Mixer bridge.

The board runs code_ble.py and advertises a Nordic UART service. This connects
to it and yields the same "tilt,roll,energy" lines the USB path produces, so
the mapping, dashboard and Pd side are unchanged.

Requires:  python3 -m pip install bleak
"""

import asyncio
import re

DEVICE_NAME = "PenMixer"
# Nordic UART Service - TX is the characteristic the peripheral notifies on.
NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

ANSI = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-9;]*[A-Za-z]")


async def stream(on_line, name=DEVICE_NAME, timeout=15.0):
    """Connect and call on_line(str) for every complete frame received."""
    try:
        from bleak import BleakClient, BleakScanner
    except ImportError:
        raise SystemExit(
            "BLE mode needs bleak.  Install with:\n"
            "    python3 -m pip install bleak"
        )

    print("scanning for %r ..." % name)
    device = await BleakScanner.find_device_by_name(name, timeout=timeout)
    if device is None:
        raise SystemExit(
            "No device called %r found.\n"
            "  - is code_ble.py running on the board?\n"
            "  - is it still plugged into USB power?\n"
            "  - macOS needs Bluetooth permission for your terminal app" % name
        )

    print("connecting to %s ..." % device.address)
    buf = ""

    def handle(_, data: bytearray):
        nonlocal buf
        buf += data.decode("utf-8", "ignore")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = ANSI.sub("", line).strip()
            if line:
                on_line(line)

    async with BleakClient(device) as client:
        await client.start_notify(NUS_TX, handle)
        print("connected - streaming over BLE")
        while client.is_connected:
            await asyncio.sleep(0.5)
    print("BLE disconnected")


def run(on_line, name=DEVICE_NAME):
    asyncio.run(stream(on_line, name))
