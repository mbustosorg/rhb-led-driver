RHB LED Driver
==============

Runs on a Raspberry Pi on the Red Hot Beverly and drives the pixels on the
overhead hose, the handle, and the 4' pressure gauge off the back, through a
Falcon F16V5 pixel controller.  Patterns react to what the car is doing,
using the sensor readings the rest of the rig already broadcasts over OSC.

    OSC (WiFi, port 8888)                       E1.31 / sACN (Ethernet)
    rhb-sensor-monitor  /pressure, /poof_count  ┐
    rhb-water-heater    /temperature, ...       ├─► this Pi ─► F16V5 ─► hose / handle / gauge
    TouchOSC            /led/pattern, ...       ┘

Layout
------

    rhb_led_driver/
      main.py           OSC server + fixed-rate render loop
      sensors.py        OSC address -> sensor name, staleness, button edges
      layout.py         segments and their sACN universes (config/layout.toml)
      geometry.py       x,y of every pixel from each segment's path / arc / CSV
      output.py         sACN to the F16V5, or nothing (--dry-run)
      simulator.py/.html  live browser view and controls (--sim)
      patterns/         one file per pattern; registry in __init__.py
      adopted/          code copied from lindsay-50 -- see adopted/README.md
    config/layout.toml  pixel counts, universes, controller address, brightness cap
    scripts/adopted_drift.py   compare adopted code with lindsay-50
    scripts/preview_layout.py  draw the layout, colored by a pattern, as an SVG

Setup
-----

Python 3.11+ (Raspberry Pi OS Bookworm ships it).

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt            # Pi
    .venv/bin/pip install -r requirements-dev.txt        # laptop: pytest, black
    cp settings.toml.example settings.toml

Run from the repo root (settings.toml is read from the cwd):

    .venv/bin/python -m rhb_led_driver --dry-run         # no sACN, no hardware
    .venv/bin/python -m rhb_led_driver
    .venv/bin/python -m pytest

Running at boot
---------------

`config/rhb_led_driver.service` runs the driver as `pi` out of
`/home/pi/rhb-led-driver` and restarts it 2 s after any exit, forever:

    sudo cp config/rhb_led_driver.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now rhb_led_driver
    journalctl -u rhb_led_driver -f        # logs

Stopping the service sends a black frame before exit.

Read-only SD card
-----------------

The car loses power without warning, which is what corrupts SD cards.
`scripts/setup-readonly.sh` makes the card read-only (a RAM overlay on top
of it) and puts the systemd journal on a USB stick, so the driver's logs
survive a power cut:

    lsblk -o NAME,TRAN,SIZE,LABEL           # find the stick, e.g. sda1
    sudo scripts/setup-readonly.sh --device /dev/sda1 --format
    sudo reboot
    journalctl -u rhb_led_driver            # now includes previous boots

The stick is mounted at `/data` (ext4, label `RHBDATA`) and `/var/log/journal`
is bind-mounted from `/data/journal`.  If the stick is missing the Pi still
boots and the lights still run; the journal just falls back to RAM.  The
driver itself writes no files, so it needs no `--app`/`--unit`.

To update code later, turn the overlay off first: `sudo raspi-config` ->
Performance Options -> Overlay File System -> No (and No to read-only boot),
reboot, `git pull`, turn it back on, reboot.  The same script, kept
identical, is in `rhb-sensor-monitor`.

Simulator
---------

    .venv/bin/python -m rhb_led_driver --sim --dry-run     # then open http://127.0.0.1:8080/

The real driver runs, and a page draws every pixel at its layout position,
live, exactly as sent to the F16V5 (brightness cap included).  The page can
switch patterns, set brightness and the solid color, and fake each sensor: tick **drive** to
send a value twice a second like the real senders, untick it to watch the
pattern fall back when the value goes stale, and hold the poof button (or
Space).  The page's controls go through the same routes as OSC, so TouchOSC
or the rig's real sensors can drive the simulator at the same time.

Without `--dry-run`, `--sim` also sends sACN, so on the car
`--sim --sim-host 0.0.0.0` shows what the lights are doing on a phone at
`http://<pi>:8080/`.  Only do that on the rig's own network: the page has
no login and anyone who can reach it can change the pattern.

Pixel positions
---------------

Every segment in `config/layout.toml` says where its pixels are, in one
shared frame for the whole car (inches, suggested), with exactly one of:

    path = [[20, 96], [90, 102], [160, 96]]     # polyline, pixels evenly spaced
    arc = { center = [200, 60], radius = 22, start_deg = 225, end_deg = -45 }
    disc = { center = [200, 60], radius = 20, pitch = 0.656, rows = [0, 15] }  # matrix rows in a circle
    points_file = "handle.csv"                  # one x,y row per pixel, measured

Pixels run in wiring order: the first pixel sits on the first path point, the
arc's `start_deg`, the disc's top-left row end (rows then serpentine), or the
CSV's first row.  Patterns get three views of each
segment (`patterns/base.py`): `pos` (0..1 along the run), `xy` (inches) and
`uv` (normalized over the whole car, Pixelblaze style), so a 2-D pattern
paints one picture across the hose, handle and gauge together.

Check a layout, or what a pattern does in space, with no hardware:

    .venv/bin/python scripts/preview_layout.py -p honeycomb -t 5 -o preview.svg
    .venv/bin/python scripts/preview_layout.py -p instruments -s /pressure=40 -s /temperature=150

Each segment's first pixel is ringed, so a run wired backwards shows up.

Sensors
-------

| Name | OSC address | Sender | Stale after |
| --- | --- | --- | --- |
| `accumulator_pressure` | `/pressure` | rhb-sensor-monitor | 3 s |
| `poof_count` | `/poof_count` | rhb-sensor-monitor | 30 s |
| `water_temp` | `/temperature` | rhb-water-heater | 30 s |
| `water_heater_on` | `/water_heater` | rhb-water-heater | 30 s |
| `poof_button` | `/poof_button` | **nothing yet** (1 = pressed, 0 = released) | never |

Add a sensor with one line in `sensors.SENSORS`.  Patterns read
`sensors.get(name, default)`, which returns the default once a value goes
stale, so a sender dropping off the network gives a fallback look instead of
a frozen one.  `sensors.since_rise(name)` gives the time since the last
press of a button-style input.

Control: `/led/pattern <name>`, `/led/brightness <0..1>`, and `/led/color <#rrggbb>`
(the `solid` pattern's color; three floats 0..1 also work).

Joining the rig
---------------

* **Give the Pi a static address** on the 192.168.1.x WiFi; there is no DHCP.
  Add it to `rhb-sensor-monitor/config/network.txt`.
* **Add that address to every sender's listener list**:
  rhb-sensor-monitor `--client_ip` and the water heater's `MOBILE_CLIENTS`.
* **Turn WiFi power save off** (`iw wlan0 set power_save off`, persisted).
  The water heater's W5500 gives up on ARP inside each send, so a dozing
  listener silently misses `/temperature`.
* **F16V5 on the Pi's Ethernet**, statically addressed; set `host` in
  `config/layout.toml` and, if needed, `SACN_BIND_IP` to the Pi's Ethernet
  address.  (`F16V5_HOST` in settings.toml overrides `host` for a
  controller elsewhere, such as a test bench on a home network.)  On the
  F16V5 set input to E1.31 and, per string port, the start
  universe and pixel count from `layout.toml`.

Output notes
------------

* One sACN universe = 170 RGB pixels; each segment starts on its own universe.
* `max_brightness` in `layout.toml` caps every pattern, before any OSC
  brightness: size it to the power supply.
* Unicast only, with no universe discovery and no E1.31 sync (see
  `output.py` for why sync is off).
* On SIGTERM / Ctrl-C the driver sends a black frame before exiting.
