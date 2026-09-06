# Battery soak test

Status: NOT YET MEASURED. The first attempt (2026-09-06, XIAO nRF52840 Sense
on its cell, BLE streaming at ~65 fps) was cut short after 13 minutes when the
board was plugged back into USB, which ends the test and starts charging. That
run says nothing about battery life. Rerun with the board off USB for the
whole test:

    app/venv/bin/python prototype/tools/battery_soak.py

The script writes the runtime and the PRD P4 verdict (3 hours) here when the
cell runs down.
