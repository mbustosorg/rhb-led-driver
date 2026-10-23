"""The poof overlay: drawn over whatever pattern is running.

Each press of the poof button sends a bright pulse from the gauge end of
every hose* segment out to the nozzle.  The pulse replaces the pattern's
color where it is, rather than adding to it, so it reads on a bright
pattern as well as a dark one.  A pattern with its own answer to the
button (own_poof, e.g. eiffel's show) is left alone.
"""

import numpy as np

# Behavioral knobs -- tune here.
PULSE_SECONDS = 1.0  # time for a poof pulse to travel the hose
PULSE_WIDTH = 0.08  # fraction of the hose lit by the pulse
PULSE_COLOR = np.array([1.0, 0.5, 0.0])


class PoofOverlay:
    def __init__(self, layout):
        self.pos = {s.name: np.linspace(0.0, 1.0, s.pixels) for s in layout.segments if s.name.startswith("hose")}

    def render(self, now, sensors, frame) -> None:
        since = sensors.since_rise("poof_button")
        if since is None or since >= PULSE_SECONDS:
            return
        head = since / PULSE_SECONDS
        for name, pos in self.pos.items():
            glow = np.clip(1.0 - np.abs(pos - head) / PULSE_WIDTH, 0.0, 1.0)[:, None]
            frame[name][:] = frame[name] * (1.0 - glow) + PULSE_COLOR * glow
