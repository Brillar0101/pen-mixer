# Pen Mixer

Strap a sensor to a pen. Tilt it and a filter sweeps across whatever track is
playing on the laptop. Twist it and the level moves.

This repo holds the whole project: prototype firmware, production firmware and
laptop stack, and the production PCB as a KiCad project.

```mermaid
flowchart LR
    HAND["Hand<br>tilt, twist"] --> FW

    subgraph pen["Pen Mixer board: on the pen"]
        FW["LSM6DSV16X IMU<br>+ ISP1807 nRF52840"]
    end

    FW -->|"BLE, Nordic UART"| BR
    FW -.->|"USB-C, serial"| BR

    subgraph laptop["Laptop"]
        BR["bridge.py<br>smooth, map"] -->|"UDP"| PD["Pure Data<br>filter + gain"]
        BR -->|"SSE"| DASH["dashboard<br>localhost:8080"]
    end

    PD --> SPK["Speakers"]

    classDef pfBlue fill:#E7F1FA,stroke:#0066CC,color:#151515
    classDef pfGold fill:#FDF7E7,stroke:#F0AB00,color:#151515
    classDef pfGreen fill:#F3FAF2,stroke:#3E8635,color:#151515
    classDef pfGray fill:#F0F0F0,stroke:#6A6E73,color:#151515
    class HAND,SPK pfBlue
    class FW pfGreen
    class BR pfGold
    class PD,DASH pfGray
```

## The hardware

The production board is a 12 x 30 mm, four-layer, 0.6 mm PCB, all SMD, designed
to ride on a pen barrel with a 401230 LiPo at the back of the pen.

| Ref | Part | Role |
|---|---|---|
| U1 | ISP1807 | nRF52840 with integrated antenna, pre-certified |
| U2 | LSM6DSV16X | 6-axis IMU with on-chip fusion |
| U3 | MCP73831 | LiPo charger, 50 mA |
| U4 | TPS7A02 | 3.3 V LDO, 200 nA quiescent |
| J1 | USB-C 16P | charge, programming, serial |
| J2 | pads on B.Cu | off-board LiPo, 401230 |

The KiCad project lives in `hardware/`. Schematic PDF, board plots, a render
and the BOM are in `hardware/output/`.

Two items block fabrication, deliberately:

1. **Routing.** 53 connections are unrouted. Power and ground come from the
   pours; what remains is USB as a differential pair, I2C, two interrupts, the
   analog pair and SWD. An evening in the interactive router.
2. **The ISP1807 land pattern is reconstructed**, not vendor-supplied. Pad
   numbering is read from the datasheet figure and is correct; the coordinates
   are derived from the dimensional drawing. On a 0.65 mm pitch 78-pad LGA,
   diff it against Insight SiP's official land pattern before paying for
   fabrication.

Every pinout came from a primary datasheet, kept in `hardware/datasheets/`.
The one that would have cost a board spin: ISP1807 pin 20 (OUT_ANT) must be
tied to pin 22 (OUT_MOD) on the application PCB, or the radio has no antenna.

## The firmware and laptop stack

`production/` runs on the Seeed XIAO nRF52840 Sense today and targets the
custom board unchanged, since both are an nRF52840 with an ST IMU on I2C.

```
production/
  bridge.py           serial or BLE, then smoothing, mapping, UDP, dashboard
  ble_source.py       laptop-side BLE client for --ble
  dashboard.py        live web view on :8080
  firmware/
    code.py           IMU over USB serial
    code_ble.py       IMU over BLE, advertises as PenMixer
  patches/            Pure Data: track playback, manual sliders, live input
```

Run it with `python3 production/bridge.py`, open
`production/patches/pen-mixer-track.pd`, turn on DSP. The dashboard is at
localhost:8080. The only dependency in the whole project is `bleak`, and only
for BLE mode.

## The prototype

`prototype/` is the same laptop stack driven from a XIAO RP2040 using
capacitive touch as a stand-in sensor. It exists because the whole chain was
built and tuned on it before any motion sensor arrived; moving to the product
build replaced one function. Kept for history and for bring-up of new laptops.

## Measured, not estimated

| What | Number |
|---|---|
| Frame rate over USB | 197 Hz against a 250 Hz target |
| Frames in the soak run | 105,872, 0 malformed |
| Smoother settling, alpha 0.4 | 24 ms to 95% of a step |
| End-to-end budget | 32 ms, against ~20 ms where feel degrades |
| BLE vs USB link cost | ~10 ms vs 1 ms |

## Layout

```
prototype/          RP2040 build: touch stand-in, same laptop stack
production/         nRF52840 build: real IMU, USB or BLE
hardware/           KiCad 10 project, 12 x 30 mm production board
  pen-mixer.pretty/ custom footprints, ISP1807 land pattern flagged above
  datasheets/       primary sources for every pinout
  output/           schematic PDF, board plots, render, BOM, DRC report
docs/               architecture page and printable PDF
ARCHITECTURE.md     how it all fits together, with diagrams
```

Audio files are gitignored; `python3 production/make_test_tone.py` generates a
test tone. Standalone repos for each build:
[pen-mixer-rp2040](https://github.com/Brillar0101/pen-mixer-rp2040),
[pen-mixer-nrf52840](https://github.com/Brillar0101/pen-mixer-nrf52840).
