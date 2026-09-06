"""Map pen motion frames to EQ band gains.

Signed around the at-rest zero, so the pen held still is flat (0 dB) and
motion one way boosts while the other way cuts:
    tilt   -> bass,   forward boosts up to +MAX_BOOST_DB, back cuts to -MAX_BOOST_DB
    roll   -> treble, twist one way boosts, the other cuts
    mid    -> flat until the firmware streams a horizontal-motion value (PRD M2)
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




def gains_from_frame(frame: TouchFrame) -> BandGains:
    """Pen mapping: signed, both directions; mids flat until a third axis arrives."""
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
