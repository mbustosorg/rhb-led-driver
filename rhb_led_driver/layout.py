"""The LED segments on the car and where they live in sACN universe space."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

PIXELS_PER_UNIVERSE = 170  # 510 of 512 DMX channels, RGB


@dataclass(frozen=True)
class Segment:
    name: str
    pixels: int
    start_universe: int

    @property
    def universes(self) -> range:
        count = -(-self.pixels // PIXELS_PER_UNIVERSE)  # ceil
        return range(self.start_universe, self.start_universe + count)


@dataclass(frozen=True)
class Layout:
    host: str
    fps: float
    max_brightness: float
    segments: tuple[Segment, ...]

    def segment(self, name: str) -> Segment:
        for s in self.segments:
            if s.name == name:
                return s
        raise KeyError(name)


def load_layout(path: Path) -> Layout:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    controller = raw["controller"]
    segments = tuple(Segment(s["name"], int(s["pixels"]), int(s["start_universe"])) for s in raw["segment"])
    layout = Layout(
        host=controller["host"],
        fps=float(controller.get("fps", 40)),
        max_brightness=float(controller.get("max_brightness", 1.0)),
        segments=segments,
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
