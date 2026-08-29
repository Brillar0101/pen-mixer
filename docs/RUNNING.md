# Running Pen Mixer

Everything runs from `prototype/` against a Seeed XIAO nRF52840 Sense (the
same code targets the production board unchanged).

## Prerequisites

- Python 3 on the laptop. The only dependency is `bleak`, and only for BLE
  mode: `pip install bleak`.
- Pure Data (`brew install --cask purr-data` or vanilla Pd from puredata.info).
- Firmware on the board: copy `prototype/firmware/code.py` (USB serial) or
  `prototype/firmware/code_ble.py` (BLE, advertises as `PenMixer`) onto the
  CIRCUITPY drive.

## Start the bridge

```sh
python3 prototype/bridge.py            # USB serial, auto-detects the port
python3 prototype/bridge.py --ble      # BLE instead of the cable
```

Useful flags: `--port /dev/tty...` to pin the serial device, `--alpha 0.4`
to change smoothing, `--web 8080` for the dashboard port, `--quiet` to
silence per-frame logging.

## Start the audio

1. Open one of the patches in `prototype/patches/`:
   - `pen-mixer-track.pd` — plays an audio file and applies filter + gain
   - `pen-mixer-live.pd` — processes live audio input
   - `pen-mixer-manual.pd` — sliders only, no sensor needed (sanity check)
2. Turn on DSP (Media → DSP On, or the toggle in the patch).
3. Audio files are gitignored; generate a test tone with
   `python3 prototype/make_test_tone.py` or load your own file.

## See it move

- Dashboard: open `localhost:8080` — live tilt/twist visualization.
- Tilt the pen: the filter sweeps. Twist it: the level moves.

## Troubleshooting

- No sound: DSP is off, or the patch did not load a file. Try the manual
  patch first to confirm the audio path.
- No data: check the CIRCUITPY drive mounted and the right firmware file is
  named `code.py`; for BLE, confirm the board advertises as `PenMixer`.
- Jumpy response: raise smoothing with `--alpha 0.3` (lower = smoother).
