# ADOPTED from lindsay-50 lib_shared/patterns/coronal_mass_ejection.py @ c98fde6 -- edit freely.
# Port: radial coords from pixel uv around a chosen segment's center (the gauge's dial) instead of the panel's.
# --- end adoption header ---
"""CoronalMassEjection -- a port of a Pixelblaze 2D pattern (ZRanger1 / wizard).

A white-hot star throws off Perlin-turbulence "flares" that churn and
occasionally fling super-hot bits outward.  The pattern works in radial
coordinates: each pixel's angle drives one noise axis and its radius the
other, so the noise field wraps seamlessly around the star.

On the sign the star sat in the middle of the panel.  Here it sits in the
center of CENTER (the gauge's dial, by default), scaled so that segment's
farthest pixel lands at RIM: the dial's ring of pixels becomes the star's ring of flares,
and the hose and handle catch the flares flung further out.

Pixelblaze primitives, mapped:
    time(i)                 sawtooth 0..1, period i*65.536s
    hypot / atan2           radial coordinate conversion
    setPerlinWrap(x,y,z)    make Perlin periodic with those integer periods
    perlinTurbulence(...)   sum of |perlin| over octaves (fractal turbulence)
    smoothstep(e0,e1,v)     Hermite edge ramp, clamped to [0,1]
    hsv(h,s,v)              HSV->RGB, hue wraps mod 1

The angular axis is scaled so its full sweep (-pi..pi) spans exactly the
Perlin x-wrap period (DENSITY), which is what makes the ring of flares
join without a seam.
"""

import numpy as np

from rhb_led_driver.adopted.perlin import P, fade, grad, lerp
from rhb_led_driver.adopted.pixelblaze import hsv_to_rgb, time_pb
from rhb_led_driver.patterns.base import Pattern

# Behavioral knobs: the original's UI controls, plus where the star sits.
CENTER = "gauge"  # segment the star is centered on; None = the middle of the whole car
RIM = 0.35  # radius CENTER's farthest pixel lands at, in the sign's units (its panel was -0.5..0.5)
TF = 1.0  # animation speed: <1 slower, >1 faster
DENSITY = 6  # flares around the ring
GAIN = 0.25  # fractal gain
ITERATIONS = 3  # turbulence octaves
MIRROR = False
CUTOFF = 0.675  # higher = fewer, sharper flares
MAX_BRIGHTNESS = 0.8
CORE_SIZE = 0.1


def _smoothstep(edge0, edge1, x):
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _perlin_wrapped(x, y, z, wx, wy, wz):
    """3D Perlin noise periodic with integer periods (wx, wy, wz).

    Lattice indices are taken modulo the wrap period before hashing, so the
    +1 neighbour of the last cell hashes to cell 0 -- the noise tiles
    seamlessly. x, y are arrays; z a scalar. Mirrors Pixelblaze's
    setPerlinWrap behaviour.
    """
    x0 = np.floor(x)
    y0 = np.floor(y)
    z0 = np.floor(z)
    xf = x - x0
    yf = y - y0
    zf = z - z0
    xi0 = x0.astype(np.int32) % wx
    xi1 = (x0.astype(np.int32) + 1) % wx
    yi0 = y0.astype(np.int32) % wy
    yi1 = (y0.astype(np.int32) + 1) % wy
    zi0 = int(z0) % wz
    zi1 = (int(z0) + 1) % wz
    u = fade(xf)
    v = fade(yf)
    w = fade(zf)

    def h(xi, yi, zi):
        # Every index stays < len(P) (512): P[..] <= 255, +yi/+zi <= 510.
        return P[P[P[xi] + yi] + zi]

    x1 = lerp(u, grad(h(xi0, yi0, zi0), xf, yf, zf), grad(h(xi1, yi0, zi0), xf - 1, yf, zf))
    x2 = lerp(u, grad(h(xi0, yi1, zi0), xf, yf - 1, zf), grad(h(xi1, yi1, zi0), xf - 1, yf - 1, zf))
    y1 = lerp(v, x1, x2)
    x3 = lerp(u, grad(h(xi0, yi0, zi1), xf, yf, zf - 1), grad(h(xi1, yi0, zi1), xf - 1, yf, zf - 1))
    x4 = lerp(u, grad(h(xi0, yi1, zi1), xf, yf - 1, zf - 1), grad(h(xi1, yi1, zi1), xf - 1, yf - 1, zf - 1))
    y2 = lerp(v, x3, x4)
    return lerp(w, y1, y2)


def _perlin_turbulence_wrapped(x, y, z, lacunarity, gain, octaves, wx, wy, wz):
    """Fractal turbulence over the wrapped Perlin. Coords scale by frequency;
    the wrap period stays fixed so every octave stays seam-continuous (the
    angular span is an integer multiple of `wx`)."""
    total = np.zeros_like(x)
    freq = 1.0
    amp = 1.0
    for _ in range(octaves):
        total += np.abs(_perlin_wrapped(x * freq, y * freq, z * freq, wx, wy, wz)) * amp
        freq *= lacunarity
        amp *= gain
    return total


class CoronalMassEjection(Pattern):
    name = "coronal_mass_ejection"

    def __init__(self, layout):
        super().__init__(layout)
        self._names = list(self.uv)
        uv = np.concatenate([self.uv[n] for n in self._names])
        self._splits = np.cumsum([len(self.uv[n]) for n in self._names])[:-1]

        # Center and scale: the star in CENTER's middle with its farthest pixel at
        # RIM; for the whole car, the sign's own scale (uv span 1 = panel span 1).
        if CENTER:
            center = self.center_uv[CENTER]
            reach = float(np.hypot(*(self.uv[CENTER] - center).T).max())
            scale = RIM / reach if reach > 0 else 1.0
        else:
            center, scale = (uv.min(axis=0) + uv.max(axis=0)) / 2.0, 1.0
        rel = (uv - center) * scale
        self._radius = np.hypot(rel[:, 0], rel[:, 1])
        self._angle = np.arctan2(rel[:, 1], rel[:, 0])
        self._c2 = CORE_SIZE / 4.0

    def render(self, now, sensors, frame):
        now = now * TF
        t1 = time_pb(now, 0.2)
        # perlin z/y wrap at 256, so sweeping across 0..256 loops seamlessly.
        noise_time = time_pb(now, 10.0) * 256.0
        noise_y_time = time_pb(now, 8.0) * 256.0

        # The angular axis is scaled so its -pi..pi sweep spans exactly the
        # x-wrap period (DENSITY) -- mirror doubles the sweep. That alignment
        # is what makes the ring of flares join without a seam.
        density_pi_conversion = (1.0 / np.pi) * DENSITY * (1.0 if MIRROR else 0.5)

        radius = self._radius
        xn = self._angle * density_pi_conversion

        # Wrap: x-period = DENSITY (the angular seam), y/z-period = 256 (time).
        v = 1.0 - _perlin_turbulence_wrapped(
            xn, radius - noise_y_time, noise_time, 2.0, GAIN, ITERATIONS, DENSITY, 256, 256
        )

        # Discrete radial flares from the noise, plus an always-white-hot core
        # that blooms past 1 near the center (clamped when painted).
        core = 1.0 - ((radius * v) - self._c2) / CORE_SIZE
        v = np.maximum(_smoothstep(CUTOFF, 1.0, v), core)
        v = v * v * v

        # hsv(t1 - 0.125*v, 6.5*radius - v, v): hue drifts with time, saturation
        # rises with radius (white core), value is the flare intensity.
        hue = (t1 - 0.125 * v) % 1.0
        sat = np.clip(6.5 * radius - v, 0.0, 1.0)
        val = np.clip(v, 0.0, 1.0)

        rgb = np.clip(hsv_to_rgb(hue, sat, val) * MAX_BRIGHTNESS, 0.0, 1.0)
        for name, part in zip(self._names, np.split(rgb, self._splits)):
            frame[name][:] = part
