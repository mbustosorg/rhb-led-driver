"""Where each pixel physically is: x,y for every pixel of a segment.

A segment's shape is given in layout.toml in one of three ways, in whatever
units you measure in (inches suggested) and in one shared frame for the
whole car, so patterns that work in space line up across segments:

    path = [[x, y], [x, y], ...]     polyline; pixels spaced evenly along it,
                                     first pixel on the first point, last on
                                     the last
    arc = { center = [x, y], radius = r, start_deg = a, end_deg = b }
                                     circular arc; 0 deg is +x, angles grow
                                     counterclockwise (y up), pixels run from
                                     start_deg to end_deg.  A full turn (360
                                     apart) spaces pixels evenly around the
                                     circle, with no doubled pixel at the seam.
    points_file = "handle.csv"       one "x,y" row per pixel, in pixel order;
                                     relative to layout.toml's directory.  For
                                     anything measured or exported from a
                                     mapping tool.
"""

import csv
from pathlib import Path

import numpy as np

SHAPE_KEYS = ("path", "arc", "points_file")


def path_points(points, n: int) -> np.ndarray:
    pts = np.asarray(points, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 2 or len(pts) < 2:
        raise ValueError("path needs at least two [x, y] points")
    seg_len = np.hypot(*np.diff(pts, axis=0).T)
    along = np.concatenate([[0.0], np.cumsum(seg_len)])
    if along[-1] == 0:
        raise ValueError("path has zero length")
    t = np.linspace(0.0, along[-1], n)
    return np.column_stack([np.interp(t, along, pts[:, 0]), np.interp(t, along, pts[:, 1])])


def arc_points(center, radius: float, start_deg: float, end_deg: float, n: int) -> np.ndarray:
    full_turn = abs(end_deg - start_deg) >= 360.0
    a = np.radians(np.linspace(start_deg, end_deg, n, endpoint=not full_turn))
    cx, cy = center
    return np.column_stack([cx + radius * np.cos(a), cy + radius * np.sin(a)])


def file_points(path: Path, n: int) -> np.ndarray:
    with open(path, newline="") as f:
        rows = [r for r in csv.reader(f) if r and not r[0].lstrip().startswith("#")]
    try:
        float(rows[0][0])
    except (ValueError, IndexError):
        rows = rows[1:]  # header row
    pts = np.array([[float(r[0]), float(r[1])] for r in rows])
    if len(pts) != n:
        raise ValueError(f"{path} has {len(pts)} points, segment has {n} pixels")
    return pts


def segment_points(raw: dict, n: int, base_dir: Path) -> np.ndarray:
    """x,y for each pixel of one [[segment]] table: shape (n, 2)."""
    given = [k for k in SHAPE_KEYS if k in raw]
    if len(given) != 1:
        raise ValueError(f"segment {raw.get('name')}: give exactly one of {', '.join(SHAPE_KEYS)}")
    if "path" in raw:
        return path_points(raw["path"], n)
    if "arc" in raw:
        arc = raw["arc"]
        return arc_points(arc["center"], float(arc["radius"]), float(arc["start_deg"]), float(arc["end_deg"]), n)
    return file_points(base_dir / raw["points_file"], n)


def segment_center(raw: dict, xy: np.ndarray) -> np.ndarray:
    """The middle of a segment: an arc's own center, else its bounding box's."""
    if "arc" in raw:
        return np.asarray(raw["arc"]["center"], dtype=float)
    return (xy.min(axis=0) + xy.max(axis=0)) / 2.0


def uv_transform(xy_by_segment: dict[str, np.ndarray]):
    """(origin, span) such that uv = (xy - origin) / span; see normalize()."""
    every = np.concatenate(list(xy_by_segment.values()))
    lo = every.min(axis=0)
    return lo, float((every.max(axis=0) - lo).max()) or 1.0


def normalize(xy_by_segment: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Map every segment into 0..1 on the car's longest axis, keeping aspect.

    One bounding box for all segments, so a pattern sees the car as one
    canvas: the same (u, v) on the hose and the gauge is the same place in
    the pattern.  The shorter axis spans less than 0..1.
    """
    lo, span = uv_transform(xy_by_segment)
    return {name: (xy - lo) / span for name, xy in xy_by_segment.items()}
