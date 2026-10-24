"""The LED segments on the car, where they live in sACN universe space, and what powers them."""

import fnmatch
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from rhb_led_driver.geometry import segment_center, segment_points

PIXELS_PER_UNIVERSE = 170  # 510 of 512 DMX channels, RGB; a universe can never hold more


@dataclass(frozen=True)
class Segment:
    name: str
    pixels: int
    start_universe: int
    # (pixels, 2) physical x,y of each pixel; see geometry.py
    xy: np.ndarray | None = field(default=None, compare=False, repr=False)
    # Its middle, same units: an arc's center, else the bounding box's.
    center: np.ndarray | None = field(default=None, compare=False, repr=False)
    watts_per_pixel: float = 0.0  # one pixel at full white

    @property
    def universes(self) -> range:
        count = -(-self.pixels // PIXELS_PER_UNIVERSE)  # ceil
        return range(self.start_universe, self.start_universe + count)


@dataclass(frozen=True)
class Supply:
    """A power supply's budget: its segments together may draw at most max_watts."""

    name: str
    max_watts: float
    segments: tuple[str, ...]


@dataclass(frozen=True)
class Layout:
    host: str
    fps: float
    max_brightness: float
    segments: tuple[Segment, ...]
    supplies: tuple[Supply, ...] = ()

    def segment(self, name: str) -> Segment:
        for s in self.segments:
            if s.name == name:
                return s
        raise KeyError(name)


def load_layout(path: Path) -> Layout:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    controller = raw["controller"]
    watts = float(raw.get("power", {}).get("watts_per_pixel", 0.0))
    segments = []
    for s in raw["segment"]:
        xy = segment_points(s, int(s["pixels"]), path.parent)
        wpp = float(s.get("watts_per_pixel", watts))
        segments.append(Segment(s["name"], int(s["pixels"]), int(s["start_universe"]), xy, segment_center(s, xy), wpp))
    segments = tuple(segments)
    names = [s.name for s in segments]
    supplies = []
    for p in raw.get("supply", []):
        # Segment names or shell-style patterns ("gauge_*"), in layout order.
        members = [n for n in names if any(fnmatch.fnmatchcase(n, pat) for pat in p["segments"])]
        for pat in p["segments"]:
            if not any(fnmatch.fnmatchcase(n, pat) for n in names):
                raise ValueError(f"supply {p['name']}: no segment matches {pat!r}")
        supplies.append(Supply(p["name"], float(p["max_watts"]), tuple(members)))
    layout = Layout(
        host=controller["host"],
        fps=float(controller.get("fps", 40)),
        max_brightness=float(controller.get("max_brightness", 1.0)),
        segments=segments,
        supplies=tuple(supplies),
    )
    validate(layout)
    return layout


def validate(layout: Layout) -> None:
    """Fail at startup, not on the playa, if two segments share a universe."""
    names = [s.name for s in layout.segments]
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate segment names: {names}")
    owner: dict[int, str] = {}
    for s in layout.segments:
        if s.pixels <= 0 or s.start_universe < 1:
            raise ValueError(f"segment {s.name}: pixels and start_universe must be positive")
        for u in s.universes:
            if u in owner:
                raise ValueError(f"universe {u} used by both {owner[u]} and {s.name}")
            owner[u] = s.name
    if not 0.0 <= layout.max_brightness <= 1.0:
        raise ValueError("max_brightness must be within 0..1")
    powered: dict[str, str] = {}
    for p in layout.supplies:
        if p.max_watts <= 0:
            raise ValueError(f"supply {p.name}: max_watts must be positive")
        for n in p.segments:
            if n in powered:
                raise ValueError(f"segment {n} is on both supply {powered[n]} and {p.name}")
            powered[n] = p.name
            if layout.segment(n).watts_per_pixel <= 0:
                raise ValueError(f"supply {p.name}: segment {n} needs watts_per_pixel ([power] or the segment)")
