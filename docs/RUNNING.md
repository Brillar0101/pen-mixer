# Running Pen Mixer

The laptop side is the Qt desktop app in `app/`: it EQs whatever the computer
is playing, driven by the pen over Bluetooth, with a live spectrum so you can
see the sound change. The board is a Seeed XIAO nRF52840 Sense (the same
firmware targets the production board unchanged), flashed once from
`prototype/flash/`; it advertises as `PenMixer-Lexy`.

## 1. Flash the board (once)

Copy `prototype/flash/code.py` and `prototype/flash/lib/` onto the board's
CIRCUITPY drive. Full steps from a blank board, for macOS and Windows, are in
[prototype/flash/README.md](../prototype/flash/README.md). Unplug the board
afterward and it runs on its battery.

## 2. Start the app on macOS

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

In the window:

1. Click "Route system audio here". The music now flows through the app and
   keeps playing; the waves and spectrum bars move.
2. Set Source to "Bluetooth (pen board)", or click "Scan Bluetooth" and pick
   `PenMixer-Lexy`. Allow the Bluetooth permission prompt the first time.
   The banner turns green when connected.
3. Play music and move the pen: tilt for bass, sway sideways for mids, twist
   for treble. Each gesture boosts one way and cuts the other; the pen at
   rest leaves the music flat.

Closing the app hands your speakers back automatically.

## 2. Start the app on Windows

First time only. VB-CABLE is the Windows loopback device (the BlackHole
equivalent). In an administrator PowerShell (right-click Start > Terminal
(Admin)), then reboot:

```powershell
curl.exe -L -o $env:TEMP\vbcable.zip https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack45.zip
Expand-Archive $env:TEMP\vbcable.zip $env:TEMP\vbcable -Force
& $env:TEMP\vbcable\VBCABLE_Setup_x64.exe    # click "Install Driver"
shutdown /r /t 0
```

After the reboot, in a normal PowerShell:

```powershell
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

In Windows: Settings > System > Sound > Output > "CABLE Input (VB-Audio
Virtual Cable)". In the window:

1. Click "Hear music here". The app picks "CABLE Output" as input and your
   speakers as output and starts the audio; music is audible again through
   the app.
2. Set Source to "Bluetooth (pen board)", or click "Scan Bluetooth" and pick
   `PenMixer-Lexy`. The banner turns green when connected.
3. Play music and move the pen, as on macOS.

When you are done, set the Windows output back to your speakers; on Windows
the app cannot restore it for you.

## No board handy

Set Source to "Simulate (no board)". Synthetic pen motion sweeps all three
bands so the whole pipeline demos untethered.

## Troubleshooting

- Waves do not move: the system output is not routed to the loopback device.
  On macOS click "Route system audio here"; on Windows set the output to
  "CABLE Input". The status line says "input is silent" after two seconds
  when this is the case.
- Routed but silent: the music itself stopped, or the browser tab is bound
  to the old audio device. Reload the tab and press play.
- Banner stays red on Bluetooth: the board is not advertising. Is it powered
  and running `code.py`? Is anything else (another laptop, the soak test)
  already connected to it? Only one central can hold the link.
- "CABLE Output" missing on Windows: the VB-CABLE install needs the reboot;
  after it, click Rescan in the app. Do not use "Stereo Mix" instead; it
  feeds the app's own output back into it.
- Sound seems muffled: raise the Volume slider (default +9 dB restores unity
  against the input headroom pad), and on Bluetooth headphones make sure
  nothing is using their microphone, which drops them to phone quality.
- "No module named penmixer": run `pip install -e .` from `app/`; the dot
  matters.

## Legacy: the bridge and Pure Data stack

Before the Qt app, the laptop side was `prototype/bridge.py` feeding Pure Data
patches over UDP with a browser dashboard on port 8080. It still runs:

```sh
pip install bleak
python3 prototype/bridge.py            # USB serial, auto-detects the port
python3 prototype/bridge.py --ble      # BLE instead of the cable
```

Then open a patch from `prototype/patches/` in Pure Data (`pen-mixer-track.pd`
plays a file, `pen-mixer-live.pd` processes live input, `pen-mixer-manual.pd`
is sliders only), turn DSP on, and open `localhost:8080` for the dashboard.
Flags: `--port` to pin the serial device, `--alpha` for smoothing, `--web`
for the dashboard port, `--quiet` to silence per-frame logging. The Qt app
replaces all of this in one window and is the recommended path.
