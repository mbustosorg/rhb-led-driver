"""Every pixel one color.  Ignores sensors.

The color can be changed live with /led/color (the simulator page has a
picker); COLOR is what it starts as.
"""

import numpy as np

from rhb_led_driver.patterns.base import Pattern

# Behavioral knobs -- tune here.
COLOR = np.array([1.0, 0.8, 0.55])  # warm white; full RGB white reads bluish on the strips


class Solid(Pattern):
    name = "solid"

    def __init__(self, layout):
        super().__init__(layout)
        self.color = COLOR

    def render(self, now, sensors, frame):
        for seg in frame.values():
            seg[:] = self.color
