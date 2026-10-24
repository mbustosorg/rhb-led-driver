from pathlib import Path

import numpy as np
import pytest

from rhb_led_driver.layout import load_layout
from rhb_led_driver.output import NullOutput
from rhb_led_driver.patterns import PATTERNS
from rhb_led_driver.patterns.base import blank_frame
from rhb_led_driver.sensors import SensorState

LAYOUT = load_layout(Path(__file__).resolve().parent.parent / "config" / "layout.toml")


@pytest.mark.parametrize("name", sorted(PATTERNS))
@pytest.mark.parametrize("with_data", [False, True])
def test_pattern_renders_valid_frame(name, with_data):
    sensors = SensorState()
    if with_data:
        for address, value in [("/pressure", 30), ("/temperature", 120), ("/water_heater", 1), ("/poof_button", 1)]:
            sensors.on_osc(address, value)
    frame = blank_frame(LAYOUT)
    PATTERNS[name](LAYOUT).render(12.3, sensors, frame)
    for seg in LAYOUT.segments:
        assert frame[seg.name].shape == (seg.pixels, 3)
        assert np.isfinite(frame[seg.name]).all()
    NullOutput(LAYOUT).send(frame, 0.5)


def test_solid_color_follows_led_color():
    from rhb_led_driver.main import Driver

    driver = Driver(LAYOUT, NullOutput(LAYOUT), "rainbow")
    driver.handle("/led/color", "#ff8000")
    driver.handle("/led/pattern", "solid")  # a color set before switching still applies
    driver.pattern.render(0.0, driver.sensors, driver.frame)
    for seg in driver.frame.values():
        assert np.allclose(seg, [1.0, 128 / 255, 0.0])
    driver.handle("/led/color", 0.0, 0.0, 2.0)  # floats work too, clipped to 0..1
    driver.pattern.render(0.0, driver.sensors, driver.frame)
    assert np.allclose(driver.frame[LAYOUT.segments[0].name], [0.0, 0.0, 1.0])
    assert driver.state()["color"] == "#0000ff"
    driver.handle("/led/color", "nope")  # ignored
    assert driver.state()["color"] == "#0000ff"


@pytest.mark.parametrize("pattern", ["solid", "rainbow", "instruments"])
def test_poof_pulse_overlays_any_pattern(pattern):
    from rhb_led_driver.main import Driver
    from rhb_led_driver.poof import PULSE_COLOR

    driver = Driver(LAYOUT, NullOutput(LAYOUT), pattern)
    driver.poof.render(0.0, driver.sensors, driver.frame)  # no press yet: nothing drawn
    driver.pattern.render(0.0, driver.sensors, driver.frame)
    before = {n: seg.copy() for n, seg in driver.frame.items()}
    driver.handle("/poof_button", 1)
    driver.poof.render(0.0, driver.sensors, driver.frame)
    hoses = [n for n in driver.frame if n.startswith("hose")]
    assert hoses
    for name, seg in driver.frame.items():
        if name in hoses:
            assert np.allclose(seg[0], PULSE_COLOR, atol=0.01)  # the pulse starts at the gauge end
            assert np.allclose(seg[-1], before[name][-1])  # and hasn't reached the nozzle
        else:
            assert np.array_equal(seg, before[name])


def test_eiffel_keeps_its_own_poof():
    from rhb_led_driver.main import Driver

    assert Driver(LAYOUT, NullOutput(LAYOUT), "eiffel").pattern.own_poof
    assert not Driver(LAYOUT, NullOutput(LAYOUT), "solid").pattern.own_poof


def test_standby_blinks_only_the_first_pixel_red():
    from rhb_led_driver.patterns.standby import BLINK_SECONDS, ON_FRACTION

    pattern = PATTERNS["standby"](LAYOUT)
    frame = blank_frame(LAYOUT)
    pattern.render(10 * BLINK_SECONDS, SensorState(), frame)  # start of a cycle: on
    for seg in frame.values():
        assert np.allclose(seg[0], [1.0, 0.0, 0.0]) and not seg[1:].any()
    pattern.render(10 * BLINK_SECONDS + BLINK_SECONDS * (ON_FRACTION + 0.1), SensorState(), frame)  # off
    assert not any(seg.any() for seg in frame.values())
    assert pattern.own_poof
