"""Read the computer's master volume so the app can follow it.

Windows only (pycaw over Core Audio); on other platforms or if anything
fails, get_volume returns None and the app simply does not sync. The
endpoint handle is cached and re-resolved when it goes stale, e.g. when
the default output device changes.
"""

import sys

_endpoint = None


def _resolve():
    from pycaw.pycaw import AudioUtilities

    return AudioUtilities.GetSpeakers().EndpointVolume


def get_volume() -> tuple[float, bool] | None:
    """Master volume of the default output as (scalar 0..1, muted), or None."""
    global _endpoint
    if sys.platform != "win32":
        return None
    for _ in range(2):
        try:
            if _endpoint is None:
                _endpoint = _resolve()
            return _endpoint.GetMasterVolumeLevelScalar(), bool(_endpoint.GetMute())
        except Exception:
            _endpoint = None
    return None
