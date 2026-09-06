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
    hostapi: int
    hostapi_name: str


# PortAudio cannot open a duplex stream whose two ends sit on different host
# APIs; it fails with PaErrorCode -9993. The same card is enumerated once per
# API, so the input decides which API the output has to come from. Ranked by
# latency, best first.
HOST_API_PREFERENCE = ("wasapi", "directsound", "mme", "wdm-ks")
LOOPBACK_HINTS = ("blackhole", "cable output")
OUTPUT_HINTS = ("bose", "airpod", "headphone", "speaker")


def _api_rank(name: str) -> int:
    low = name.lower()
    for rank, hint in enumerate(HOST_API_PREFERENCE):
        if hint in low:
            return rank
    return len(HOST_API_PREFERENCE)


def _is_loopback(name: str) -> bool:
    return any(hint in name.lower() for hint in LOOPBACK_HINTS)


def is_virtual_sink(name: str) -> bool:
    """Outputs that would feed the loopback back into itself."""
    low = name.lower()
    return "blackhole" in low or "cable in" in low


def _same_endpoints_on(
    in_dev: DeviceInfo,
    out_dev: DeviceInfo,
    devices: list[DeviceInfo],
    api_hint: str,
) -> tuple[DeviceInfo, DeviceInfo] | None:
    """The same two endpoints as enumerated by another host API, if both exist.

    MME truncates names to 31 characters, so match by prefix in both
    directions.
    """

    def twin(target: DeviceInfo, want_input: bool) -> DeviceInfo | None:
        for dev in devices:
            if api_hint not in dev.hostapi_name.lower():
                continue
            if (dev.inputs if want_input else dev.outputs) < 2:
                continue
            a, b = dev.name.strip(), target.name.strip()
            if a.startswith(b) or b.startswith(a):
                return dev
        return None

    fallback_in = twin(in_dev, want_input=True)
    fallback_out = twin(out_dev, want_input=False)
    if fallback_in is None or fallback_out is None:
        return None
    return fallback_in, fallback_out


def rescan_devices() -> None:
    """Make PortAudio re-enumerate: picks up devices plugged in or installed
    after launch. Only safe while no stream is open."""
    sd._terminate()
    sd._initialize()


def list_devices() -> list[DeviceInfo]:
    devices = []
    for idx, dev in enumerate(sd.query_devices()):
        api = int(dev["hostapi"])
        devices.append(
            DeviceInfo(
                index=idx,
                name=str(dev["name"]),
                inputs=int(dev["max_input_channels"]),
                outputs=int(dev["max_output_channels"]),
                hostapi=api,
                hostapi_name=str(sd.query_hostapis(api)["name"]),
            )
        )
    return devices


def loopback_inputs() -> list[DeviceInfo]:
    """Every loopback capture device, lowest-latency host API first."""
    found = [d for d in list_devices() if d.inputs >= 2 and _is_loopback(d.name)]
    return sorted(found, key=lambda d: _api_rank(d.hostapi_name))


def preferred_hostapi() -> int | None:
    """The one host API the device pickers should show.

    Windows enumerates every endpoint once per API (MME, DirectSound, WASAPI,
    WDM-KS), which quadruples the list and invites picking an unopenable
    cross-API pair. Follow the best loopback's API; without one, the
    best-ranked API that has both an input and an output.
    """
    found = loopback_inputs()
    if found:
        return found[0].hostapi
    devices = list_devices()
    ranked = sorted(
        {(d.hostapi, d.hostapi_name) for d in devices},
        key=lambda pair: _api_rank(pair[1]),
    )
    for api, _name in ranked:
        has_in = any(d.inputs >= 2 for d in devices if d.hostapi == api)
        has_out = any(d.outputs >= 2 for d in devices if d.hostapi == api)
        if has_in and has_out:
            return api
    return None


def default_input_index() -> int | None:
    """Prefer the loopback device so system audio is what gets EQ'd.

    BlackHole on macOS, VB-Audio Virtual Cable ("CABLE Output") on Windows.
    Windows enumerates the cable under every host API; take the fastest.
    """
    found = loopback_inputs()
    return found[0].index if found else None


def preferred_output_index(input_index: int | None) -> int | None:
    """A real output device on the same host API as the chosen input.

    Matching the host API is what keeps the duplex stream openable, so it
    outranks the name hints: a nicer-sounding device on the wrong API is
    useless.
    """
    devices = list_devices()
    usable = [d for d in devices if d.outputs >= 2 and not is_virtual_sink(d.name)]
    if input_index is not None and 0 <= input_index < len(devices):
        api = devices[input_index].hostapi
        same_api = [d for d in usable if d.hostapi == api]
        if same_api:
            usable = same_api
    for hint in OUTPUT_HINTS:
        for dev in usable:
            if hint in dev.name.lower():
                return dev.index
    return usable[0].index if usable else None


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
        self._makeup = 10.0 ** (9.0 / 20.0)  # default +9 dB, cancels the input pad

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
        """Output volume after the EQ. +9 dB restores unity against the pad."""
        self._makeup = 10.0 ** (db / 20.0)

    def start(self, input_index: int, output_index: int) -> None:
        self.stop()
        devices = list_devices()
        in_dev, out_dev = devices[input_index], devices[output_index]
        if in_dev.hostapi != out_dev.hostapi:
            # PortAudio would report only "illegal combination of I/O devices".
            raise RuntimeError(
                f"input is {in_dev.hostapi_name} but output is "
                f"{out_dev.hostapi_name}; both must be on the same host API. "
                f"Click Rescan and pick again."
            )
        # WASAPI is preferred but refuses transiently on some machines
        # (paInsufficientMemory and friends); the same endpoints on MME are
        # slower but nearly always open. Try WASAPI, then fall back.
        pairs = [(in_dev, out_dev)]
        if "wasapi" in in_dev.hostapi_name.lower():
            fallback = _same_endpoints_on(in_dev, out_dev, devices, "mme")
            if fallback is not None:
                pairs.append(fallback)
        last_error: Exception | None = None
        for pair_in, pair_out in pairs:
            out_rate = float(
                sd.query_devices(pair_out.index)["default_samplerate"] or 48000.0
            )
            in_rate = float(
                sd.query_devices(pair_in.index)["default_samplerate"] or 48000.0
            )
            # Windows devices are picky about rates; try the plausible ones.
            rates = list(dict.fromkeys([out_rate, in_rate, 48000.0, 44100.0]))
            # WASAPI shared mode rejects any rate that is not the device mix
            # rate, and the cable and the speakers often disagree (44.1k vs
            # 48k). auto_convert lets Windows resample instead of refusing.
            extra = None
            if "wasapi" in pair_in.hostapi_name.lower():
                extra = sd.WasapiSettings(auto_convert=True)
            for rate in rates:
                try:
                    self._rate = rate
                    self._eq = ThreeBandEq(rate=rate, channels=2)
                    self._stream = sd.Stream(
                        device=(pair_in.index, pair_out.index),
                        samplerate=rate,
                        blocksize=BLOCK_FRAMES,
                        channels=2,
                        dtype="float32",
                        extra_settings=extra,
                        callback=self._callback,
                    )
                    self._stream.start()
                    return
                except Exception as exc:  # noqa: BLE001 - next rate or pair
                    last_error = exc
                    self._stream = None
        raise RuntimeError(f"could not open audio stream: {last_error}")

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
        processed = np.clip(processed * self._makeup, -1.0, 1.0)
        outdata[:] = processed
        self._level = float(np.sqrt(np.mean(processed**2)))
        mono = processed.mean(axis=1).astype(np.float32)
        self._viz = np.concatenate([self._viz[len(mono):], mono])
