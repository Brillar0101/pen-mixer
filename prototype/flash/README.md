# Flashing the pen board

Everything needed to take a Seeed XIAO nRF52840 Sense from blank to
streaming pen motion. The steps are the same on macOS and Windows: the
board shows up as a plain USB drive (Finder on macOS, File Explorer on
Windows) and flashing is copying files onto it. This folder holds:

- `circuitpython-xiao-sense.uf2`: the CircuitPython runtime for the board
- `code.py`: the BLE firmware, ready to copy (a copy of
  `../firmware/code_ble.py`)
- `lib/`: the libraries the firmware imports

## Fresh board, or reinstalling CircuitPython

1. Plug the board in over USB-C. Use a known data cable; a charge-only
   cable is the classic reason nothing shows up.
2. Double-tap the small reset button beside the USB connector, two quick
   presses like a double-click. A drive named `XIAO-SENSE` appears in
   Finder or File Explorer.
3. Drag `circuitpython-xiao-sense.uf2` onto that drive. The board reboots
   by itself and the drive comes back as `CIRCUITPY`.
4. Copy `code.py` and the whole `lib/` folder onto `CIRCUITPY`. Wait for
   the copy to finish, then eject the drive (macOS: drag to the eject
   icon; Windows: "Safely Remove Hardware") before unplugging.

The firmware starts the moment the copy lands. This `code.py` is the BLE
build: the board advertises as `PenMixer-Lexy`, and the app's Scan Bluetooth
button or a green "Pen board connected" banner confirms it is alive.

## Updating the firmware only

CircuitPython is already on the board, so skip the uf2: plug in, wait for
`CIRCUITPY` to mount, and replace `code.py` on the drive. The board
restarts the code automatically on every save.

## Choosing USB serial instead of Bluetooth

CircuitPython runs whatever file is named `code.py` on the drive. For the
wired build, copy `../firmware/code.py` onto `CIRCUITPY` instead; for
Bluetooth, use this folder's `code.py` (which is `../firmware/code_ble.py`).
The laptop side is the same either way, only the Source setting changes.

## Renaming the board

The advertised name is one line in the firmware, `ble.name = "PenMixer-Lexy"`.
Change it before copying, and change the matching name on the laptop side
(`DEVICE_NAME` in `app/src/penmixer/bleio.py`, and `ble_source.py` for the
prototype bridge). macOS caches Bluetooth names, so the old one can linger
in scans for a while after a rename.

## If something looks wrong

- No `XIAO-SENSE` drive after the double-tap: retime the two presses, and
  swap in a data cable.
- Board runs but no motion: open a serial console to read the error.
  macOS: `screen /dev/cu.usbmodem* 115200`. Windows: find the COM port in
  Device Manager, then PuTTY at 115200 baud, or
  `py -m serial.tools.miniterm COM5 115200` if pyserial is installed.
  Also check that `lib/` actually copied over; missing libraries fail on
  the first import.
- BLE build not found in a scan: a connected board stops advertising, so
  disconnect the app first, or power-cycle the pen.
