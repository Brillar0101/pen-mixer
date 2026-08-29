#!/usr/bin/env python3
"""Generate test-tone.wav - a sawtooth chord for testing the filter.

Deliberately harmonic-rich: a lowpass sweep on a pure tone is nearly
inaudible, but on a saw chord it is dramatic.  Run once after cloning.

    python3 make_test_tone.py
"""
import math
import os
import struct
import wave

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "patches", "test-tone.wav")

SR, DUR = 44100, 30.0
FREQS = [110.00, 164.81, 220.00, 261.63, 329.63]   # Am7, voiced low


def saw(ph):
    return 2.0 * (ph - math.floor(ph + 0.5))


n = int(SR * DUR)
phases = [0.0] * len(FREQS)
inc = [f / SR for f in FREQS]
frames = bytearray()

for i in range(n):
    t = i / SR
    env = 0.5 + 0.5 * math.sin(2 * math.pi * 0.07 * t)
    l = r = 0.0
    for k in range(len(FREQS)):
        phases[k] += inc[k]
        s = saw(phases[k])
        pan = k / (len(FREQS) - 1)
        l += s * (1.0 - pan * 0.6)
        r += s * (0.4 + pan * 0.6)
    g = 0.11 * (0.6 + 0.4 * env)
    fade = min(1.0, t / 0.5, (DUR - t) / 0.5)
    frames += struct.pack("<hh",
                          int(max(-1, min(1, l * g * fade)) * 32767),
                          int(max(-1, min(1, r * g * fade)) * 32767))

with wave.open(OUT, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(bytes(frames))
print("wrote", OUT)
