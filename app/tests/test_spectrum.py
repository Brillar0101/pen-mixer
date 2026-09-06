from itertools import pairwise

import numpy as np

from penmixer.spectrum import band_levels, bar_frequencies, bar_spectrum

RATE = 48000.0


def sine(freq: float, samples: int = 2048) -> np.ndarray:
    t = np.arange(samples) / RATE
    return 0.5 * np.sin(2 * np.pi * freq * t)


def test_bass_tone_lands_in_bass_band() -> None:
    bass, mid, treble = band_levels(sine(100.0), RATE)
    assert bass > mid and bass > treble


def test_treble_tone_lands_in_treble_band() -> None:
    bass, mid, treble = band_levels(sine(8000.0), RATE)
    assert treble > bass and treble > mid


def test_silence_is_near_zero() -> None:
    levels = band_levels(np.zeros(2048), RATE)
    assert all(v < 0.05 for v in levels)


def test_bar_spectrum_shape_and_range() -> None:
    bars = bar_spectrum(sine(1000.0), RATE)
    assert bars.shape == (32,)
    assert float(bars.max()) <= 1.0
    assert float(bars.min()) >= 0.0


def test_bar_frequencies_ascend() -> None:
    freqs = bar_frequencies()
    assert all(a < b for a, b in pairwise(freqs))
