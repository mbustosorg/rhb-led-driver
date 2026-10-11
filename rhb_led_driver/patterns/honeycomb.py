# ADOPTED from lindsay-50 lib_shared/patterns/honeycomb.py @ c98fde6 -- edit freely.
# Port: same math, evaluated at each pixel's uv instead of a 64x64 meshgrid; time from render().
# --- end adoption header ---
"""Honeycomb -- a port of a Pixelblaze 2D pattern (honeycomb.js).

A full-color HSV interference field.  On the sign it was evaluated over the
whole panel; here it is evaluated only where pixels actually are, so the
hose, handle and gauge each show their slice of one field that spans the car.
"""

import numpy as np

from rhb_led_driver.adopted.pixelblaze import PI2, hsv_to_rgb, time_saw, triangle, wave
from rhb_led_driver.patterns.base import Pattern

# Behavioral knobs.
TF = 15.0  # animation duration; smaller = faster
# Cell size: 1.0 matches the sign (a cell or two across the longest axis);
# raise it for more, smaller cells along the car.
DENSITY = 1.0


class Honeycomb(Pattern):
    name = "honeycomb"

    def __init__(self, layout):
        super().__init__(layout)
        # Every pixel of every segment in one array, so a frame is one vectorized pass.
        self._names = list(self.uv)
        uv = np.concatenate([self.uv[n] for n in self._names])
        self._X, self._Y = uv[:, 0], uv[:, 1]
        self._splits = np.cumsum([len(self.uv[n]) for n in self._names])[:-1]

    def render(self, now, sensors, frame):
        def T(period_s):  # Pixelblaze time() over a period in seconds
            return time_saw(now, period_s)

        f = (wave(T(TF * 6.6)) * 5.0 + 7.0) * DENSITY  # cell density
        t1 = wave(T(TF * 9.8)) * PI2  # x shift
        t2 = wave(T(TF * 12.5)) * PI2  # y shift
        t3 = wave(T(TF * 9.8))  # hue shift
        t4 = T(TF * 0.66)  # value shift

        z = (1.0 + np.sin(self._X * f + t1) + np.cos(self._Y * f + t2)) * 0.5
        v = wave(z + t4)
        v = v * v * v
        h = triangle(z) / 2.0 + t3

        rgb = hsv_to_rgb(h, 1.0, np.clip(v, 0.0, 1.0))
        for name, part in zip(self._names, np.split(rgb, self._splits)):
            frame[name][:] = part
