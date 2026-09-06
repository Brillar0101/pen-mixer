"""Map touch frames to EQ band gains.

Deterministic mapping, documented so the demo is explainable:
    pad A0 (tilt)          -> bass boost, 0 dB untouched up to +MAX_BOOST_DB
    pad A1 (roll)          -> treble boost, same range
    both pads together     -> mid boost follows the weaker of the two,
                              so pinching both pads raises the mids
Untouched pads always mean flat (0 dB), never a cut, so the music is
unchanged until a finger lands.
"""

from dataclasses import dataclass

from .frames import ROLL_RANGE, TILT_RANGE, TouchFrame

MAX_BOOST_DB = 12.0


@dataclass(frozen=True)
class BandGains:
    bass_db: float
    mid_db: float
    treble_db: float


FLAT = BandGains(0.0, 0.0, 0.0)


def _normalize(value: float, low: float, high: float) -> float:
    return min(max((value - low) / (high - low), 0.0), 1.0)


def gains_from_frame(frame: TouchFrame) -> BandGains:
    """Convert one touch frame into band gains in dB."""
    d0 = _normalize(frame.tilt, *TILT_RANGE)
    d1 = _normalize(frame.roll, *ROLL_RANGE)
    return BandGains(
        bass_db=d0 * MAX_BOOST_DB,
        mid_db=min(d0, d1) * MAX_BOOST_DB,
        treble_db=d1 * MAX_BOOST_DB,
    )


def gains_from_frame_signed(frame: TouchFrame) -> BandGains:
    """IMU pen mapping: signed around the at-rest zero, so motion one way
    boosts and the other way cuts (the PRD's M2 direction idea). The mids
    stay flat until the firmware sends a third axis."""
    return BandGains(
        bass_db=max(-1.0, min(1.0, frame.tilt / TILT_RANGE[1])) * MAX_BOOST_DB,
        mid_db=0.0,
        treble_db=max(-1.0, min(1.0, frame.roll / ROLL_RANGE[1])) * MAX_BOOST_DB,
    )


def smooth(previous: BandGains, target: BandGains, alpha: float = 0.25) -> BandGains:
    """One-pole smoothing between gain updates to avoid jumpy sliders.

    alpha 0.25 at the firmware's 6 ms frame interval gives a ~24 ms time
    constant, the smoothing figure the PRD's F2 requirement specifies.
    """

    def step(prev: float, new: float) -> float:
        return prev + alpha * (new - prev)

    return BandGains(
        bass_db=step(previous.bass_db, target.bass_db),
        mid_db=step(previous.mid_db, target.mid_db),
        treble_db=step(previous.treble_db, target.treble_db),
    )
