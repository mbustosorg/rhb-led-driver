"""Eiffel: the tower at night -- steady gold, glittering with white strobes.

The tower's lighting is a warm sodium gold; on the hour, some 20,000 white
strobe bulbs flash at random for a few minutes.  Here every pixel glows
gold, and each one independently fires a brief white flash at random
(a Poisson process, so flashes never fall into a rhythm) that fades back
to gold within a few frames.

The poof button is the hourly show: each press brings a burst of much
denser sparkle that eases back to the normal glitter.

Flashes are timed in seconds, not frames, so the look is the same at any
frame rate.
"""

import numpy as np

from rhb_led_driver.patterns.base import Pattern

# Behavioral knobs.
GOLD = np.array([1.0, 0.58, 0.12])  # sodium-lamp gold
GOLD_LEVEL = 0.2  # base glow; flashes go to full white, so they still stand out
GOLD_VARIATION = 0.12  # fixed per-bulb brightness spread, so the gold isn't flat
FLASH = np.array([1.0, 0.97, 0.9])  # strobe white, a touch warm
FLASHES_PER_SECOND = 0.5  # per pixel, normal glitter
FLASH_DECAY_S = 0.06  # time constant of a flash fading back to gold
BURST_SECONDS = 2.0  # a poof-button press: the hourly show
BURST_MULTIPLIER = 6.0  # flash rate at the start of a burst, easing back to 1x


class Eiffel(Pattern):
    name = "eiffel"

    def __init__(self, layout, rng=None):
        super().__init__(layout)
        self._rng = rng or np.random.default_rng()
        self._names = list(self.pos)
        self._splits = np.cumsum([len(self.pos[n]) for n in self._names])[:-1]
        n = sum(len(p) for p in self.pos.values())
        self._bulb = 1.0 + GOLD_VARIATION * self._rng.uniform(-1.0, 1.0, n)
        self._flash = np.zeros(n)  # 1.0 at the instant of a flash, decaying to 0
        self._last = None

    def _rate(self, sensors) -> float:
        since = sensors.since_rise("poof_button")
        if since is None or since >= BURST_SECONDS:
            return FLASHES_PER_SECOND
        ease = 1.0 - since / BURST_SECONDS
        return FLASHES_PER_SECOND * (1.0 + (BURST_MULTIPLIER - 1.0) * ease * ease)

    def render(self, now, sensors, frame):
        # Frame-rate independent; a long stall must not set every pixel off at once.
        dt = 0.0 if self._last is None else min(max(now - self._last, 0.0), 0.1)
        self._last = now

        self._flash *= np.exp(-dt / FLASH_DECAY_S)
        fired = self._rng.random(self._flash.shape) < self._rate(sensors) * dt
        self._flash[fired] = 1.0

        f = self._flash[:, None]
        gold = GOLD * (GOLD_LEVEL * self._bulb)[:, None]
        rgb = gold * (1.0 - f) + FLASH * f
        for name, part in zip(self._names, np.split(rgb, self._splits)):
            frame[name][:] = part
