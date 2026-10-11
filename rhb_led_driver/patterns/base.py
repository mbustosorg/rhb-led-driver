"""Pattern interface.

A pattern draws one frame for every segment, given the time and the sensor
state.  It writes floats 0..1 into `(pixels, 3)` numpy arrays; brightness
limiting and byte conversion happen in output.py, so patterns never need
to care about power draw.

Three ways to know where a pixel is, all dicts keyed by segment name:

    pos[name]   (pixels,)    0..1 along the segment, in wiring order
    xy[name]    (pixels, 2)  physical x,y from layout.toml (inches)
    uv[name]    (pixels, 2)  xy normalized over the whole car: 0..1 on its
                             longest axis, aspect kept -- the Pixelblaze-style
                             coordinates 2-D patterns want
"""

import numpy as np

from rhb_led_driver.geometry import normalize
from rhb_led_driver.layout import Layout
from rhb_led_driver.output import Frame
from rhb_led_driver.sensors import SensorState


class Pattern:
    name = "base"

    def __init__(self, layout: Layout):
        self.layout = layout
        # 0..1 position of each pixel along its segment, for spatial math.
        self.pos = {s.name: np.linspace(0.0, 1.0, s.pixels) for s in layout.segments}
        self.xy = {s.name: s.xy for s in layout.segments}
        self.uv = normalize(self.xy)

    def render(self, now: float, sensors: SensorState, frame: Frame) -> None:
        """Fill `frame[segment]` in place.  `now` is seconds on the monotonic clock."""
        raise NotImplementedError


def blank_frame(layout: Layout) -> Frame:
    return {s.name: np.zeros((s.pixels, 3)) for s in layout.segments}
