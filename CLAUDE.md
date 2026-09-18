# Pen Mixer working rules

Settled decisions. Build on these; do not re-litigate.

## PCB (production/kicad/)

- **Route with freerouting, always.** Export Specctra DSN, run the jar, import the SES.
  Remove the copper zones before export and re-add them after import (freerouting
  mis-handles GND planes). Hand-drawn segments only when freerouting demonstrably
  cannot complete, and say so out loud when it happens.
- **No vias on or near copper pads.** Zero overlap tolerated; keep real clearance
  where density allows.
- **GND pours on all four layers**, thermal reliefs, antenna keep-out at the tip
  stays copper-free (pads exempt).
- **Official vendor/JLCPCB footprints and 3D models only** - fetch by LCSC number
  via easyeda2kicad. Never hand-draw symbols or footprints; the user supplies files
  when JLC has none.
- **Verify the netlist after every schematic edit** against reference-nets.json
  (kicad-cli netlist export, compare ref|pin -> net). "IDENTICAL" or it's broken.
- **Run DRC after every board edit.** Baseline: 0 unconnected, 0 errors; the 2
  TrueType text_thickness warnings on the board label are accepted.
- One editor at a time: quit KiCad before editing files on disk, reopen after.
- v1 is frozen: git tag v1 and production/kicad/v1/. v2 (13 x 35 mm, v2.1 board) is
  frozen: git tag v2 and production/kicad/v2/. Current board is v3, a regular five-point
  star 40 mm tip to tip with a vertical (top-entry) USB-C in the body; antenna tip at the top.

## Sourcing

- Production parts from JLCPCB/LCSC (exception: U1 ISP1807 from Mouser/DigiKey, 0 stock).
- Prototype parts from Amazon.
- Battery: 3.7 V LiPo, wires soldered to the two pads at the tip on the back; the
  cell lies along the back. No connector (height) and no holder.

## Style

- Commit subjects: 3-4 words, imperative, no conventional-commit prefixes.
- Docs are humanized: no em dashes, sentence-case headings, no bold-header bullets.
- BOM data lives in schematic symbol properties; bom/bom.csv is exported from KiCad.
