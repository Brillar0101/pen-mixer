"""System audio routing helpers (macOS, via SwitchAudioSource).

Lets the app route the Mac's output to BlackHole with one click and put it
back afterward, so the user never has to visit Sound settings mid-demo.
Windows has no equivalent CLI, so there the default playback device has to
be switched by hand and all this module can do is say so.
"""

import shutil
import subprocess
import sys

BLACKHOLE_NAME = "BlackHole 2ch"
_CANDIDATES = ("/opt/homebrew/bin/SwitchAudioSource", "/usr/local/bin/SwitchAudioSource")


def _tool() -> str | None:
    found = shutil.which("SwitchAudioSource")
    if found:
        return found
    for path in _CANDIDATES:
        if shutil.which(path):
            return path
    return None


def available() -> bool:
    return _tool() is not None


def current_output() -> str | None:
    tool = _tool()
    if tool is None:
        return None
    try:
        result = subprocess.run(
            [tool, "-c", "-t", "output"], capture_output=True, text=True, timeout=5, check=False
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def set_output(device_name: str) -> bool:
    tool = _tool()
    if tool is None:
        return False
    try:
        result = subprocess.run(
            [tool, "-t", "output", "-s", device_name],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def loopback_hint() -> str:
    """Why the EQ input is silent, and the one manual step that fixes it.

    The engine reads the loopback capture device, so nothing reaches the EQ
    until the system's playback device is the matching loopback sink. On
    macOS the route button does that; on Windows it has to be done by hand.
    """
    if sys.platform == "win32":
        return (
            "audio running but the input is silent: set Windows Settings -> System -> "
            "Sound -> Output to 'CABLE Input (VB-Audio Virtual Cable)', then play music"
        )
    return (
        "audio running but the input is silent: set System Settings -> Sound -> "
        f"Output to {BLACKHOLE_NAME}, then play music"
    )
