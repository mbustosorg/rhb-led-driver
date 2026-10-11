"""Pattern interface.

A pattern draws one frame for every segment, given the time and the sensor
state.  It writes floats 0..1 into `(pixels, 3)` numpy arrays; brightness
limiting and byte conversion happen in output.py, so patterns never need
to care about power draw.
"""

import numpy as np

from rhb_led_driver.layout import Layout
from rhb_led_driver.output import Frame
from rhb_led_driver.sensors import SensorState


class Pattern:
    name = "base"

    def __init__(self, layout: Layout):
        self.layout = layout
        # 0..1 position of each pixel along its segment, for spatial math.
        self.pos = {s.name: np.linspace(0.0, 1.0, s.pixels) for s in layout.segments}

    def render(self, now: float, sensors: SensorState, frame: Frame) -> None:
        """Fill `frame[segment]` in place.  `now` is seconds on the monotonic clock."""
        raise NotImplementedError


def blank_frame(layout: Layout) -> Frame:
    return {s.name: np.zeros((s.pixels, 3)) for s in layout.segments}
