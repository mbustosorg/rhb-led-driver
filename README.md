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
      output.py         sACN to the F16V5, or nothing (--dry-run)
      patterns/         one file per pattern; registry in __init__.py
      adopted/          code copied from lindsay-50 -- see adopted/README.md
    config/layout.toml  pixel counts, universes, controller address, brightness cap
    scripts/adopted_drift.py   compare adopted code with lindsay-50

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

Control: `/led/pattern <name>` and `/led/brightness <0..1>`.

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
  address.  On the F16V5 set input to E1.31 and, per string port, the start
  universe and pixel count from `layout.toml`.

Output notes
------------

* One sACN universe = 170 RGB pixels; each segment starts on its own universe.
* `max_brightness` in `layout.toml` caps every pattern, before any OSC
  brightness: size it to the power supply.
* Unicast only, with no universe discovery and no E1.31 sync (see
  `output.py` for why sync is off).
* On SIGTERM / Ctrl-C the driver sends a black frame before exiting.
