"""System audio routing helpers (macOS, via SwitchAudioSource).

Lets the app route the Mac's output to BlackHole with one click and put it
back afterward, so the user never has to visit Sound settings mid-demo.
"""

import shutil
import subprocess

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
