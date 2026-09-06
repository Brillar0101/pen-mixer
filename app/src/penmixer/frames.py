"""Parse the pen board serial frame format: "tilt,roll,energy" CSV lines.

The firmware (code.py) prints one frame every ~6 ms:
    tilt   -45..45   pen tilt from the IMU
    roll   -90..90   pen roll from the IMU
    energy   0..1    overall motion energy
Comment lines start with '#'.
"""

from dataclasses import dataclass

TILT_RANGE = (-45.0, 45.0)
ROLL_RANGE = (-90.0, 90.0)


@dataclass(frozen=True)
class TouchFrame:
    tilt: float
    roll: float
    energy: float


def parse_line(line: str) -> TouchFrame | None:
    """Parse one serial line into a TouchFrame, or None if not a data frame."""
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    parts = text.split(",")
    if len(parts) != 3:
        return None
    try:
        tilt, roll, energy = (float(p) for p in parts)
    except ValueError:
        return None
    tilt = min(max(tilt, TILT_RANGE[0]), TILT_RANGE[1])
    roll = min(max(roll, ROLL_RANGE[0]), ROLL_RANGE[1])
    energy = min(max(energy, 0.0), 1.0)
    return TouchFrame(tilt=tilt, roll=roll, energy=energy)
