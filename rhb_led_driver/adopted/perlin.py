# ADOPTED from lindsay-50 lib_shared/patterns/windfire.py @ c98fde6 -- edit freely.
# Extract: the Perlin noise primitives only, made public (_perlin -> perlin, ...).
# _TIME_UNIT left out: it is pixelblaze.PB_TIME_UNIT.
# --- end adoption header ---
"""Improved Perlin noise and fractal turbulence, vectorized with numpy.

Pixelblaze's perlin(x, y, z, seed) and perlinTurbulence(...), as used by the
sign's windfire and coronal-mass-ejection patterns.  x and y are arrays, z a
scalar (usually time).  The lattice wraps every 256.
"""

import numpy as np

# Standard Ken Perlin permutation table, doubled to 512 so index+offset math
# never runs off the end.
PERM = np.array(
    [
        151,
        160,
        137,
        91,
        90,
        15,
        131,
        13,
        201,
        95,
        96,
        53,
        194,
        233,
        7,
        225,
        140,
        36,
        103,
        30,
        69,
        142,
        8,
        99,
        37,
        240,
        21,
        10,
        23,
        190,
        6,
        148,
        247,
        120,
        234,
        75,
        0,
        26,
        197,
        62,
        94,
        252,
        219,
        203,
        117,
        35,
        11,
        32,
        57,
        177,
        33,
        88,
        237,
        149,
        56,
        87,
        174,
        20,
        125,
        136,
        171,
        168,
        68,
        175,
        74,
        165,
        71,
        134,
        139,
        48,
        27,
        166,
        77,
        146,
        158,
        231,
        83,
        111,
        229,
        122,
        60,
        211,
        133,
        230,
        220,
        105,
        92,
        41,
        55,
        46,
        245,
        40,
        244,
        102,
        143,
        54,
        65,
        25,
        63,
        161,
        1,
        216,
        80,
        73,
        209,
        76,
        132,
        187,
        208,
        89,
        18,
        169,
        200,
        196,
        135,
        130,
        116,
        188,
        159,
        86,
        164,
        100,
        109,
        198,
        173,
        186,
        3,
        64,
        52,
        217,
        226,
        250,
        124,
        123,
        5,
        202,
        38,
        147,
        118,
        126,
        255,
        82,
        85,
        212,
        207,
        206,
        59,
        227,
        47,
        16,
        58,
        17,
        182,
        189,
        28,
        42,
        223,
        183,
        170,
        213,
        119,
        248,
        152,
        2,
        44,
        154,
        163,
        70,
        221,
        153,
        101,
        155,
        167,
        43,
        172,
        9,
        129,
        22,
        39,
        253,
        19,
        98,
        108,
        110,
        79,
        113,
        224,
        232,
        178,
        185,
        112,
        104,
        218,
        246,
        97,
        228,
        251,
        34,
        242,
        193,
        238,
        210,
        144,
        12,
        191,
        179,
        162,
        241,
        81,
        51,
        145,
        235,
        249,
        14,
        239,
        107,
        49,
        192,
        214,
        31,
        181,
        199,
        106,
        157,
        184,
        84,
        204,
        176,
        115,
        121,
        50,
        45,
        127,
        4,
        150,
        254,
        138,
        236,
        205,
        93,
        222,
        114,
        67,
        29,
        24,
        72,
        243,
        141,
        128,
        195,
        78,
        66,
        215,
        61,
        156,
        180,
    ],
    dtype=np.int32,
)
P = np.concatenate([PERM, PERM])


def fade(t):
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def lerp(t, a, b):
    return a + t * (b - a)


def grad(h, x, y, z):
    """Improved-Perlin gradient dot product (12 edge gradients)."""
    h = h & 15
    u = np.where(h < 8, x, y)
    v = np.where(h < 4, y, np.where((h == 12) | (h == 14), x, z))
    return np.where(h & 1 == 0, u, -u) + np.where(h & 2 == 0, v, -v)


def perlin(x, y, z):
    """3D improved Perlin noise. x, y are arrays; z a scalar. Wraps every 256."""
    xi = np.floor(x).astype(np.int32) & 255
    yi = np.floor(y).astype(np.int32) & 255
    zi = int(np.floor(z)) & 255
    xf = x - np.floor(x)
    yf = y - np.floor(y)
    zf = z - np.floor(z)
    u = fade(xf)
    v = fade(yf)
    w = fade(zf)

    A = P[xi] + yi
    AA = P[A] + zi
    AB = P[A + 1] + zi
    B = P[xi + 1] + yi
    BA = P[B] + zi
    BB = P[B + 1] + zi

    x1 = lerp(u, grad(P[AA], xf, yf, zf), grad(P[BA], xf - 1, yf, zf))
    x2 = lerp(u, grad(P[AB], xf, yf - 1, zf), grad(P[BB], xf - 1, yf - 1, zf))
    y1 = lerp(v, x1, x2)
    x3 = lerp(u, grad(P[AA + 1], xf, yf, zf - 1), grad(P[BA + 1], xf - 1, yf, zf - 1))
    x4 = lerp(u, grad(P[AB + 1], xf, yf - 1, zf - 1), grad(P[BB + 1], xf - 1, yf - 1, zf - 1))
    y2 = lerp(v, x3, x4)
    return lerp(w, y1, y2)


def perlin_turbulence(x, y, z, lacunarity, gain, octaves):
    """Fractal turbulence: sum of |perlin| across octaves (Pixelblaze order)."""
    total = np.zeros_like(x)
    freq = 1.0
    amp = 1.0
    for _ in range(octaves):
        total += np.abs(perlin(x * freq, y * freq, z * freq)) * amp
        freq *= lacunarity
        amp *= gain
    return total
