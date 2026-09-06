# Flash kit

Everything needed to flash a fresh XIAO nRF52840 Sense:

- `circuitpython-xiao-sense.uf2`: double-tap reset, then drag onto the
  XIAO-SENSE drive that appears.
- `code.py` and `lib/`: copy both onto the CIRCUITPY drive that mounts
  after the uf2 installs. This `code.py` is the BLE variant
  (`../firmware/code_ble.py`); swap in `../firmware/code.py` for USB
  serial instead.
