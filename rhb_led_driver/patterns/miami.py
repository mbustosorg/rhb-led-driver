"""Miami: hot pink and electric blue, synthwave sunset on the water.  Ignores sensors.

gauge_matrix*  a retro sun sinking into the sea: the top is a hot pink sun
               cut by black slices that scroll down and widen toward the
               horizon; below it, electric blue water shimmers, with a pink
               streak of reflection under the sun
gauge_ring*    neon bands, pink and blue, the two rings spinning opposite ways
handle*        crossfade pink <-> blue
anything else  (hoses, connectors) pink and blue flowing outward, the upper
               and lower edges opposite colors

Everything but the sun pumps on a BPM beat.
"""

import numpy as np

from rhb_led_driver.adopted.pixelblaze import wave
from rhb_led_driver.patterns.base import Pattern

# Behavioral knobs -- tune here.
PINK = np.array([1.0, 0.08, 0.58])  # hot pink
BLUE = np.array([0.0, 0.55, 1.0])  # electric blue
BPM = 118.0
BEAT_DEPTH = 0.45  # how far the lights drop between beats
HORIZON = 0.42  # matrix height of the sea's edge, 0 bottom .. 1 top
SUN_SLICES = 7  # black slices across the sun
SUN_SLICE_SECONDS = 4.0  # for a slice to move down one slot
SUN_LEVEL = 0.6
SEA_LEVEL = 0.35
REFLECTION_WIDTH = 0.18  # of the matrix's width
RING_BANDS = 6
RING_SECONDS = 5.0  # one band's worth of spin
FLOW_SECONDS = 3.0  # one pink-blue cycle flowing past a point
FLOW_CYCLES = 2.0  # pink-blue cycles along a run
HANDLE_SECONDS = 4.0


def mix(a, b, t):
    """a where t is 0, b where t is 1, per pixel."""
    t = np.asarray(t)[..., None]
    return a * (1.0 - t) + b * t


class Miami(Pattern):
    name = "miami"

    def __init__(self, layout):
        super().__init__(layout)
        # 0..1 across and up the matrix, over all its bands together.
        matrix = [n for n in self.uv if n.startswith("gauge_matrix")]
        if matrix:
            uv = np.concatenate([self.uv[n] for n in matrix])
            lo, hi = uv.min(axis=0), uv.max(axis=0)
            span = np.where(hi - lo > 0, hi - lo, 1.0)
            self._across = {n: (self.uv[n][:, 0] - lo[0]) / span[0] for n in matrix}
            self._up = {n: (self.uv[n][:, 1] - lo[1]) / span[1] for n in matrix}

    def render(self, now, sensors, frame):
        beat = (now * BPM / 60.0) % 1.0
        pump = 1.0 - BEAT_DEPTH + BEAT_DEPTH * (1.0 - beat) ** 3

        for name, seg in frame.items():
            pos = self.pos[name]
            if name.startswith("gauge_matrix"):
                seg[:] = self._sunset(now, self._across[name], self._up[name])
            elif name.startswith("gauge_ring"):
                spin = now / RING_SECONDS * (1.0 if name.endswith("outer") else -1.0)
                t = np.clip((wave(pos * RING_BANDS + spin) - 0.5) * 4.0 + 0.5, 0.0, 1.0)  # sharp neon edges
                seg[:] = mix(PINK, BLUE, t) * pump
            elif name.startswith("handle"):
                seg[:] = mix(PINK, BLUE, wave(now / HANDLE_SECONDS + 0.5 * name.endswith("right"))) * pump
            else:
                offset = 0.5 if name.endswith("lower") else 0.0
                seg[:] = mix(PINK, BLUE, wave(pos * FLOW_CYCLES - now / FLOW_SECONDS + offset)) * pump

    def _sunset(self, now, across, up):
        out = np.zeros((len(up), 3))
        sky = up >= HORIZON
        # Sun: slices scroll down and get fatter as they near the horizon.
        height = (up[sky] - HORIZON) / (1.0 - HORIZON)
        slot = (height * SUN_SLICES + now / SUN_SLICE_SECONDS) % 1.0
        lit = slot >= 0.5 * (1.0 - height) ** 2
        out[sky] = PINK * SUN_LEVEL * lit[:, None]
        # Sea: shimmering blue, with the sun's pink streak down the middle.
        sea = ~sky
        depth = 1.0 - up[sea] / HORIZON
        shimmer = 0.4 + 0.6 * wave(across[sea] * 5.0 + depth * 9.0 - now * 0.7) * wave(depth * 23.0 + now * 0.4)
        streak = np.clip(1.0 - np.abs(across[sea] - 0.5) / (REFLECTION_WIDTH / 2.0), 0.0, 1.0)
        streak *= wave(depth * 14.0 + now * 1.3) > 0.55  # broken into ripples
        out[sea] = mix(BLUE * shimmer[:, None], PINK, streak * (1.0 - depth)) * SEA_LEVEL
        return out
