# CLAUDE.md

See README.md for what this is and how it fits the RHB rig.

- `rhb_led_driver/adopted/` holds code copied from `../lindsay-50`. Never import from or path-link to lindsay-50. Adopt by copying with the header and a `manifest.toml` entry (see `adopted/README.md`); check drift with `python scripts/adopted_drift.py`.
- Time intervals use `time.monotonic()`; the rig Pis boot with a wrong wall clock until GPS sets it.
- The rig is statically addressed (no DHCP). WiFi listeners must have power save off.
- Behavioral knobs live as constants at the top of each pattern file; deployment settings in `settings.toml`; physical layout in `config/layout.toml`.
- Run tests with `.venv/bin/python -m pytest`; format with black (line length 120).
- `scripts/setup-readonly.sh` is kept identical in rhb-sensor-monitor; change both.
