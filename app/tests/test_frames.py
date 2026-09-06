from penmixer.frames import TouchFrame, parse_line


def test_valid_frame() -> None:
    frame = parse_line("12.50,-30.00,0.250\n")
    assert frame == TouchFrame(tilt=12.5, roll=-30.0, energy=0.25)


def test_comment_and_blank_lines_ignored() -> None:
    assert parse_line("# touch mode") is None
    assert parse_line("") is None
    assert parse_line("   \n") is None


def test_malformed_lines_ignored() -> None:
    assert parse_line("1.0,2.0") is None
    assert parse_line("a,b,c") is None
    assert parse_line("1,2,3,4,5") is None


def test_values_clamped_to_firmware_ranges() -> None:
    frame = parse_line("999,-999,5.0")
    assert frame is not None
    assert frame.tilt == 45.0
    assert frame.roll == -90.0
    assert frame.energy == 1.0


def test_four_field_frame_carries_sway() -> None:
    frame = parse_line("0.00,0.00,0.000,-0.50")
    assert frame is not None
    assert frame.sway == -0.5


def test_three_field_frame_defaults_sway_to_zero() -> None:
    frame = parse_line("1.0,2.0,0.1")
    assert frame is not None
    assert frame.sway == 0.0


def test_sway_is_clamped() -> None:
    frame = parse_line("0,0,0,7.5")
    assert frame is not None
    assert frame.sway == 1.0
