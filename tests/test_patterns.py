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
