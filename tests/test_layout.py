import tomllib
from pathlib import Path

import pytest

from rhb_led_driver.layout import PIXELS_PER_UNIVERSE, Layout, Segment, load_layout, validate

ROOT = Path(__file__).resolve().parent.parent


def test_shipped_layout_loads():
    path = ROOT / "config" / "layout.toml"
    with open(path, "rb") as f:
        names = [s["name"] for s in tomllib.load(f)["segment"]]
    layout = load_layout(path)
    assert [s.name for s in layout.segments] == names
    for s in layout.segments:
        assert s.xy.shape == (s.pixels, 2)


def test_universe_fits_in_sacn():
    # 512 DMX channels per universe, 3 per RGB pixel: 170 is the most there can be.
    # More and every real send fails ("max length of 512") while the simulator looks fine.
    assert PIXELS_PER_UNIVERSE * 3 <= 512


def test_universe_span():
    assert list(Segment("a", 170, 1).universes) == [1]
    assert list(Segment("a", 171, 1).universes) == [1, 2]


def test_overlapping_universes_rejected():
    layout = Layout("h", 40, 1.0, (Segment("a", 300, 1), Segment("b", 10, 2)))
    with pytest.raises(ValueError, match="universe 2"):
        validate(layout)
