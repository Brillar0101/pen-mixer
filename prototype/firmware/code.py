# code_touch.py - XIAO RP2040 : real hand input via capacitive touch
#
# The RP2040 has no IMU, but its pins can sense a finger. Touch A0 and A1
# (or wires soldered/taped to them) and the values move. This is a real
# hand-driven control, today, with no extra parts.
#
# Emits the same "tilt,roll,energy" frame format as code.py, so the bridge
# and Pd patches need no changes at all.

import time
import math

import board

USE_TOUCH = True
try:
    import touchio
    t0_pin = touchio.TouchIn(board.A0)
    t1_pin = touchio.TouchIn(board.A1)
except Exception:
    USE_TOUCH = False
    import analogio
    t0_pin = analogio.AnalogIn(board.A0)
    t1_pin = analogio.AnalogIn(board.A1)


def raw(pin):
    return pin.raw_value if USE_TOUCH else pin.value


# Establish a baseline so we report change, not absolute capacitance.
time.sleep(0.3)
base0 = sum(raw(t0_pin) for _ in range(40)) / 40.0
base1 = sum(raw(t1_pin) for _ in range(40)) / 40.0
SPAN = 900.0 if USE_TOUCH else 12000.0

print("# touch mode" if USE_TOUCH else "# analog mode")

prev0 = 0.0
t_start = time.monotonic()

while True:
    d0 = (raw(t0_pin) - base0) / SPAN          # 0..1-ish when touched
    d1 = (raw(t1_pin) - base1) / SPAN

    d0 = max(0.0, min(1.0, d0))
    d1 = max(0.0, min(1.0, d1))

    tilt = -45.0 + d0 * 90.0                   # A0 -> filter cutoff
    roll = -90.0 + d1 * 180.0                  # A1 -> gain
    energy = min(1.0, abs(d0 - prev0) * 25.0)  # rate of change -> send
    prev0 = d0

    print("%.2f,%.2f,%.3f" % (tilt, roll, energy))
    time.sleep(0.006)
