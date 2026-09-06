"""Parse the pen board serial frame format: "tilt,roll,energy" CSV lines.

The firmware (code.py) prints one frame every ~6 ms:
    tilt   -45..45   pen tilt from the IMU
    roll   -90..90   pen roll from the IMU
    energy   0..1    overall motion energy
    sway    -1..1    horizontal motion (left negative, right positive); optional
Comment lines start with '#'.
"""

from dataclasses import dataclass

TILT_RANGE = (-45.0, 45.0)
ROLL_RANGE = (-90.0, 90.0)


@dataclass(frozen=True)
class MotionFrame:
    tilt: float
    roll: float
    energy: float
    sway: float = 0.0  # -1..1 horizontal motion, left negative; absent on old firmware


def parse_line(line: str) -> MotionFrame | None:
    """Parse one serial line into a MotionFrame, or None if not a data frame."""
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    parts = text.split(",")
    if len(parts) not in (3, 4):
        return None
    try:
        values = [float(p) for p in parts]
    except ValueError:
        return None
    tilt, roll, energy = values[:3]
    sway = min(max(values[3], -1.0), 1.0) if len(values) == 4 else 0.0
    tilt = min(max(tilt, TILT_RANGE[0]), TILT_RANGE[1])
    roll = min(max(roll, ROLL_RANGE[0]), ROLL_RANGE[1])
    energy = min(max(energy, 0.0), 1.0)
    return MotionFrame(tilt=tilt, roll=roll, energy=energy, sway=sway)


TouchFrame = MotionFrame  # legacy name from the touch test rig
