import pytest

from penmixer.frames import MotionFrame
from penmixer.mapping import MAX_BOOST_DB, BandGains, gains_from_frame, smooth


def at_rest() -> MotionFrame:
    return MotionFrame(tilt=0.0, roll=0.0, energy=0.0)


def test_pen_at_rest_is_flat() -> None:
    assert gains_from_frame(at_rest()) == BandGains(0.0, 0.0, 0.0)


def test_tilt_forward_boosts_bass_only() -> None:
    # A full tilt has to reach the rail, or the band cannot be driven fully.
    gains = gains_from_frame(MotionFrame(tilt=45.0, roll=0.0, energy=0.0))
    assert gains.bass_db == pytest.approx(MAX_BOOST_DB)
    assert gains.mid_db == 0.0
    assert gains.treble_db == 0.0


def test_tilt_back_cuts_bass() -> None:
    gains = gains_from_frame(MotionFrame(tilt=-45.0, roll=0.0, energy=0.0))
    assert gains.bass_db == pytest.approx(-MAX_BOOST_DB)


def test_twist_drives_treble_both_ways() -> None:
    boost = gains_from_frame(MotionFrame(tilt=0.0, roll=90.0, energy=0.0))
    # Treble is 2x sensitive, so a quarter roll already reaches half gain.
    cut = gains_from_frame(MotionFrame(tilt=0.0, roll=-22.5, energy=0.0))
    assert boost.treble_db == MAX_BOOST_DB
    assert cut.treble_db == -MAX_BOOST_DB / 2
    assert boost.bass_db == 0.0


def test_half_tilt_is_half_gain() -> None:
    gains = gains_from_frame(MotionFrame(tilt=22.5, roll=0.0, energy=0.0))
    assert gains.bass_db == pytest.approx(MAX_BOOST_DB / 2)


def test_smooth_moves_toward_target() -> None:
    start = BandGains(0.0, 0.0, 0.0)
    target = BandGains(12.0, 12.0, 12.0)
    stepped = smooth(start, target, alpha=0.5)
    assert stepped.bass_db == 6.0
    assert 0.0 < stepped.mid_db < 12.0


def test_sway_drives_mid_left_cuts_right_boosts() -> None:
    right = gains_from_frame(MotionFrame(tilt=0.0, roll=0.0, energy=0.0, sway=1.0))
    left = gains_from_frame(MotionFrame(tilt=0.0, roll=0.0, energy=0.0, sway=-0.25))
    assert right.mid_db == MAX_BOOST_DB
    assert left.mid_db == pytest.approx(-MAX_BOOST_DB / 2)
    assert right.bass_db == 0.0 and right.treble_db == 0.0
