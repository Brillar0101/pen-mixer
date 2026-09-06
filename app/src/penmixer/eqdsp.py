"""Three-band EQ built from RBJ cookbook biquads (low shelf, peaking, high shelf).

Pure DSP: no Qt, no audio device code, so this module runs and tests
anywhere, including inside the Docker test container.
"""

from dataclasses import dataclass

import numpy as np
from scipy.signal import lfilter

# Band edges follow the PRD (M1-M3): bass 60-250 Hz, mid 250 Hz-2 kHz,
# treble 2-20 kHz. Low shelf corner at 250 covers the bass band, the peaking
# filter sits at the mid band's geometric center, the high shelf covers 2 kHz up.
BASS_HZ = 250.0
MID_HZ = 700.0
TREBLE_HZ = 2000.0
MID_Q = 0.7
SHELF_SLOPE = 0.9


@dataclass(frozen=True)
class Biquad:
    b: tuple[float, float, float]
    a: tuple[float, float, float]


def _shelf_terms(gain_db: float, freq_hz: float, rate: float) -> tuple[float, float, float, float]:
    amp = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * freq_hz / rate
    alpha = np.sin(w0) / 2.0 * np.sqrt((amp + 1.0 / amp) * (1.0 / SHELF_SLOPE - 1.0) + 2.0)
    return amp, w0, np.cos(w0), alpha


def design_low_shelf(gain_db: float, freq_hz: float, rate: float) -> Biquad:
    amp, _, cos_w0, alpha = _shelf_terms(gain_db, freq_hz, rate)
    sq = 2.0 * np.sqrt(amp) * alpha
    b0 = amp * ((amp + 1) - (amp - 1) * cos_w0 + sq)
    b1 = 2 * amp * ((amp - 1) - (amp + 1) * cos_w0)
    b2 = amp * ((amp + 1) - (amp - 1) * cos_w0 - sq)
    a0 = (amp + 1) + (amp - 1) * cos_w0 + sq
    a1 = -2 * ((amp - 1) + (amp + 1) * cos_w0)
    a2 = (amp + 1) + (amp - 1) * cos_w0 - sq
    return Biquad(b=(b0 / a0, b1 / a0, b2 / a0), a=(1.0, a1 / a0, a2 / a0))


def design_high_shelf(gain_db: float, freq_hz: float, rate: float) -> Biquad:
    amp, _, cos_w0, alpha = _shelf_terms(gain_db, freq_hz, rate)
    sq = 2.0 * np.sqrt(amp) * alpha
    b0 = amp * ((amp + 1) + (amp - 1) * cos_w0 + sq)
    b1 = -2 * amp * ((amp - 1) + (amp + 1) * cos_w0)
    b2 = amp * ((amp + 1) + (amp - 1) * cos_w0 - sq)
    a0 = (amp + 1) - (amp - 1) * cos_w0 + sq
    a1 = 2 * ((amp - 1) - (amp + 1) * cos_w0)
    a2 = (amp + 1) - (amp - 1) * cos_w0 - sq
    return Biquad(b=(b0 / a0, b1 / a0, b2 / a0), a=(1.0, a1 / a0, a2 / a0))


def design_peaking(gain_db: float, freq_hz: float, rate: float, q: float = MID_Q) -> Biquad:
    amp = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * freq_hz / rate
    alpha = np.sin(w0) / (2.0 * q)
    b0 = 1 + alpha * amp
    b1 = -2 * np.cos(w0)
    b2 = 1 - alpha * amp
    a0 = 1 + alpha / amp
    a1 = -2 * np.cos(w0)
    a2 = 1 - alpha / amp
    return Biquad(b=(b0 / a0, b1 / a0, b2 / a0), a=(1.0, a1 / a0, a2 / a0))


class ThreeBandEq:
    """Stateful stereo 3-band EQ. Gains change between blocks, state persists."""

    def __init__(self, rate: float, channels: int = 2) -> None:
        self._rate = rate
        self._channels = channels
        self._gains = (0.0, 0.0, 0.0)
        self._filters = self._design(self._gains)
        self._state = [
            [np.zeros(2) for _ in range(3)] for _ in range(channels)
        ]

    def _design(self, gains: tuple[float, float, float]) -> list[Biquad]:
        bass, mid, treble = gains
        return [
            design_low_shelf(bass, BASS_HZ, self._rate),
            design_peaking(mid, MID_HZ, self._rate),
            design_high_shelf(treble, TREBLE_HZ, self._rate),
        ]

    def set_gains(self, bass_db: float, mid_db: float, treble_db: float) -> None:
        gains = (bass_db, mid_db, treble_db)
        if any(abs(a - b) > 0.01 for a, b in zip(gains, self._gains)):
            self._gains = gains
            self._filters = self._design(gains)

    @property
    def gains(self) -> tuple[float, float, float]:
        return self._gains

    def process(self, block: np.ndarray) -> np.ndarray:
        """Filter one (frames, channels) float32 block; returns a new array."""
        out = np.empty_like(block)
        for ch in range(min(self._channels, block.shape[1])):
            signal = block[:, ch].astype(np.float64)
            for i, biq in enumerate(self._filters):
                signal, self._state[ch][i] = lfilter(
                    biq.b, biq.a, signal, zi=self._state[ch][i]
                )
            out[:, ch] = np.clip(signal, -1.0, 1.0).astype(block.dtype)
        return out
