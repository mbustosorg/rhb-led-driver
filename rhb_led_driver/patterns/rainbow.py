"""Idle pattern: a slow rainbow drifting along every segment.  Ignores sensors."""

from rhb_led_driver.adopted.pixelblaze import hsv_to_rgb, time_saw
from rhb_led_driver.patterns.base import Pattern


class Rainbow(Pattern):
    name = "rainbow"
    period_s = 20.0

    def render(self, now, sensors, frame):
        shift = time_saw(now, self.period_s)
        for name, pos in self.pos.items():
            frame[name][:] = hsv_to_rgb(pos + shift, 1.0, 1.0)
