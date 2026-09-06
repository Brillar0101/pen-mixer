"""Live audio engine: reads the loopback input, applies the EQ, writes to output.

macOS routing for "EQ whatever is playing":
    System Settings -> Sound -> Output -> BlackHole 2ch
    In the app: input = BlackHole 2ch, output = your speakers/headphones.
Music from any app then flows through this engine and the EQ.
"""

import threading
from dataclasses import dataclass

import numpy as np
import sounddevice as sd

from .eqdsp import ThreeBandEq
from .mapping import BandGains
from .spectrum import WINDOW_SAMPLES

BLOCK_FRAMES = 256
RAMP_ALPHA = 0.35
# BlackHole delivers system audio hotter than full scale (measured 1.6 peak on
# this machine), and a +12 dB boost needs room on top of that. -9 dB of input
# headroom keeps boosted output clean; the volume knob compensates.
HEADROOM = 0.35


@dataclass(frozen=True)
class DeviceInfo:
    index: int
    name: str
    inputs: int
    outputs: int


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
            )
        )
    return devices


def default_input_index() -> int | None:
    """Prefer the loopback device so system audio is what gets EQ'd.

    BlackHole on macOS, VB-Audio Virtual Cable ("CABLE Output") on Windows.
    """
    for hint in ("blackhole", "cable output"):
        for dev in list_devices():
            if hint in dev.name.lower() and dev.inputs >= 2:
                return dev.index
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

    def start(self, input_index: int, output_index: int) -> None:
        self.stop()
        out_rate = float(sd.query_devices(output_index)["default_samplerate"] or 48000.0)
        in_rate = float(sd.query_devices(input_index)["default_samplerate"] or 48000.0)
        # Windows devices are picky about rates; try the plausible ones in order.
        rates = list(dict.fromkeys([out_rate, in_rate, 48000.0, 44100.0]))
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
        processed = eq.process(indata * HEADROOM)
        outdata[:] = processed
        self._level = float(np.sqrt(np.mean(processed**2)))
        mono = processed.mean(axis=1).astype(np.float32)
        self._viz = np.concatenate([self._viz[len(mono):], mono])
