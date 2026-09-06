"""Battery soak test (PRD P4): how long does the pen board stream on one charge?

Connects to the PenMixer board over Bluetooth, subscribes to the motion
stream, and logs until the board stops responding for RECONNECT_GRACE_S.
Prints one status line per minute and a final summary. Run with the board
OFF USB, fully charged, and within range of the laptop for the whole test.

    python prototype/tools/battery_soak.py [--out docs/measurements/battery-soak.md]
"""

import argparse
import asyncio
import datetime as dt
import time

from bleak import BleakClient, BleakScanner

NAME = "PenMixer"
NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
RECONNECT_GRACE_S = 180.0
REPORT_EVERY_S = 60.0


async def run(out_path: str) -> None:
    started = time.monotonic()
    started_wall = dt.datetime.now()
    frames = 0
    last_frame = time.monotonic()
    last_report = time.monotonic()
    disconnects = 0

    def on_frame(_: object, data: bytearray) -> None:
        nonlocal frames, last_frame
        frames += data.count(b"\n")
        last_frame = time.monotonic()

    print(f"soak start {started_wall:%Y-%m-%d %H:%M:%S}, waiting for {NAME}", flush=True)
    while True:
        device = await BleakScanner.find_device_by_name(NAME, timeout=15.0)
        if device is None:
            if frames and time.monotonic() - last_frame > RECONNECT_GRACE_S:
                break
            if not frames and time.monotonic() - started > RECONNECT_GRACE_S:
                print("board never appeared; is it on and charged?", flush=True)
                return
            continue
        try:
            async with BleakClient(device) as client:
                await client.start_notify(NUS_TX, on_frame)
                print("connected", flush=True)
                while client.is_connected:
                    await asyncio.sleep(1.0)
                    now = time.monotonic()
                    if now - last_report >= REPORT_EVERY_S:
                        elapsed = now - started
                        print(
                            f"{elapsed / 60:6.1f} min  {frames} frames  "
                            f"{frames / max(elapsed, 1):.0f} fps avg",
                            flush=True,
                        )
                        last_report = now
                    if now - last_frame > RECONNECT_GRACE_S:
                        break
        except Exception as exc:  # noqa: BLE001 - radio drop, reconnect loop
            print(f"link dropped: {exc}", flush=True)
        disconnects += 1
        if time.monotonic() - last_frame > RECONNECT_GRACE_S:
            break

    ended_wall = dt.datetime.now()
    runtime_s = last_frame - started
    hours = runtime_s / 3600
    verdict = "PASS (3 h requirement met)" if hours >= 3.0 else "FAIL (under 3 h)"
    summary = (
        f"# Battery soak test\n\n"
        f"- Board: Seeed XIAO nRF52840 Sense running prototype/flash/code.py (BLE, 100 Hz frames)\n"
        f"- Started: {started_wall:%Y-%m-%d %H:%M:%S}\n"
        f"- Last frame: {ended_wall - dt.timedelta(seconds=RECONNECT_GRACE_S):%Y-%m-%d %H:%M:%S}\n"
        f"- Runtime on one charge: {hours:.2f} h ({runtime_s / 60:.0f} min)\n"
        f"- Frames received: {frames} ({frames / max(runtime_s, 1):.0f} fps average)\n"
        f"- Reconnects during test: {disconnects - 1}\n"
        f"- PRD P4 (runs 3 hours at once): {verdict}\n"
    )
    print(summary, flush=True)
    with open(out_path, "w") as f:
        f.write(summary)
    print(f"RESULT written to {out_path}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/measurements/battery-soak.md")
    args = parser.parse_args()
    asyncio.run(run(args.out))
