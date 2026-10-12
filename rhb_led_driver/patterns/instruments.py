"""Sensor-driven pattern: the car's state, shown on the car.

Segments are found by name, so new runs join in without code changes:

gauge     fills with accumulator pressure, in wiring order; color runs from
          blue at a cold bath to red at a hot one
handle*   breathe in the bath color; faster while the heater is on
hose*     a bright pulse runs from the gauge end out to the nozzle whenever
          the poof button is pressed
anything else (the connector) glows steadily in the bath color

Any sensor that is stale or has never reported falls back to a neutral
look rather than freezing on its last value.
"""

import numpy as np

from rhb_led_driver.adopted.pixelblaze import hsv_to_rgb, wave
from rhb_led_driver.patterns.base import Pattern

# Behavioral knobs -- tune here.
PRESSURE_FULL_PSI = 60.0
TEMP_COLD_F = 70.0
TEMP_HOT_F = 160.0
PULSE_SECONDS = 1.0  # time for a poof pulse to travel the hose
PULSE_WIDTH = 0.08  # fraction of the hose lit by the pulse
HUE_COLD, HUE_HOT = 0.66, 0.0  # blue, red
PULSE_COLOR = np.array([1.0, 0.5, 0.0])
CONNECTOR_LEVEL = 0.3


class Instruments(Pattern):
    name = "instruments"

    def render(self, now, sensors, frame):
        temp = sensors.get("water_temp")
        if temp is None:
            hue, sat = HUE_COLD, 0.0  # white: no bath data
        else:
            heat = np.clip((temp - TEMP_COLD_F) / (TEMP_HOT_F - TEMP_COLD_F), 0.0, 1.0)
            hue, sat = HUE_COLD + (HUE_HOT - HUE_COLD) * heat, 1.0
        color = hsv_to_rgb(np.array(hue), sat, np.array(1.0))

        psi = sensors.get("accumulator_pressure")
        breath = 0.15 + 0.85 * wave(now * (1.0 if sensors.get("water_heater_on", 0.0) else 0.25))
        since = sensors.since_rise("poof_button")
        pulse_head = since / PULSE_SECONDS if since is not None and since < PULSE_SECONDS else None

        for name, seg in frame.items():
            pos = self.pos[name]
            if name == "gauge":
                seg[:] = 0.0
                if psi is None:
                    seg[:: max(1, len(seg) // 8)] = 0.2  # dim tick marks: no reading
                else:
                    seg[pos <= np.clip(psi / PRESSURE_FULL_PSI, 0.0, 1.0)] = color
            elif name.startswith("handle"):
                seg[:] = color * breath
            elif name.startswith("hose"):
                seg[:] = 0.03
                if pulse_head is not None:
                    glow = np.clip(1.0 - np.abs(pos - pulse_head) / PULSE_WIDTH, 0.0, 1.0)
                    seg += glow[:, None] * PULSE_COLOR
            else:
                seg[:] = color * CONNECTOR_LEVEL
