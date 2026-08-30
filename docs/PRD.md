# Product requirements document

Requirements for the Mixer Pen, taken from the client brief and the academic
rubric. Each one is marked with where it stands: **v1** means it works today,
**v2** means it is planned for the second version. Nothing here is quietly
dropped; if v1 misses a requirement, the table says so.

## Functional requirements

| # | Requirement | Status |
|---|---|---|
| F1 | Some form of feedback | **v1.** Two kinds: the audio itself changes live, and the dashboard at localhost:8080 shows tilt and twist as you move. |
| F2 | Manipulate sound and get better at it | **v1.** Continuous control with 24 ms smoothing, so small hand improvements are audible. |
| F3 | Gesture rewards practice | **v1.** The mapping is deterministic and repeatable; a practiced gesture lands the same filter sweep every time. |
| F4 | Bluetooth link to the laptop, controlling the audio player | **v1.** BLE (Nordic UART) to bridge.py, which drives Pure Data over UDP. |

## Pen direction mapping

The brief asks for a three-band EQ mapped to pen motion. v1 ships a simpler
mapping (tilt sweeps one filter, twist moves gain) that proves the pipeline.
The full three-band mapping is v2 work in firmware and the Pure Data patch;
no hardware change is needed, the IMU already measures all three axes.

| # | Requirement | Status |
|---|---|---|
| M1 | Bass 60-250 Hz on vertical motion (y), like writing an "l" | **v2.** |
| M2 | Mids 250 Hz-2 kHz on horizontal motion (x), like crossing a "t"; left cuts, right boosts | **v2.** |
| M3 | Treble 2-20 kHz on orientation, upright (90&deg;) as base; leaning toward 0&deg; adds brightness | **v2.** Closest to today's tilt-sweeps-filter behavior. |

## Physical requirements

| # | Requirement | Status |
|---|---|---|
| P1 | At most 30 mm in both directions | **v2.** The v1 board is 11 x 42 mm; the USB-C connector and the antenna keep-out stretched it. v2 shrinks it by dropping USB-C for charge pads or folding the layout. |
| P2 | Clear casing | **v2.** No enclosure exists yet. Planned as a clear resin or polycarbonate shell over the board and battery. |
| P3 | Weight at most 1 oz (28 g) | **v1 by design.** Board plus battery is roughly 5 g. Stays met with any reasonable casing; final weight gets measured in v2 with the shell on. |
| P4 | Runs 3 hours at once | **v1 by design.** The 100 mAh cell against a ~6 mA average BLE draw estimates well past 3 h. Estimated, not yet measured; a soak test is on the v2 checklist. |
| P5 | Attaches to the top of a pen, semi-universal, ~3 mm of adjustment | **v2.** v1 mounts with a hose clamp for bench testing. v2 gets a sprung or rubber-lined clip sized for a mechanical pencil, a number 2 pencil, and a Bic. |
| P6 | On and off with one hand, rubber for grip | **v2.** Part of the same clip design as P5. |
| P7 | Position near the top, on top or beside it | **v1.** The mount already targets the top of the pen; the mapping does not care which side. |

## Open questions from the brief

| # | Question | Answer |
|---|---|---|
| Q1 | Can we include an NFC chip? | **v2, and cheaply.** The nRF52840 inside the ISP1807 has an NFC-A tag peripheral built in; the module exposes the NFC1/NFC2 pins. v2 adds only a small antenna coil and a tuning capacitor. |
| Q2 | Song requests over NFC, e.g. pass a YouTube link to the chip | **v2.** The tag can carry an NDEF record with a URL that a phone tap reads, and the laptop bridge can rewrite it over BLE. Fetching audio from YouTube itself stays on the laptop side and depends on the source being licensed. |

## What v2 is, in one list

Three-band EQ mapping (M1-M3), the 30 mm board (P1), the clear casing (P2),
the one-handed adjustable clip (P5, P6), the NFC antenna and song-request
flow (Q1, Q2), and measured numbers for weight and battery life (P3, P4).
