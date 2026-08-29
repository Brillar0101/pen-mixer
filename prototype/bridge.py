#!/usr/bin/env python3
"""Pen Mixer bridge: USB serial -> smoothing -> UDP to Pure Data.

Reads "tilt,roll,energy" frames from the board, smooths them, maps them to
audio parameters, and sends them to Pd as FUDI messages (plain text over UDP,
so Pd needs no OSC externals).

    python3 bridge.py               # autodetect the serial port
    python3 bridge.py --port /dev/tty.usbmodem14201
    python3 bridge.py --quiet       # no console meter
"""

import argparse
import glob
import math
import os
import re
import select
import socket
import subprocess
import sys
import time

try:
    import serial            # optional; a raw fallback is used if absent
except ImportError:
    serial = None

# CircuitPython prints an ANSI terminal-title sequence on boot, which lands in
# the middle of the first data frame.  Strip all escapes, not just that one.
ANSI = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-9;]*[A-Za-z]")

PD_ADDR = ("127.0.0.1", 9999)
BAUD = 115200

try:
    import dashboard
except ImportError:
    dashboard = None


def find_port():
    for pattern in ("/dev/cu.usbmodem*", "/dev/ttyACM*", "/dev/cu.usbserial*"):
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[0]
    return None


class RawSerial:
    """Minimal line reader so the bridge runs with no third-party packages.

    pyserial is nicer and cross-platform, but on macOS and Linux reading the
    tty directly is enough and removes the only install step.
    """

    def __init__(self, port, baud):
        subprocess.run(["stty", "-f", port, str(baud), "raw", "-echo"],
                       check=False, capture_output=True)
        self.fd = os.open(port, os.O_RDONLY | os.O_NONBLOCK)
        self.buf = b""

    def readline(self):
        while b"\n" not in self.buf:
            r, _, _ = select.select([self.fd], [], [], 1.0)
            if not r:
                return b""
            try:
                chunk = os.read(self.fd, 4096)
            except BlockingIOError:
                return b""
            if not chunk:
                return b""
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        return line

    def close(self):
        os.close(self.fd)


class Smooth:
    """One-pole exponential smoother.

    Raw sensor values fed straight into a filter cutoff produce clicks and
    zipper noise.  This is the single most important few lines in the file.
    """

    def __init__(self, alpha=0.4):
        self.alpha = alpha
        self.y = None

    def __call__(self, x):
        self.y = x if self.y is None else self.y + self.alpha * (x - self.y)
        return self.y


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def linexp(v, in_lo, in_hi, out_lo, out_hi):
    """Linear input -> exponential output. Pitch and frequency are perceived
    logarithmically, so a linear cutoff sweep sounds wrong."""
    f = clamp((v - in_lo) / (in_hi - in_lo), 0.0, 1.0)
    return out_lo * math.pow(out_hi / out_lo, f)


def linlin(v, in_lo, in_hi, out_lo, out_hi):
    f = clamp((v - in_lo) / (in_hi - in_lo), 0.0, 1.0)
    return out_lo + f * (out_hi - out_lo)


def meter(label, value, lo, hi, width=22):
    f = clamp((value - lo) / (hi - lo), 0.0, 1.0)
    filled = int(f * width)
    return "%-7s [%s%s]" % (label, "#" * filled, "-" * (width - filled))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=None, help="serial device")
    ap.add_argument("--alpha", type=float, default=0.4,
                    help="smoothing 0.05 (heavy/laggy) .. 1.0 (raw/clicky). "
                         "Measured at 250 Hz: 0.05=236ms, 0.15=76ms, 0.4=24ms, "
                         "0.5=20ms to settle. Budget is ~15ms end to end.")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--web", type=int, default=8080,
                    help="port for the live dashboard, 0 to disable")
    args = ap.parse_args()

    if dashboard and args.web:
        dashboard.serve(args.web)
        print("dashboard: http://localhost:%d" % args.web)

    port = args.port or find_port()
    if not port:
        sys.exit("No serial port found. Plug the board in, or pass --port.")

    try:
        ser = serial.Serial(port, BAUD, timeout=1) if serial else RawSerial(port, BAUD)
    except Exception as e:
        sys.exit("Could not open %s: %s" % (port, e))

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s_tilt, s_roll, s_energy = (Smooth(args.alpha) for _ in range(3))

    print("bridge: %s (%s) -> udp %s:%d   (ctrl-c to stop)" % (
        port, "pyserial" if serial else "raw", PD_ADDR[0], PD_ADDR[1]))
    frames = 0
    last_print = 0.0
    bad = 0
    t_start = time.monotonic()

    try:
        while True:
            raw = ser.readline().decode("utf-8", "ignore")
            raw = ANSI.sub("", raw).strip()
            if not raw:
                continue
            parts = raw.split(",")
            if len(parts) != 3:
                bad += 1
                continue
            try:
                tilt, roll, energy = (float(p) for p in parts)
            except ValueError:
                bad += 1
                continue

            tilt = s_tilt(tilt)
            roll = s_roll(roll)
            energy = s_energy(energy)

            # --- the mapping.  This is the part worth arguing about. ---
            cutoff = linexp(tilt, -45.0, 45.0, 80.0, 12000.0)   # tilt  -> filter
            gain = linlin(roll, -90.0, 90.0, 0.25, 1.75)        # twist -> level
            wet = linlin(energy, 0.0, 1.0, 0.0, 1.0)            # speed -> send

            for name, val in (("cutoff", cutoff), ("gain", gain), ("wet", wet)):
                sock.sendto(("%s %.4f;\n" % (name, val)).encode(), PD_ADDR)

            frames += 1
            now = time.monotonic()

            if dashboard:
                dashboard.publish(tilt=tilt, roll=roll, energy=energy,
                                  cutoff=cutoff, gain=gain, wet=wet,
                                  fps=int(frames / max(0.001, now - t_start)),
                                  bad=bad, mode="touch")
            if not args.quiet and now - last_print > 0.05:
                last_print = now
                sys.stdout.write("\r%s  %s   %5d fps  %d bad " % (
                    meter("cutoff", cutoff, 80, 12000),
                    meter("gain", gain, 0.25, 1.75),
                    frames, bad))
                sys.stdout.flush()
    except KeyboardInterrupt:
        print("\nstopped after %d frames (%d malformed)" % (frames, bad))
    finally:
        ser.close()


if __name__ == "__main__":
    main()
