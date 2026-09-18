"""FFT analysis for the visualizer: band levels and log-spaced spectrum bars.

Pure numpy, no Qt, so it tests in the Docker container. Band edges follow
the PRD (M1-M3): bass below 250 Hz, mid 250 Hz to 2 kHz, treble above.
"""

import numpy as np

BASS_EDGE_HZ = 250.0
TREBLE_EDGE_HZ = 2000.0
WINDOW_SAMPLES = 4096  # 11.7 Hz per bin at 48 kHz, so the bass bars resolve
FLOOR_DB = -70.0


def _magnitudes(mono: np.ndarray, rate: float) -> tuple[np.ndarray, np.ndarray]:
    window = np.hanning(len(mono))
    spectrum = np.abs(np.fft.rfft(mono * window)) / (len(mono) / 2)
    freqs = np.fft.rfftfreq(len(mono), d=1.0 / rate)
    return freqs, spectrum


def _to_unit(power: float) -> float:
    """Map a linear magnitude to 0..1 through a dB scale with a floor."""
    db = 20.0 * np.log10(max(power, 1e-9))
    return float(min(max((db - FLOOR_DB) / -FLOOR_DB, 0.0), 1.0))


def band_levels(mono: np.ndarray, rate: float) -> tuple[float, float, float]:
    """RMS-ish level of bass, mid, treble as 0..1 values."""
    if len(mono) < 32:
        return (0.0, 0.0, 0.0)
    freqs, spectrum = _magnitudes(mono, rate)
    bass = spectrum[freqs < BASS_EDGE_HZ]
    mid = spectrum[(freqs >= BASS_EDGE_HZ) & (freqs < TREBLE_EDGE_HZ)]
    treble = spectrum[freqs >= TREBLE_EDGE_HZ]
    return tuple(
        _to_unit(float(np.sqrt(np.mean(band**2)))) if len(band) else 0.0
        for band in (bass, mid, treble)
    )


def bar_spectrum(
    mono: np.ndarray,
    rate: float,
    bars: int = 32,
    fmin: float = 50.0,
    fmax: float = 16000.0,
) -> np.ndarray:
    """Log-spaced spectrum bars as 0..1 values, cava-style."""
    if len(mono) < 32:
        return np.zeros(bars)
    freqs, spectrum = _magnitudes(mono, rate)
    edges = np.geomspace(fmin, min(fmax, rate / 2), bars + 1)
    levels = np.zeros(bars)
    for i in range(bars):
        mask = (freqs >= edges[i]) & (freqs < edges[i + 1])
        if mask.any():
            levels[i] = _to_unit(float(np.sqrt(np.mean(spectrum[mask] ** 2))))
        else:
            # Low bars on a log scale can be narrower than one FFT bin, and an
            # empty mask would leave them dark forever. Read the nearest bin.
            center = np.sqrt(edges[i] * edges[i + 1])
            nearest = int(np.argmin(np.abs(freqs - center)))
            levels[i] = _to_unit(float(spectrum[nearest]))
    return levels


def bar_frequencies(bars: int = 32, fmin: float = 50.0, fmax: float = 16000.0) -> np.ndarray:
    """Center frequency of each bar, for coloring bars by band."""
    edges = np.geomspace(fmin, fmax, bars + 1)
    return np.sqrt(edges[:-1] * edges[1:])
