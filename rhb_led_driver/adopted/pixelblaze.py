# ADOPTED from lindsay-50 lib_shared/patterns/honeycomb.py @ c98fde6 -- edit freely.
# Extract: only the Pixelblaze primitives, made public; the Honeycomb effect itself is not here.
# Added: time_pb(), Pixelblaze time() in its own 65.536 s units (windfire / coronal_mass_ejection).
# --- end adoption header ---
"""Pixelblaze primitives, vectorized with numpy.

Pixelblaze primitives, mapped:
    time(i)     sawtooth 0..1, period i*65.536s  -> here: period passed in seconds
    wave(v)     (1 + sin(v*2pi)) / 2
    triangle(v) 1 - |1 - 2*frac(v)|
    hsv(h,s,v)  HSV->RGB, hue wraps mod 1
"""

import numpy as np

PI2 = 2.0 * np.pi


def time_saw(now, period_s):
    """Pixelblaze time(): a 0..1 sawtooth over `period_s` seconds."""
    return (now / period_s) % 1.0


PB_TIME_UNIT = 65.536  # Pixelblaze time(i) has period i * 65.536 s (2^16 ms)


def time_pb(now, interval):
    """Pixelblaze time(interval) exactly, for ports that keep the original's intervals."""
    return (now / (interval * PB_TIME_UNIT)) % 1.0


def wave(v):
    return (1.0 + np.sin(v * PI2)) * 0.5


def triangle(v):
    frac = v - np.floor(v)
    return 1.0 - np.abs(1.0 - 2.0 * frac)


def hsv_to_rgb(h, s, v):
    """Vectorized HSV->RGB. h,v are arrays in 0..1, s scalar; returns (...,3)."""
    h = (h % 1.0) * 6.0
    # np.choose in numpy 2.x requires int32 indices; int64 raises
    # "Cannot cast array data from dtype('int64') to dtype('int32')".
    i = np.floor(h).astype(np.int32)
    f = h - i
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    i = i % 6
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], axis=-1)
