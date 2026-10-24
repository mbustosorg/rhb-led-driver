"""Power limiting: keep each supply within its budget, frame by frame.

layout.toml gives each segment's watts at full white and each supply's
max_watts.  Every frame, the draw of a supply's segments is estimated from
what is about to be sent -- brightness included, each channel a third of a
pixel's full-white watts -- and if it is over budget the whole supply is
dimmed just enough to fit.  Ordinary frames are left alone; only bright
ones (solid white, a white flash) are pulled down.

The dimming drops at once, so the supply never sees the overload, and
eases back over RELEASE_SECONDS, so a frame that flickers around the
budget doesn't flicker the lights with it.
"""

import numpy as np

from rhb_led_driver.layout import Layout
from rhb_led_driver.output import Frame

# Behavioral knobs -- tune here.
RELEASE_SECONDS = 0.5  # time to recover from full dimming back to none


class PowerLimiter:
    def __init__(self, layout: Layout):
        self._supplies = [
            (p.name, p.max_watts, [(n, layout.segment(n).watts_per_pixel / 3.0) for n in p.segments])
            for p in layout.supplies
        ]
        self.scale = {p.name: 1.0 for p in layout.supplies}  # dimming applied last frame, 1 = none
        self.watts = {p.name: 0.0 for p in layout.supplies}  # estimated draw after dimming

    def apply(self, frame: Frame, brightness: float, dt: float) -> Frame:
        """The frame to send: `frame` itself, with dimmed copies of any over-budget supply's segments."""
        out = dict(frame)
        for name, max_watts, members in self._supplies:
            watts = brightness * sum(np.clip(frame[n], 0.0, 1.0).sum() * w for n, w in members)
            target = min(1.0, max_watts / watts) if watts > 0 else 1.0
            scale = target if target <= self.scale[name] else min(target, self.scale[name] + dt / RELEASE_SECONDS)
            self.scale[name] = scale
            self.watts[name] = watts * scale
            if scale < 1.0:
                for n, _ in members:
                    out[n] = frame[n] * scale
        return out

    def state(self) -> dict:
        return {
            name: {"watts": round(self.watts[name], 1), "max_watts": max_watts, "scale": round(self.scale[name], 3)}
            for name, max_watts, _ in self._supplies
        }
