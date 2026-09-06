# Pen Mixer EQ (Qt)

Move a pen, shape the music. This app turns motion from the Pen Mixer board
into a live three-band EQ over whatever the computer is playing: tilt the
pen and the bass swells, roll it and the treble lifts, do both and the mids
come up. A spectrum visualizer and waveform show the sound changing in real
time.

This README explains the whole project from zero: where it came from, how
every piece works, how to run it, and every problem we hit along the way so
you do not have to rediscover them.

## Quick start

Everything below assumes the pen board is already flashed (see
`prototype/flash/README.md`) and advertising as "PenMixer-Lexy".

### macOS

First time only:

```bash
brew install blackhole-2ch switchaudio-osx
git clone https://github.com/Brillar0101/pen-mixer.git
cd pen-mixer/app
python3 -m venv venv
venv/bin/pip install -r requirements.txt -e .
```

Every time:

```bash
cd pen-mixer/app
venv/bin/python -m penmixer.app
```

In the window: click "Route system audio here" (music now flows through the
app), set Source to "Bluetooth (pen board)" or click "Scan Bluetooth" and
pick PenMixer-Lexy, play music, move the pen. Allow the Bluetooth permission
prompt the first time. Closing the app hands your speakers back.

### Windows

First time only (VB-CABLE is the Windows loopback; details in "Running it
on Windows" below):

```powershell
# administrator PowerShell, then reboot
curl.exe -L -o $env:TEMP\vbcable.zip https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack45.zip
Expand-Archive $env:TEMP\vbcable.zip $env:TEMP\vbcable -Force
& $env:TEMP\vbcable\VBCABLE_Setup_x64.exe
shutdown /r /t 0
```

```powershell
# normal PowerShell, after the reboot
git clone https://github.com/Brillar0101/pen-mixer.git
cd pen-mixer\app
python -m venv venv
venv\Scripts\pip install -r requirements.txt -e .
```

Every time:

```powershell
cd pen-mixer\app
venv\Scripts\python -m penmixer.app
```

Set Windows Settings > System > Sound > Output to "CABLE Input", then in the
window click "Hear music here", set Source to "Bluetooth (pen board)" or use
"Scan Bluetooth", play music, move the pen. Set the Windows output back to
your speakers when you are done.

### No board handy

Set Source to "Simulate (no board)": synthetic pen motion sweeps all three
bands so the whole pipeline demos untethered.

## Where this fits in the bigger project

The parent project is the Pen Mixer: a tiny board (nRF52840 + IMU) that clips
onto a pen and turns handwriting gestures into audio control over Bluetooth.
That hardware lives in this repo (`production/` for the board,
`prototype/firmware/` for the firmware), and its product requirements call
for a three-band EQ mapped to pen motion (bass 60-250 Hz, mid 250 Hz-2 kHz,
treble 2-20 kHz).

During prototyping the board is a Seeed XIAO nRF52840 Sense running the same
firmware. This directory is the laptop side: one Qt app that replaced the
previous three-piece stack (a serial bridge script, a browser dashboard, and
Pure Data patches) with a single window that owns everything. That was a
deliberate requirement: the Qt interface is the only source of truth. Serial
reading, audio processing, and the UI all live in this one process, so what
you see is always what is actually happening.

## How it works, end to end

Follow one pen move through the system:

1. The board runs `code.py` (CircuitPython, in `../prototype/firmware/`).
   Its 6-axis IMU reads tilt and roll from gravity, so 0.0 means the pen is
   level and the ends of the range mean a full lean.

2. Every ~6 ms the firmware prints one line over USB serial:
   `tilt,roll,energy`. Tilt spans -45 to +45 degrees, roll -90 to +90, and
   energy 0 to 1 for overall motion. The BLE firmware emits the same frame
   format over the air, which is the point: everything downstream works
   unchanged whichever link carries it.

3. `serialio.py` runs a Qt thread that auto-discovers the board's port
   (`/dev/cu.usbmodem*`), parses frames (`frames.py`), and reconnects by
   itself if the board is unplugged. A banner at the top of the window shows
   the board state at all times: red "Pen board not detected", green
   "Pen board connected on <port>", amber "simulated input". The banner is
   separate from the audio status line so the two never overwrite each other.

4. `mapping.py` converts a frame to gains, deliberately simple and
   deterministic: tilt scales a bass boost from 0 to +12 dB, roll the same
   for treble, and the mids follow the weaker of the two, so moving both
   ways at once raises the middle. At rest always means flat, 0 dB; the
   music is unchanged until the pen moves. A one-pole smoother tuned to
   ~24 ms (the PRD's F2 figure) keeps the motion glide-smooth.

5. The gains drive three RBJ biquad filters in `eqdsp.py`: a low shelf at
   250 Hz, a peaking filter at 700 Hz (the geometric center of the PRD's mid
   band), and a high shelf at 2 kHz. Filter state persists across blocks;
   coefficients are recomputed only when a gain actually changes, and the
   audio callback ramps toward targets so there are never clicks.

6. `audio.py` owns a duplex sounddevice stream: it reads the system's music
   from the BlackHole loopback device, runs it through the EQ, and writes it
   to the real speakers or headphones. It also applies -9 dB of input
   headroom, because BlackHole delivers system audio hotter than full scale
   (we measured peaks of 1.6) and a +12 dB boost on top of that would clip.

7. `spectrum.py` runs numpy's rfft over the last 2048 output samples and
   produces both three band levels and 32 log-spaced bars (50 Hz to 16 kHz,
   dB scale). `viz.py` draws them cava-style, colored by band, with the raw
   waveform drawn behind. The bars analyze the processed signal, the same
   samples going to your ears, so what you see is real: boost the bass and
   the blue bars rise because the audio itself changed. Only the motion
   styling (fast rise, smooth decay, held peak caps) is cosmetic.

8. `ui.py` is the single source of truth: the window owns the reader, the
   engine, and the gain state. Motion drives the sliders and the sliders
   drive the DSP; untick "Pen control" and you can drag the sliders by
   hand (including cuts). Live meters show the raw tilt and roll input as
   it moves.

## Why BlackHole, and how the routing works

macOS gives no direct way to process another app's audio. The standard
answer is a loopback device: BlackHole 2ch is a virtual audio device that
acts like a cable. Route the system's output into it, and whatever any app
plays lands there as an input this app can read. The chain during a session:

```
YouTube/Spotify -> BlackHole 2ch -> this app (EQ + visualizer) -> speakers
```

Doing that by hand means fiddling with Sound settings, so the app does it
with one click. The "Route system audio here" button (using the
SwitchAudioSource CLI) switches the system output to BlackHole, selects your
real speakers or headphones as the app's output, and starts the engine
immediately, so the music never goes silent, it just changes path. Stopping
the audio or closing the app restores the previous output automatically.
BlackHole itself is excluded from the output choices because selecting it
would create a silent loop.

## Running it

Prerequisites on macOS: `brew install blackhole-2ch` for the loopback and
optionally `brew install switchaudio-osx` for the one-click routing button.

```bash
git clone https://github.com/Brillar0101/pen-mixer.git
cd pen-mixer/app
python3 -m venv venv
venv/bin/pip install -r requirements.txt -e .
venv/bin/python -m penmixer.app
```

Then, in the window:

1. Click "Route system audio here" and play music anywhere
2. Waves and spectrum bars move; you hear the music through the app
3. Set Source to "Bluetooth (pen board)", or click "Scan Bluetooth" and pick
   PenMixer-Lexy; the banner turns green when connected
4. Tilt for bass, sway sideways for mids, twist for treble; each gesture
   boosts one way and cuts the other, and the pen at rest leaves the music flat

No board? Set Source to "Simulate (no board)" and synthetic motion sweeps
the controls so the whole pipeline demos untethered.

## Running it on Windows

The app is cross-platform Python; only the loopback device and the routing
button differ from macOS.

1. Install Python 3.11+ from python.org (tick "Add python.exe to PATH").
   If `python` opens the Microsoft Store instead of running, use `py` in the
   commands below, or reinstall with the PATH box ticked.
2. Install the loopback device: VB-Audio Virtual Cable, the Windows
   equivalent of BlackHole. In an administrator PowerShell (right-click
   Start > Terminal (Admin)):

```powershell
curl.exe -L -o $env:TEMP\vbcable.zip https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack45.zip
Expand-Archive $env:TEMP\vbcable.zip $env:TEMP\vbcable -Force
& $env:TEMP\vbcable\VBCABLE_Setup_x64.exe    # click "Install Driver"
shutdown /r /t 0                              # reboot is mandatory
```

   If the download URL fails, get it from vb-audio.com/Cable instead:
   extract, right-click `VBCABLE_Setup_x64.exe`, Run as administrator,
   Install Driver, reboot. After the reboot, verify the cable exists:

```powershell
venv\Scripts\python -c "import sounddevice; print(sounddevice.query_devices())"
```

   The list must show "CABLE Input (VB-Audio Virtual Cable)" and "CABLE
   Output (VB-Audio Virtual Cable)". No CABLE devices means the install or
   the reboot did not happen. If they are in the list but not in the app,
   click the app's Rescan button.
3. Clone and set up (run from the project root, and keep the trailing dot
   on the install command; it means "this folder" and installs the app):

```powershell
git clone https://github.com/Brillar0101/pen-mixer.git
cd pen-mixer\app
python -m venv venv
venv\Scripts\pip install -r requirements.txt -e .
venv\Scripts\python -m penmixer.app
```

4. Route the audio by hand (the route button is macOS-only, it uses a
   macOS tool): Settings > System > Sound > Output > "CABLE Input
   (VB-Audio Virtual Cable)". Then click "Hear music here" in the app: it
   selects CABLE Output as input, your speakers as output, and starts the
   audio, trying several sample rates until the stream opens. The music
   becomes audible through the app, with the EQ live on it.
5. Plug in the board. Windows names serial ports COM3-style and the app
   accepts any COM port that reports a USB vendor id, so detection works
   the same; the banner turns green.

Remember to switch the system output back to your speakers when done;
on Windows the app cannot restore it for you.

Do not use "Stereo Mix" as the input even though it looks like a loopback:
it taps the same speakers this app plays into, so the app would hear its
own output and feed back on itself, and many Realtek drivers mix the
microphone into it as well.

## Installing Docker

Docker is optional: the app runs natively without it. It gives you the
reproducible test suite anywhere, and the containerized app path.

macOS:

```bash
brew install --cask docker    # or download Docker Desktop from docker.com
open -a Docker                # first start; wait for the whale icon
docker --version              # verify
```

Windows: install Docker Desktop from docker.com/products/docker-desktop.
It requires the WSL2 backend; the installer sets it up (or run
`wsl --install` in an elevated PowerShell first, then reboot). Verify with
`docker --version` in PowerShell. The `docker compose run --rm test` suite
works identically; the containerized GUI app path is documented for macOS
and untested on Windows (WSLg can display it, but the audio and serial
bridges are macOS scripts).

Linux: `curl -fsSL https://get.docker.com | sh`, then log out and in after
adding yourself to the docker group (`sudo usermod -aG docker $USER`).

## The nRF52840 pen board over Bluetooth

The app talks to the pen board directly: set the Source dropdown to
"Bluetooth (pen board)" or click "Scan Bluetooth" to pick it from a list of
everything in range. The board runs the firmware in `prototype/flash`
(flash kit with CircuitPython, libraries and `code.py`); it advertises as
"PenMixer-Lexy" with a Nordic UART service. The app scans, connects, and
reconnects on its own; the banner reports every state. On macOS the first
scan pops a Bluetooth permission prompt for the terminal or Python; allow
it or the scan finds nothing.

The mapping is signed around the pen at rest, so holding still is flat
(0 dB) and every band moves both ways:

| Gesture | Band | Direction |
|---------|------|-----------|
| Tilt forward / back | Bass 60-250 Hz | forward boosts to +12 dB, back cuts to -12 dB |
| Sway left / right (horizontal stroke) | Mid 250 Hz-2 kHz | right boosts, left cuts (PRD M2) |
| Twist | Treble 2-20 kHz | one way boosts, the other cuts |

Sway comes from the firmware as a fourth frame value: a leaky integral of
the gyro rate about the sweep axis, so a stroke builds the value and
holding still lets it drift back to center. Older three-field firmware still
works; sway simply reads zero. If the "Sway (mid)" meter reacts to the
wrong gesture for how the board sits on the pen, change `SWAY_AXIS` in the
firmware (0, 1 or 2) and copy `code.py` back onto CIRCUITPY.

## Tests and Docker

Every module without Qt or hardware dependencies (frames, mapping, eqdsp,
spectrum) has a pytest suite: parsing and clamping, the mapping rules, the
measured filter response (a +12 dB bass boost must raise a 100 Hz tone by
more than 9 dB while moving an 8 kHz tone by less than 1 dB), and FFT band
assignment. Run natively:

```bash
venv/bin/python -m pytest
venv/bin/ruff check src tests
```

Or in Docker, which needs no audio, no USB, and no macOS:

```bash
docker compose run --rm test
```

The app itself can also run inside Docker (`docker compose up --build app`),
which on macOS needs three host bridges because containers cannot reach the
display, CoreAudio, or USB: XQuartz for the window, PulseAudio for sound,
and a socat serial-to-TCP forward. `scripts/host_bridges.sh` sets those up.
It works, but the network audio hops add latency, so for a live music demo
run natively and treat the containerized app as the portability proof.

## Requirements traceability

The PRD lives in this repo (`../docs/PRD.md`). Where this app stands:

| Req | Requirement | This rig |
|-----|-------------|----------|
| F1  | Some form of feedback | Met: live audio change, spectrum bars, dB readouts, pad meters |
| F2  | Continuous control, 24 ms smoothing | Met: smoothing tuned to ~24 ms plus a click-free gain ramp |
| F3  | Deterministic, repeatable mapping | Met: pure function of frame values; same gesture, same sound |
| F4  | Bluetooth link to the laptop | Met: BLE to the nRF52840 board, with USB serial as the wired fallback |
| M1  | Bass 60-250 Hz | Met: tilt drives the bass band |
| M2  | Mid 250 Hz-2 kHz, left cuts / right boosts | Partial: the USB path boosts only; over Bluetooth the gains are signed so cuts work, and the mids stay slider-only until the firmware streams a third axis |
| M3  | Treble 2-20 kHz | Met: roll drives the treble band |
| P1-P7, Q1-Q2, I1-I3 | Physical, NFC, interface | Out of scope: board hardware, not this laptop rig |

## Problems we hit, so you do not have to

Real issues from building and demoing this, with their fixes:

- "No module named penmixer" when launching: the package lives under `src/`
  and must be installed into the venv (`pip install -e .`). The tests passed
  anyway because pytest adds the path itself, which hid the problem.
- Silent app, music still audible: the system output was never routed to
  BlackHole, so the app was analyzing silence while the browser played to
  the speakers. The app now detects two seconds of silent input while
  running and says exactly what to fix in the status line.
- Silent everything after routing: the system output was left on BlackHole
  by an earlier session and the route button's "already routed" branch did
  nothing. It now recovers: picks real speakers, starts the engine, and
  remembers a restore target so closing the app never strands the system
  on BlackHole.
- Routed, engine running, still silent: the music itself had stopped, or
  the browser tab was still bound to the old audio device. Reloading the
  tab and pressing play fixes it; browsers follow the default device but
  sometimes only after a reload.
- Distortion risk on boosts: BlackHole delivers hotter-than-full-scale
  audio, so the engine takes -9 dB of input headroom before the EQ.
- Bluetooth headphones add latency, so the EQ response trails the pen motion
  slightly; wired output feels snappier for a live demo.
- Charge-only USB-C cables are the classic reason the board banner stays
  red with the board plugged in. Bring a known data cable.

## Repo layout

```
src/penmixer/
  frames.py     parse "tilt,roll,energy" serial frames
  mapping.py    motion -> band gains, deterministic, PRD-tuned smoothing
  eqdsp.py      RBJ biquads, stateful 3-band EQ      (no Qt: tested in Docker)
  spectrum.py   rfft band levels + log spectrum bars (no Qt: tested in Docker)
  audio.py      duplex stream, gain ramping, input headroom
  serialio.py   USB serial reader, auto-discovery, reconnect, board banner
  tcpio.py      same frames over TCP, for the Docker serial bridge
  routing.py    one-click system output switching via SwitchAudioSource
  viz.py        spectrum bars + waveform widget
  ui.py         main window: the single source of truth
  app.py        entry point
tests/          pytest suite for every no-Qt module
scripts/        host_bridges.sh for the Docker app path
```

## What comes next

The natural next steps, in rough order: signed mid control once the
firmware streams a third axis (closes M2), and profiles for different
mappings (which band each gesture drives, boost ranges, cut support).
