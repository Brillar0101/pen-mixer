from penmixer.frames import TouchFrame
from penmixer.mapping import MAX_BOOST_DB, BandGains, gains_from_frame, smooth


def untouched() -> TouchFrame:
    return TouchFrame(tilt=-45.0, roll=-90.0, energy=0.0)


def test_untouched_is_flat() -> None:
    assert gains_from_frame(untouched()) == BandGains(0.0, 0.0, 0.0)


def test_full_a0_touch_boosts_bass_only() -> None:
    gains = gains_from_frame(TouchFrame(tilt=45.0, roll=-90.0, energy=0.0))
    assert gains.bass_db == MAX_BOOST_DB
    assert gains.mid_db == 0.0
    assert gains.treble_db == 0.0


def test_full_a1_touch_boosts_treble_only() -> None:
    gains = gains_from_frame(TouchFrame(tilt=-45.0, roll=90.0, energy=0.0))
    assert gains.treble_db == MAX_BOOST_DB
    assert gains.bass_db == 0.0
    assert gains.mid_db == 0.0


def test_both_pads_raise_mid() -> None:
    gains = gains_from_frame(TouchFrame(tilt=45.0, roll=90.0, energy=0.0))
    assert gains.mid_db == MAX_BOOST_DB
    assert gains.bass_db == MAX_BOOST_DB
    assert gains.treble_db == MAX_BOOST_DB


def test_smooth_moves_toward_target() -> None:
    start = BandGains(0.0, 0.0, 0.0)
    target = BandGains(12.0, 12.0, 12.0)
    stepped = smooth(start, target, alpha=0.5)
    assert stepped.bass_db == 6.0
    assert 0.0 < stepped.mid_db < 12.0
