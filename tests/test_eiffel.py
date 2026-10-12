from pathlib import Path

import numpy as np

from rhb_led_driver.layout import load_layout
from rhb_led_driver.patterns.base import blank_frame
from rhb_led_driver.patterns.eiffel import Eiffel
from rhb_led_driver.sensors import SensorState

LAYOUT = load_layout(Path(__file__).resolve().parent.parent / "config" / "layout.toml")


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


def sparkle(press: bool, seconds=2.0, fps=40):
    """Mean fraction of pixels flashing (blue channel high: gold has little blue)."""
    clock = Clock()
    sensors = SensorState(clock=clock)
    pattern = Eiffel(LAYOUT, rng=np.random.default_rng(1))
    frame = blank_frame(LAYOUT)
    if press:
        sensors.on_osc("/poof_button", 1)
    lit = []
    for i in range(int(seconds * fps)):
        clock.t = i / fps
        pattern.render(clock.t, sensors, frame)
        rgb = np.concatenate(list(frame.values()))
        lit.append(np.mean(rgb[:, 2] > 0.5))
    return np.mean(lit)


def test_first_frame_is_steady_gold():
    pattern = Eiffel(LAYOUT, rng=np.random.default_rng(1))
    frame = blank_frame(LAYOUT)
    pattern.render(5.0, SensorState(), frame)
    rgb = np.concatenate(list(frame.values()))
    assert (rgb[:, 0] > rgb[:, 1]).all() and (rgb[:, 1] > rgb[:, 2]).all()  # gold, no flashes yet


def test_glitters_and_poof_button_brings_the_show():
    normal = sparkle(press=False)
    show = sparkle(press=True)
    assert 0.005 < normal < 0.1
    assert show > 2.5 * normal
