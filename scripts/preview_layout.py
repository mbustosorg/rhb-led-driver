"""Draw the layout as an SVG: every pixel at its x,y, colored by a pattern.

Use it to check a new layout.toml (shapes, scale, wiring direction) and to
see what a pattern does in space, with no hardware.  Each segment's first
pixel is ringed and labeled, so a reversed run is obvious.

    python scripts/preview_layout.py                       # honeycomb, t=0
    python scripts/preview_layout.py -p instruments -t 3 \\
        -s /pressure=40 -s /temperature=150 -o preview.svg
"""

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rhb_led_driver.layout import load_layout  # noqa: E402
from rhb_led_driver.patterns import PATTERNS  # noqa: E402
from rhb_led_driver.patterns.base import blank_frame  # noqa: E402
from rhb_led_driver.sensors import SensorState  # noqa: E402

MARGIN = 12.0  # layout units around the drawing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--layout", type=Path, default=ROOT / "config" / "layout.toml")
    parser.add_argument("-p", "--pattern", default="honeycomb", choices=sorted(PATTERNS))
    parser.add_argument("-t", "--time", type=float, default=0.0, help="pattern time in seconds")
    parser.add_argument("-s", "--sensor", action="append", default=[], help="OSC address=value, repeatable")
    parser.add_argument("-o", "--out", type=Path, default=Path("layout-preview.svg"))
    args = parser.parse_args()

    layout = load_layout(args.layout)
    sensors = SensorState(clock=lambda: args.time)
    for item in args.sensor:
        address, _, value = item.partition("=")
        sensors.on_osc(address, float(value))
    frame = blank_frame(layout)
    PATTERNS[args.pattern](layout).render(args.time, sensors, frame)

    every = np.concatenate([s.xy for s in layout.segments])
    lo = every.min(axis=0) - MARGIN
    hi = every.max(axis=0) + MARGIN
    w, h = hi - lo
    # Pixel dots sized from the tightest spacing in the layout.
    gaps = [np.hypot(*np.diff(s.xy, axis=0).T).min() for s in layout.segments if s.pixels > 1]
    r = max(0.3, min(gaps, default=1.0) * 0.45)

    def y(v):  # SVG y grows downward; layout y grows up
        return hi[1] - v + lo[1]

    font = w / 50
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{lo[0]:.1f} {lo[1]:.1f} {w:.1f} {h:.1f}" '
        f'width="{min(1600, w * 6):.0f}" height="{min(1600, w * 6) * h / w:.0f}">',
        f'<rect x="{lo[0]:.1f}" y="{lo[1]:.1f}" width="{w:.1f}" height="{h:.1f}" fill="#111"/>',
        f'<text x="{lo[0] + font / 2:.1f}" y="{lo[1] + font * 1.2:.1f}" fill="#aaa" font-size="{font:.1f}" '
        f'font-family="sans-serif">{args.pattern}  t={args.time:g}s</text>',
    ]
    for seg in layout.segments:
        rgb = (np.clip(frame[seg.name], 0, 1) * 255).astype(int)
        # A faint outline, so pixels that are off still show where they are.
        for (px, py), (cr, cg, cb) in zip(seg.xy, rgb):
            out.append(
                f'<circle cx="{px:.2f}" cy="{y(py):.2f}" r="{r:.2f}" fill="rgb({cr},{cg},{cb})" '
                f'stroke="#333" stroke-width="{r / 5:.2f}"/>'
            )
        fx, fy = seg.xy[0]  # wiring starts here
        out.append(
            f'<circle cx="{fx:.2f}" cy="{y(fy):.2f}" r="{r * 3:.2f}" fill="none" stroke="#fff" '
            f'stroke-width="{r / 2:.2f}"/>'
        )
        out.append(
            f'<text x="{fx + r * 4:.2f}" y="{y(fy) + font * 1.2:.2f}" fill="#fff" font-size="{font * 0.8:.1f}" '
            f'font-family="sans-serif">{seg.name} ({seg.pixels})</text>'
        )
    out.append("</svg>")
    args.out.write_text("\n".join(out))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
