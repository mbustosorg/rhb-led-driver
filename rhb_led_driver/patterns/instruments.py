"""Sensor-driven pattern: the car's state, shown on the car.

gauge   fills bottom-up with accumulator pressure; color runs from blue at a
        cold bath to red at a hot one
handle  breathes; faster while the heater is on
hose    a bright pulse runs down it whenever the poof button is pressed

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

        # Gauge
        psi = sensors.get("accumulator_pressure")
        gauge = frame["gauge"]
        gauge[:] = 0.0
        if psi is None:
            gauge[:: max(1, len(gauge) // 8)] = 0.2  # dim tick marks: no reading
        else:
            lit = self.pos["gauge"] <= np.clip(psi / PRESSURE_FULL_PSI, 0.0, 1.0)
            gauge[lit] = color

        # Handle
        breaths_per_s = 1.0 if sensors.get("water_heater_on", 0.0) else 0.25
        frame["handle"][:] = color * (0.15 + 0.85 * wave(now * breaths_per_s))

        # Hose
        hose = frame["hose_upper"]
        hose[:] = 0.03
        since = sensors.since_rise("poof_button")
        if since is not None and since < PULSE_SECONDS:
            head = since / PULSE_SECONDS
            dist = np.abs(self.pos["hose_upper"] - head)
            hose += np.clip(1.0 - dist / PULSE_WIDTH, 0.0, 1.0)[:, None] * np.array([1.0, 0.5, 0.0])

        # Hose
        hose = frame["hose_lower"]
        hose[:] = 0.03
        since = sensors.since_rise("poof_button")
        if since is not None and since < PULSE_SECONDS:
            head = since / PULSE_SECONDS
            dist = np.abs(self.pos["hose_lower"] - head)
            hose += np.clip(1.0 - dist / PULSE_WIDTH, 0.0, 1.0)[:, None] * np.array([1.0, 0.5, 0.0])
