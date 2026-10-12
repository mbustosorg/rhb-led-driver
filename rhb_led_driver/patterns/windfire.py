# ADOPTED from lindsay-50 lib_shared/patterns/windfire.py @ c98fde6 -- edit freely.
# Port: same math over the car's pixel x,y (bounding box as the panel, y flipped) instead of a 64x64 meshgrid.
# Tuned for the car: SIZE 1.6 -> 2.2, MAX_BRIGHTNESS 0.7 -> 1.0.
# --- end adoption header ---
"""WindFire -- a port of a Pixelblaze 2D pattern (wind-bent perlin fire).

A full-color flame driven by 3D Perlin turbulence, with a per-pixel
horizontal "wobble" that makes the flame lean and sway as if bent by wind.

On the sign the flame filled the panel.  Here it fills the car's bounding
box, stretched per axis just as the original stretched over its panel: the
fire burns up from the lowest pixels, hottest at the base, to flickering
tips at the highest, brightest along the middle of the car and fading
toward the ends.

Pixelblaze primitives, mapped:
    time(i)              sawtooth 0..1, period i*65.536s
    wave(v)              (1 + sin(v*2pi)) / 2
    triangle(v)          1 - |1 - 2*frac(v)|
    perlin(x,y,z,seed)   improved (Ken Perlin) 3D noise, wraps every 256
    perlinTurbulence(...) sum of |perlin| over octaves (fractal turbulence)
    setPalette(grad)     piecewise-linear RGB ramp indexed 0..1
    paint(v, bri)        palette color at position v, scaled by brightness bri

The original cycles four noise modes but forces `mode = 3` (turbulence);
this port hardcodes turbulence to match.  resetTransform/translate/scale in
the original zoom the flame 2x and center it.
"""

import numpy as np

from rhb_led_driver.adopted.perlin import perlin_turbulence
from rhb_led_driver.adopted.pixelblaze import PI2, time_pb, triangle, wave
from rhb_led_driver.patterns.base import Pattern

# Behavioral knobs.
TF = 1.0  # animation speed: <1 slower, >1 faster
# >1 makes the flame bigger: widens the bright band and lets it climb higher.
# It keeps the noise feature scale and brightness, so the fire just fills more room.
# The sign used 1.6; on the car 2.2 brings the fire up both hoses while the upper
# one still gets only the tips (above ~2.8 the hoses outshine the base).
SIZE = 2.2
# The sign used 0.7 as its only limit; here layout.toml's max_brightness already
# caps output, and stacking both left the flame at about 40%.
MAX_BRIGHTNESS = 1.0
S = 2.0  # coordinate zoom, from the Pixelblaze scale(s, s)

# setPalette(rgbGradient): position -> (R, G, B), interpolated linearly.
PAL_POS = np.array([0.0, 0.2, 0.9, 1.0])
PAL_R = np.array([0.0, 1.0, 1.0, 1.0])
PAL_G = np.array([0.0, 0.0, 0.6, 0.8])
PAL_B = np.array([0.0, 0.0, 0.0, 0.3])


class WindFire(Pattern):
    name = "windfire"

    def __init__(self, layout):
        super().__init__(layout)
        self._names = list(self.xy)
        xy = np.concatenate([self.xy[n] for n in self._names])
        self._splits = np.cumsum([len(self.xy[n]) for n in self._names])[:-1]

        # The car's bounding box as the panel, each axis 0..1.  The panel's
        # row 0 was the top, so y is flipped: yn = 0 at the highest pixel.
        lo, hi = xy.min(axis=0), xy.max(axis=0)
        span = np.where(hi > lo, hi - lo, 1.0)
        xn = (xy[:, 0] - lo[0]) / span[0]
        yn = (hi[1] - xy[:, 1]) / span[1]
        # Post-transform coords: x' = s*(xn-0.5) centers the flame; y' = s*yn
        # puts the hot base at the bottom (larger y' -> brighter, per the original).
        self._Xp = S * (xn - 0.5)
        self._Yp = S * yn + 0.4

    def render(self, now, sensors, frame):
        now = now * TF
        Xp = self._Xp
        Yp = self._Yp

        t2 = time_pb(now, 0.07)
        t3 = time_pb(now, 0.133)
        # perlin wraps every 256, so sweeping z across 0..256 gives smooth,
        # long-period animation without a visible seam.
        noise_time = time_pb(now, 8.0) * 256.0
        noise_y_time = time_pb(now, 1.6) * 256.0

        # Per-pixel horizontal wobble: a vertical sine that drifts with time,
        # stronger toward the top (S - Yp) so the flame tips bend in the wind.
        wobble = np.sin(((Yp - 0.5) / S + t2 + wave(t3)) * PI2) * 0.15 * (S - Yp)
        xw = Xp + wobble

        v = perlin_turbulence(xw, Yp / 2.0 + noise_y_time, noise_time, 2.0, 0.5, 3) * 2.0
        # Horizontal window (bright center, dark edges) + taper to the base.
        # Dividing the window arg by SIZE widens the bright band; scaling the
        # base ramp by SIZE saturates it lower down so the flame climbs higher.
        v *= triangle(0.5 + xw / (S * SIZE))
        v = np.maximum(0.0, v)
        v *= np.minimum(1.0, (Yp / S) * SIZE)
        v = np.minimum(v, 1.0)  # keep the palette from wrapping

        # paint(v, v*v): palette color at position v, brightness v*v.
        r = np.interp(v, PAL_POS, PAL_R)
        g = np.interp(v, PAL_POS, PAL_G)
        b = np.interp(v, PAL_POS, PAL_B)
        bri = (v * v) * MAX_BRIGHTNESS
        rgb = np.stack([r, g, b], axis=-1) * bri[:, None]
        for name, part in zip(self._names, np.split(rgb, self._splits)):
            frame[name][:] = part
