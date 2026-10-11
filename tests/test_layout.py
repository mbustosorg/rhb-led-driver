from pathlib import Path

import pytest

from rhb_led_driver.layout import Layout, Segment, load_layout, validate

ROOT = Path(__file__).resolve().parent.parent


def test_shipped_layout_loads():
    layout = load_layout(ROOT / "config" / "layout.toml")
    assert {s.name for s in layout.segments} == {"hose", "handle", "gauge"}


def test_universe_span():
    assert list(Segment("a", 170, 1).universes) == [1]
    assert list(Segment("a", 171, 1).universes) == [1, 2]


def test_overlapping_universes_rejected():
    layout = Layout("h", 40, 1.0, (Segment("a", 300, 1), Segment("b", 10, 2)))
    with pytest.raises(ValueError, match="universe 2"):
        validate(layout)
