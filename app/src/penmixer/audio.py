"""Live audio engine: reads the loopback input, applies the EQ, writes to output.

macOS routing for "EQ whatever is playing":
    System Settings -> Sound -> Output -> BlackHole 2ch
    In the app: input = BlackHole 2ch, output = your speakers/headphones.
Music from any app then flows through this engine and the EQ.
"""

import sys
import threading
from dataclasses import dataclass

import numpy as np
import sounddevice as sd

from .eqdsp import ThreeBandEq
from .mapping import MAX_BOOST_DB, BandGains
from .spectrum import WINDOW_SAMPLES

BLOCK_FRAMES = 256
RAMP_ALPHA = 0.35
# Room for the EQ to boost into. A band at +MAX_BOOST_DB adds exactly that
# many decibels to the peak, so the input is padded by the same amount and a
# full boost lands at full scale instead of past it. This is what makes a
# boost audible as more of that band rather than as distortion; the cost is
# that flat playback sits MAX_BOOST_DB below the source, which the volume
# knob is there to make up. Turning it up past the pad trades headroom back
# for loudness, and the soft limiter below catches what that costs.
HEADROOM = 10.0 ** (-MAX_BOOST_DB / 20.0)
# Ceiling the adaptive pad aims the boosted peak at, leaving the soft limiter
# a little to work with rather than riding exactly at full scale.
PAD_CEILING = 0.9
# Peak follower: jumps to a new peak at once, then falls with roughly a 3 s
# time constant, so the pad reacts to a loud passage immediately but does not
# chase every dip. Much slower than this and a quiet track stays padded for
# half a minute before the level comes up.
PEAK_RELEASE = 0.998
# Per-block move of the pad itself, about a 300 ms time constant at this
# block size. Slow enough not to pump, fast enough to catch a rising track.
PAD_SMOOTH = 0.02
# Level above which the output rounds off rather than squaring off. Below it
# the limiter is exactly unity, so normal playback is untouched.
SOFT_KNEE = 0.8


def _soft_limit(block: np.ndarray) -> np.ndarray:
    """Bend anything above the knee down towards 1.0 instead of clipping it.

    A hard clip replaces a curve with a corner, and a corner is broadband
    noise: that is what the crackling was. tanh keeps the result under 1.0
    without the corner.
    """
    magnitude = np.abs(block)
    over = magnitude > SOFT_KNEE
    if not over.any():
        return block
    out = block.copy()
    excess = (magnitude[over] - SOFT_KNEE) / (1.0 - SOFT_KNEE)
    out[over] = np.sign(block[over]) * (SOFT_KNEE + (1.0 - SOFT_KNEE) * np.tanh(excess))
    return out


@dataclass(frozen=True)
class DeviceInfo:
    index: int
    name: str
    inputs: int
    outputs: int
    hostapi: int


def rescan_devices() -> None:
    """Make PortAudio re-enumerate: picks up devices plugged in or installed
    after launch. Only safe while no stream is open."""
    sd._terminate()
    sd._initialize()


def list_devices() -> list[DeviceInfo]:
    devices = []
    for idx, dev in enumerate(sd.query_devices()):
        devices.append(
            DeviceInfo(
                index=idx,
                name=str(dev["name"]),
                inputs=int(dev["max_input_channels"]),
                outputs=int(dev["max_output_channels"]),
                hostapi=int(dev["hostapi"]),
            )
        )
    return devices


def hostapi_names() -> dict[int, str]:
    return {idx: str(api["name"]) for idx, api in enumerate(sd.query_hostapis())}


# Windows lists the same hardware once per host API. WASAPI is the one worth
# having: it runs at the endpoint's native rate (VB-Cable is 48 kHz, but its
# MME entry advertises 44.1 kHz and forces a resampled stream) and it is the
# only one that drives Bluetooth A2DP output reliably. MME is a legacy
# emulation layer that on this cable will not even open for render.
HOSTAPI_PREFERENCE = ("wasapi", "directsound", "mme") if sys.platform == "win32" else ()


def hostapi_rank(hostapi: int, names: dict[int, str] | None = None) -> int:
    """Lower is better. Everything unranked sorts last, order untouched."""
    if not HOSTAPI_PREFERENCE:
        return 0
    name = (names or hostapi_names()).get(hostapi, "").lower()
    for rank, wanted in enumerate(HOSTAPI_PREFERENCE):
        if wanted in name:
            return rank
    return len(HOSTAPI_PREFERENCE)


def _wasapi_duplex_settings(input_index: int, output_index: int):
    """Let WASAPI resample when the two devices sit at different rates.

    Shared mode refuses a duplex stream outright when the input and output
    have different native rates, which is the normal case here: VB-Cable runs
    at 48 kHz while a Bluetooth speaker reports 44.1 kHz, and no single rate
    satisfies both. auto_convert has the driver convert rather than fail.
    Only applied when both ends are WASAPI, since the settings object is
    rejected by the other host APIs.
    """
    names = hostapi_names()

    def is_wasapi(index: int) -> bool:
        hostapi = int(sd.query_devices(index)["hostapi"])
        return "wasapi" in names.get(hostapi, "").lower()

    if is_wasapi(input_index) and is_wasapi(output_index):
        settings = sd.WasapiSettings(auto_convert=True)
        return (settings, settings)
    return None


def default_input_index() -> int | None:
    """Prefer the loopback device so system audio is what gets EQ'd.

    BlackHole on macOS, VB-Audio Virtual Cable ("CABLE Output") on Windows.
    Among the duplicate host-API entries for one device, take the best-ranked.
    """
    names = hostapi_names()
    for hint in ("blackhole", "cable output"):
        matches = [d for d in list_devices() if hint in d.name.lower() and d.inputs >= 2]
        if matches:
            return min(matches, key=lambda d: hostapi_rank(d.hostapi, names)).index
    return None


class AudioEngine:
    """Owns the duplex stream and the EQ. Thread-safe gain updates."""

    def __init__(self) -> None:
        self._stream: sd.Stream | None = None
        self._eq: ThreeBandEq | None = None
        self._lock = threading.Lock()
        self._target = BandGains(0.0, 0.0, 0.0)
        self._current = (0.0, 0.0, 0.0)
        self._level = 0.0
        self._xruns = 0
        self._rate = 48000.0
        self._viz = np.zeros(WINDOW_SAMPLES, dtype=np.float32)
        self._makeup = 1.0  # unity: the pad stays as headroom until the user spends it
        self._peak = 1.0  # start padded, relax once the real level is known
        self._pad = HEADROOM

    @property
    def running(self) -> bool:
        return self._stream is not None and self._stream.active

    @property
    def output_level(self) -> float:
        return self._level

    @property
    def xruns(self) -> int:
        return self._xruns

    @property
    def samplerate(self) -> float:
        return self._rate

    def latest_window(self) -> np.ndarray:
        """Most recent mono samples for the visualizer (copy, thread-safe enough)."""
        return self._viz.copy()

    def set_gains(self, gains: BandGains) -> None:
        with self._lock:
            self._target = gains

    def set_makeup_db(self, db: float) -> None:
        """Output volume after the EQ, applied after the boost.

        Anything above +MAX_BOOST_DB of make-up eats into the headroom the pad
        reserved, so a full boost will start meeting the limiter.
        """
        self._makeup = 10.0 ** (db / 20.0)

    def start(self, input_index: int, output_index: int) -> None:
        self.stop()
        out_rate = float(sd.query_devices(output_index)["default_samplerate"] or 48000.0)
        in_rate = float(sd.query_devices(input_index)["default_samplerate"] or 48000.0)
        # Windows devices are picky about rates; try the plausible ones in order.
        rates = list(dict.fromkeys([out_rate, in_rate, 48000.0, 44100.0]))
        extra = _wasapi_duplex_settings(input_index, output_index)
        last_error: Exception | None = None
        for rate in rates:
            try:
                self._rate = rate
                self._eq = ThreeBandEq(rate=rate, channels=2)
                self._stream = sd.Stream(
                    device=(input_index, output_index),
                    samplerate=rate,
                    blocksize=BLOCK_FRAMES,
                    channels=2,
                    dtype="float32",
                    callback=self._callback,
                    extra_settings=extra,
                )
                self._stream.start()
                return
            except Exception as exc:  # noqa: BLE001 - try the next rate, keep the last error
                last_error = exc
                self._stream = None
        raise RuntimeError(f"could not open audio stream at {rates}: {last_error}")

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._level = 0.0

    def _callback(
        self,
        indata: np.ndarray,
        outdata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            self._xruns += 1
        eq = self._eq
        if eq is None:
            outdata[:] = indata
            return
        with self._lock:
            target = self._target
        # Per-block ramp toward the target keeps gain moves click-free.
        self._current = tuple(
            cur + RAMP_ALPHA * (tgt - cur)
            for cur, tgt in zip(
                self._current, (target.bass_db, target.mid_db, target.treble_db)
            )
        )
        eq.set_gains(*self._current)
        # Adaptive headroom. A fixed -12 dB pad assumes the source arrives near
        # full scale; against a quiet one it threw away 12 dB that could not be
        # recovered without turning the speaker up, and a small speaker driven
        # hard is its own source of crackle. Pad only as far as the current
        # boost actually needs, and never amplify.
        block_peak = float(np.abs(indata).max())
        self._peak = max(block_peak, self._peak * PEAK_RELEASE)
        # Reserve room for the *maximum* boost, not the one currently applied.
        # Tracking the current boost would cancel it out, and a boost has to
        # read as more of that band rather than the same level rebalanced.
        target_pad = min(1.0, PAD_CEILING * HEADROOM / max(self._peak, 1e-6))
        self._pad += PAD_SMOOTH * (target_pad - self._pad)
        processed = eq.process(indata * self._pad)
        processed = _soft_limit(processed * self._makeup)
        outdata[:] = processed
        self._level = float(np.sqrt(np.mean(processed**2)))
        mono = processed.mean(axis=1).astype(np.float32)
        self._viz = np.concatenate([self._viz[len(mono):], mono])
