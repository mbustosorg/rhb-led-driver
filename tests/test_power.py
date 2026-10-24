from pathlib import Path

import numpy as np
import pytest

from rhb_led_driver.layout import load_layout
from rhb_led_driver.patterns.base import blank_frame
from rhb_led_driver.power import RELEASE_SECONDS, PowerLimiter

ROOT = Path(__file__).resolve().parent.parent

LAYOUT_TOML = """
[controller]
host = "127.0.0.1"

[power]
watts_per_pixel = 0.3

[[segment]]
name = "gauge_a"
pixels = 100
start_universe = 1
path = [[0, 0], [10, 0]]

[[segment]]
name = "gauge_b"
pixels = 100
start_universe = 2
watts_per_pixel = 0.6
path = [[0, 1], [10, 1]]

[[segment]]
name = "hose"
pixels = 50
start_universe = 3
path = [[0, 2], [10, 2]]

[[supply]]
name = "gauge"
max_watts = 45
segments = ["gauge_*"]
"""


def layout(tmp_path, text=LAYOUT_TOML):
    path = tmp_path / "layout.toml"
    path.write_text(text)
    return load_layout(path)


def white(lay):
    frame = blank_frame(lay)
    for seg in frame.values():
        seg[:] = 1.0
    return frame


def test_supply_resolves_patterns_and_per_segment_watts(tmp_path):
    lay = layout(tmp_path)
    assert lay.supplies[0].segments == ("gauge_a", "gauge_b")
    assert lay.segment("gauge_b").watts_per_pixel == 0.6
    assert lay.segment("hose").watts_per_pixel == 0.3


@pytest.mark.parametrize(
    "change, error",
    [
        ('segments = ["gauge_*"]', 'segments = ["nope"]'),
        ("max_watts = 45", "max_watts = 0"),
    ],
)
def test_bad_supply_rejected(tmp_path, change, error):
    with pytest.raises(ValueError):
        layout(tmp_path, LAYOUT_TOML.replace(change, error))


def test_segment_on_two_supplies_rejected(tmp_path):
    extra = '\n[[supply]]\nname = "more"\nmax_watts = 10\nsegments = ["gauge_a"]\n'
    with pytest.raises(ValueError, match="both supply"):
        layout(tmp_path, LAYOUT_TOML + extra)


def test_over_budget_is_dimmed_to_fit_and_the_rest_left_alone(tmp_path):
    lay = layout(tmp_path)
    frame = white(lay)
    limiter = PowerLimiter(lay)
    out = limiter.apply(frame, 0.5, 0.025)  # 0.5 * (100*0.3 + 100*0.6) = 45 W: exactly at budget
    assert limiter.scale["gauge"] == 1.0 and out["gauge_a"] is frame["gauge_a"]
    out = limiter.apply(frame, 1.0, 0.025)  # 90 W asked of a 45 W supply
    assert limiter.scale["gauge"] == pytest.approx(0.5)
    assert limiter.watts["gauge"] == pytest.approx(45.0)
    assert np.allclose(out["gauge_a"], 0.5) and np.allclose(out["gauge_b"], 0.5)
    assert out["hose"] is frame["hose"]  # on no supply
    assert np.allclose(frame["gauge_a"], 1.0)  # the pattern's own frame is not touched


def test_dimming_eases_back(tmp_path):
    lay = layout(tmp_path)
    limiter = PowerLimiter(lay)
    limiter.apply(white(lay), 1.0, 0.025)
    dark = blank_frame(lay)
    limiter.apply(dark, 1.0, RELEASE_SECONDS / 4)
    assert limiter.scale["gauge"] == pytest.approx(0.75)
    for _ in range(4):
        limiter.apply(dark, 1.0, RELEASE_SECONDS / 4)
    assert limiter.scale["gauge"] == 1.0


def test_shipped_gauge_white_stays_within_budget():
    lay = load_layout(ROOT / "config" / "layout.toml")
    limiter = PowerLimiter(lay)
    limiter.apply(white(lay), lay.max_brightness, 1.0 / lay.fps)
    for p in lay.supplies:
        assert limiter.watts[p.name] <= p.max_watts + 1e-6
