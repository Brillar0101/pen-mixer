# Pen Mixer prototype board

The full-prototype rig: a Seeed XIAO nRF52840 Sense riding on an ordinary
pen, running the firmware in `../prototype/firmware/` unchanged. No custom
PCB. This is the build for working sessions before (or instead of) fabbing
the production board.

## Bill of materials

Core, about $26 if starting from nothing:

| Item | Part | Qty | Cost |
|---|---|---|---|
| Motion board | Seeed XIAO nRF52840 Sense | 1 | $16 |
| Pen | any ballpoint, thicker barrel | 1 | $2 |
| USB-C cable | data-capable, not charge-only | 1 | $8 |

Wireless additions, about $8 (sourced from Adafruit, chosen for minimum
bulk on the pen):

| Item | Part | Qty | Cost |
|---|---|---|---|
| LiPo cell | Adafruit 1570, 3.7 V 100 mAh, JST-PH, protected, 11.5 x 31 x 3.8 mm, 3 g | 1 | $5.95 |
| Battery pigtail | Adafruit 1131, JST-PH extension cable; cut the plug end, solder to BAT pads | 1 | $1.95 |

There is no power switch: unplugging the cell from the pigtail is the off
switch. The switched breakout (Adafruit 1863) was rejected as too tall for
the pen, and the inline switched cable (Adafruit 3064) was out of stock.
100 mAh clears the PRD's 3 hour target on the measured ~6 mA average BLE
draw. The 401230 bare cell in the production BOM is for the custom board
only; the prototype wants a protected JST-PH cell, since the XIAO's charger
is the only battery management in the loop.

## Battery wiring

The XIAO powers itself from the cell and charges it over USB. Cut the plug
end off the extension cable and solder its wires to the two BAT pads on the
underside; the cell then clicks into the socket end, unmodified:

    cell -> JST socket ... red  -> BAT+
                           black -> BAT-

- Polarity is unforgiving; check twice before soldering.
- Cut the cable one wire at a time so the bare leads never touch.
- BAT pads only, never the 3V3 pin; 3V3 bypasses the regulator.
- Unplugging the cell is the power switch; the XIAO has none of its own.
- Trim the cable short; 500 mm is far more than a pen needs.
- Charging is 50 mA from the onboard BQ25101, fine for a 100 mAh cell.

Battery operation is proven (BLE streaming at ~67 fps on the cell); runtime
against the PRD's 3 hour target is not yet measured. Rerun
`../prototype/tools/battery_soak.py` with USB unplugged until the cell runs
down; it writes the verdict to `measurements/battery-soak.md`.

## Mounting rules

- Nothing conductive against the back of the board: the castellated pads and
  BAT pads are exposed, and bare metal across them shorts it.
- Keep metal away from the USB-C end; the antenna is there, and metal beside
  it kills BLE range.
- Leave the BAT pads uncovered if the cell might come later.
- USB-C port faces the back of the pen so the cable runs away from the hand.

## What it does

| Gesture | Drives |
|---|---|
| Tilt forward/back | Filter cutoff, 80 Hz to 12 kHz |
| Twist the barrel | Low-shelf gain, +/-15 dB |
| Scribble fast/slow | Reverb or delay send |
| Tap the pen down | Freeze / unfreeze |

X/Y position on the page is out of scope: it needs an optical sensor held at
a fixed height and angle to the paper, which is the hard mechanical problem.

## Software

Flashing, from a blank board up: [../prototype/flash/README.md](../prototype/flash/README.md).
Running the stack, bridge to dashboard: [RUNNING.md](RUNNING.md).
The desktop app lives in `../app/`.
