from pathlib import Path

import numpy as np
import pytest

from rhb_led_driver.layout import load_layout
from rhb_led_driver.patterns.base import blank_frame
from rhb_led_driver.patterns.eiffel import Eiffel
from rhb_led_driver.sensors import SensorState

LAYOUT = load_layout(Path(__file__).resolve().parent.parent / "config" / "layout.toml")


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


def sparkle(press: bool, seconds=2.0, fps=40):
    """Mean fraction of glitter pixels flashing (blue channel high: gold has little blue)."""
    clock = Clock()
    sensors = SensorState(clock=clock)
    pattern = Eiffel(LAYOUT, rng=np.random.default_rng(1))
    frame = blank_frame(LAYOUT)
    if press:
        sensors.on_osc("/poof", 1)
    lit = []
    for i in range(int(seconds * fps)):
        clock.t = i / fps
        pattern.render(clock.t, sensors, frame)
        rgb = np.concatenate([v for k, v in frame.items() if not k.startswith("gauge_ring")])  # not the beacon
        lit.append(np.mean(rgb[:, 2] > 0.5))
    return np.mean(lit)


def test_first_frame_is_steady_gold():
    pattern = Eiffel(LAYOUT, rng=np.random.default_rng(1))
    frame = blank_frame(LAYOUT)
    pattern.render(5.0, SensorState(), frame)
    rgb = np.concatenate([v for k, v in frame.items() if not k.startswith("gauge_ring")])  # not the beacon
    assert (rgb[:, 0] > rgb[:, 1]).all() and (rgb[:, 1] > rgb[:, 2]).all()  # gold, no flashes yet


def test_glitters_and_poof_button_brings_the_show():
    normal = sparkle(press=False)
    show = sparkle(press=True)
    assert 0.005 < normal < 0.1
    assert show > 2.5 * normal


def beacon_run(seconds, fps=40, seed=3):
    pattern = Eiffel(LAYOUT, rng=np.random.default_rng(seed))
    frame, sensors = blank_frame(LAYOUT), SensorState()
    track = []
    for i in range(int(seconds * fps)):
        pattern.render(i / fps, sensors, frame)
        track.append((pattern.heading, pattern.searching))
    return pattern, frame, track


def test_beacon_sweeps_clockwise_at_the_regular_pace():
    from rhb_led_driver.patterns.eiffel import ROTATION_SECONDS, SEARCH_EVERY_S

    _, _, track = beacon_run(SEARCH_EVERY_S[0])  # before any search can start
    headings = np.array([h for h, _ in track])
    rate = (headings[-1] - headings[200]) / ((len(headings) - 1 - 200) / 40)  # past the spin-up
    assert not any(s for _, s in track)
    assert rate == pytest.approx(-2 * np.pi / ROTATION_SECONDS, rel=0.02)


def test_beacon_searches_then_returns_to_its_sweep_without_jumping():
    from rhb_led_driver.patterns.eiffel import ROTATION_SECONDS

    _, frame, track = beacon_run(90)
    searching = [s for _, s in track]
    starts = [i for i in range(1, len(searching)) if searching[i] and not searching[i - 1]]
    ends = [i for i in range(1, len(searching)) if searching[i - 1] and not searching[i]]
    assert starts and ends and ends[0] > starts[0]
    assert 3 * 40 <= ends[0] - starts[0] <= 6 * 40 + 1
    headings = np.array([h for h, _ in track])
    assert np.abs(np.diff(headings)).max() < np.radians(15)  # eased, never teleports
    # Two seconds after a search, it is sweeping clockwise at the regular pace again.
    after = headings[ends[0] + 80 : ends[0] + 160]
    assert np.diff(after).mean() * 40 == pytest.approx(-2 * np.pi / ROTATION_SECONDS, rel=0.1)
    ring = frame["gauge_ring_outer"]
    beam = (ring[:, 2] > 0.9) & (ring[:, 2] > ring[:, 0])
    assert beam.sum() > 5  # a blue-white beam on the ring


def test_no_rings_no_beacon():
    from rhb_led_driver.layout import Layout

    layout = Layout("h", 40, 1.0, tuple(s for s in LAYOUT.segments if not s.name.startswith("gauge_ring")))
    frame = blank_frame(layout)
    Eiffel(layout, rng=np.random.default_rng(1)).render(1.0, SensorState(), frame)
