# Code adopted from lindsay-50

Files here were copied out of `lindsay-50`, not imported from it.  This
project has no runtime or install-time dependency on lindsay-50, so a change
over there can never break the car, and nothing here is off limits to edit.

## Rules

1. **Copy, don't link.**  No submodule, no `pip install` from the other repo,
   no `sys.path` tricks.
2. **Every adopted file starts with the adoption header** (source path and
   commit) ending at `# --- end adoption header ---`, and has an entry in
   `manifest.toml`.  Shared helpers live here in `adopted/`; ported patterns
   live with the other patterns in `rhb_led_driver/patterns/`.
3. **Edit freely.**  Once adopted, the file is ours.  If you change something
   worth keeping, note it in the header's second line.
4. **Check drift before pulling upstream fixes:**

       python scripts/adopted_drift.py            # summary
       python scripts/adopted_drift.py --diff     # full diffs

   For each file it reports *ours* (our edits since the pinned commit) and
   *upstream* (lindsay-50 changes since the pinned commit).  Merge by hand,
   then bump `commit` in `manifest.toml`.

## Adopting another file

    cp ../lindsay-50/lib_shared/<file>.py rhb_led_driver/adopted/
    # add the 3-line header, add a [[file]] entry to manifest.toml

Fix its imports (`lib_shared.x` becomes `rhb_led_driver.adopted.x`) and
record that in the header.  If only part of a file is useful, take that part
and mark it `mode = "extract"`.

## Porting a lindsay-50 pattern

The sign's patterns compute a color for every (x, y) of a 64x64 panel.  Here
the same math runs at each pixel's `self.uv` (see `patterns/base.py`), so a
port is mostly: replace the meshgrid with the concatenated uv of all
segments, take time from `render(now, ...)`, write the result into
`frame[segment]`, and drop `set_brightness` (output.py handles brightness).
`patterns/honeycomb.py` is the worked example.  Mark it `mode = "port"`.

## What was taken, and what was not

| File | From | Why |
| --- | --- | --- |
| `config_reader.py` | `lib_shared/config_reader.py` | `settings.toml` plus env-var override, fail-fast on missing keys, secrets masked in the log |
| `log_setup.py` | `lib_shared/log_setup.py` | Same log format and Pacific timestamps as the sign |
| `pixelblaze.py` | `lib_shared/patterns/honeycomb.py` (extract) | `wave` / `triangle` / `hsv_to_rgb`, vectorized |
| `../patterns/honeycomb.py` | `lib_shared/patterns/honeycomb.py` (port) | The honeycomb pattern on pixel coordinates |
| `perlin.py` | `lib_shared/patterns/windfire.py` (extract) | Perlin noise and fractal turbulence, for the noise-based patterns |
| `../patterns/coronal_mass_ejection.py` | `lib_shared/patterns/coronal_mass_ejection.py` (port) | The star-and-flares pattern, centered on the gauge |

**Not taken: `effect_base.py` / `display_base.py`.**  Those model a 2-D
HUB75 matrix (a `Bitmap` of palette indices blitted with `SetPixel`).  The
F16V5 drives 1-D pixel strings, so patterns here render straight into numpy
`(pixels, 3)` arrays per segment (`rhb_led_driver/patterns/base.py`).  The
lindsay-50 *patterns* port onto pixel coordinates instead; see "Porting a lindsay-50 pattern" above.
