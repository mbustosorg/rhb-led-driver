"""Eiffel: the tower at night -- steady gold, glittering with white strobes.

The tower's lighting is a warm sodium gold; on the hour, some 20,000 white
strobe bulbs flash at random for a few minutes.  Here every pixel glows
gold, and each one independently fires a brief white flash at random
(a Poisson process, so flashes never fall into a rhythm) that fades back
to gold within a few frames.

The poof button is the hourly show: each press brings a burst of much
denser sparkle that eases back to the normal glitter.

The gauge's rings (gauge_ring*) are the beacon on top: a white beam sweeps
around them at a steady pace, and every so often breaks off to search --
darting to a few random headings, narrowing as it holds on each -- before
picking the rotation back up from wherever it ended.  The beam is a
critically damped spring chasing a target heading, so every start, stop and
turn eases in and out.

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
BEACON = np.array([1.0, 0.98, 0.92])  # xenon white
BEAMS = 1  # beams spread evenly around the rings (the real tower has four)
BEAM_WIDTH_DEG = 14.0  # angular spread (one standard deviation) while rotating
ROTATION_SECONDS = 8.0  # one clockwise turn in the regular sweep
SEARCH_EVERY_S = (12.0, 30.0)  # time between searches: random within this range
SEARCH_SECONDS = (3.0, 6.0)  # length of a search
SEARCH_DWELL_S = (0.4, 1.2)  # hold on each heading while searching
SEARCH_REACH_DEG = (25.0, 140.0)  # each new heading is this far from the last, either way
SEARCH_FOCUS = 0.6  # beam width while searching, as a fraction of the sweep width
SLEW = 7.0  # beam's spring stiffness (rad/s): higher snaps to a heading faster


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

        # Beacon: each ring pixel's index in the concatenated frame and its heading
        # around its ring's center (radians, layout xy so the circle stays round).
        start = dict(zip(self._names, np.concatenate([[0], self._splits])))
        rings = [s for s in layout.segments if s.name.startswith("gauge_ring")]
        self._ring_idx = (
            np.concatenate([start[s.name] + np.arange(s.pixels) for s in rings]).astype(int) if rings else None
        )
        if rings:
            self._ring_heading = np.concatenate([np.arctan2(*(s.xy - s.center).T[::-1]) for s in rings])
        self.heading = np.pi / 2  # the beam, unwrapped radians; starts at the top
        self._velocity = 0.0
        self._target = self.heading
        self._focus = 1.0
        self.searching = False
        self._next_search = self._search_end = self._next_dwell = None

    def _rate(self, sensors) -> float:
        since = sensors.since_rise("poof_button")
        if since is None or since >= BURST_SECONDS:
            return FLASHES_PER_SECOND
        ease = 1.0 - since / BURST_SECONDS
        return FLASHES_PER_SECOND * (1.0 + (BURST_MULTIPLIER - 1.0) * ease * ease)

    def _steer(self, now, dt):
        """Advance the beam: regular sweep, or a search's string of random headings."""
        if self._next_search is None:
            self._next_search = now + self._rng.uniform(*SEARCH_EVERY_S)
        if not self.searching and now >= self._next_search:
            self.searching, self._search_end, self._next_dwell = True, now + self._rng.uniform(*SEARCH_SECONDS), now
        if self.searching and now >= self._search_end:
            # Pick the rotation back up from where the search left the beam.
            self.searching, self._target = False, self.heading
            self._next_search = now + self._rng.uniform(*SEARCH_EVERY_S)
        if self.searching:
            if now >= self._next_dwell:
                reach = np.radians(self._rng.uniform(*SEARCH_REACH_DEG)) * self._rng.choice([-1.0, 1.0])
                self._target = self.heading + reach
                self._next_dwell = now + self._rng.uniform(*SEARCH_DWELL_S)
        else:
            self._target -= 2.0 * np.pi / ROTATION_SECONDS * dt  # clockwise, y up

        # Critically damped spring toward the target, in small steps so it stays stable.
        steps = max(1, int(np.ceil(dt / 0.01)))
        for _ in range(steps):
            h = dt / steps
            self._velocity += (SLEW * SLEW * (self._target - self.heading) - 2.0 * SLEW * self._velocity) * h
            self.heading += self._velocity * h
        focus = SEARCH_FOCUS if self.searching else 1.0
        self._focus += (focus - self._focus) * (1.0 - np.exp(-dt / 0.3))

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

        if self._ring_idx is not None:
            self._steer(now, dt)
            spacing = 2.0 * np.pi / BEAMS
            off = (self._ring_heading - self.heading + spacing / 2) % spacing - spacing / 2
            beam = np.exp(-0.5 * (off / np.radians(BEAM_WIDTH_DEG * self._focus)) ** 2)[:, None]
            rgb[self._ring_idx] = rgb[self._ring_idx] * (1.0 - beam) + BEACON * beam
        for name, part in zip(self._names, np.split(rgb, self._splits)):
            frame[name][:] = part
