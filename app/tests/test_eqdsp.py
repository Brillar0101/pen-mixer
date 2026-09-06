import numpy as np
import pytest

from penmixer.eqdsp import ThreeBandEq

RATE = 48000.0


def sine(freq: float, seconds: float = 0.5) -> np.ndarray:
    t = np.arange(int(RATE * seconds)) / RATE
    mono = 0.25 * np.sin(2 * np.pi * freq * t)
    return np.stack([mono, mono], axis=1).astype(np.float32)


def rms(block: np.ndarray) -> float:
    tail = block[len(block) // 2 :]  # skip filter warm-up
    return float(np.sqrt(np.mean(tail**2)))


def test_flat_gains_pass_signal_through() -> None:
    eq = ThreeBandEq(rate=RATE)
    signal = sine(440.0)
    out = eq.process(signal)
    assert rms(out) == pytest.approx(rms(signal), rel=0.02)


def test_bass_boost_raises_low_frequencies() -> None:
    eq = ThreeBandEq(rate=RATE)
    eq.set_gains(12.0, 0.0, 0.0)
    boosted = rms(eq.process(sine(100.0)))
    flat = rms(sine(100.0))
    gain_db = 20 * np.log10(boosted / flat)
    assert gain_db > 9.0


def test_bass_boost_leaves_treble_alone() -> None:
    eq = ThreeBandEq(rate=RATE)
    eq.set_gains(12.0, 0.0, 0.0)
    out = rms(eq.process(sine(8000.0)))
    assert 20 * np.log10(out / rms(sine(8000.0))) < 1.0


def test_treble_boost_raises_high_frequencies() -> None:
    eq = ThreeBandEq(rate=RATE)
    eq.set_gains(0.0, 0.0, 12.0)
    gain_db = 20 * np.log10(rms(eq.process(sine(8000.0))) / rms(sine(8000.0)))
    assert gain_db > 9.0


def test_mid_boost_raises_700() -> None:
    eq = ThreeBandEq(rate=RATE)
    eq.set_gains(0.0, 12.0, 0.0)
    gain_db = 20 * np.log10(rms(eq.process(sine(700.0))) / rms(sine(700.0)))
    assert gain_db > 9.0


def test_process_returns_new_array() -> None:
    eq = ThreeBandEq(rate=RATE)
    signal = sine(440.0)
    out = eq.process(signal)
    assert out is not signal
