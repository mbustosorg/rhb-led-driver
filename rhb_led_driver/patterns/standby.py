"""Standby: the driver is up but no show is running.  Ignores sensors.

Everything dark except the first pixel of every segment, which blinks red.
That says the program is loaded, and that each controller port is wired
and getting data: a strip whose first pixel isn't blinking isn't.  Pick a
pattern (/led/pattern, or the simulator page) to start the show.
"""

import numpy as np

from rhb_led_driver.patterns.base import Pattern

# Behavioral knobs -- tune here.
BLINK_SECONDS = 1.0  # one on-and-off cycle
ON_FRACTION = 0.3  # of each cycle the light is on
COLOR = np.array([1.0, 0.0, 0.0])
LIT = 1  # pixels lit at the start of each segment


class Standby(Pattern):
    name = "standby"
    own_poof = True  # stays quiet: the poof pulse would look like a show

    def render(self, now, sensors, frame):
        on = (now % BLINK_SECONDS) < BLINK_SECONDS * ON_FRACTION
        for seg in frame.values():
            seg[:] = 0.0
            if on:
                seg[:LIT] = COLOR
