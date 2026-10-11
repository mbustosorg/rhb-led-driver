"""Latest sensor readings from the rig, received over OSC.

The rest of the car already broadcasts these; this Pi just has to be added
to each sender's listener list (rhb-sensor-monitor `--client_ip`, the water
heater's MOBILE_CLIENTS).  Every reading is stamped on the monotonic clock
so a pattern can tell a live value from one whose sender has gone quiet,
and fall back to something sensible instead of freezing on a stale number.
"""

import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Sensor:
    name: str
    address: str
    stale_after: float  # seconds without an update before the value is ignored


# OSC address -> what patterns call it.
SENSORS = (
    # rhb-sensor-monitor: guaranteed at least every 500 ms
    Sensor("accumulator_pressure", "/pressure", stale_after=3.0),
    Sensor("poof_count", "/poof_count", stale_after=30.0),
    # rhb-water-heater, once per heater cycle
    Sensor("water_temp", "/temperature", stale_after=30.0),
    Sensor("water_heater_on", "/water_heater", stale_after=30.0),
    # No sender yet.  Value 1 = pressed, 0 = released.
    Sensor("poof_button", "/poof_button", stale_after=float("inf")),
)


@dataclass
class Reading:
    value: float
    at: float  # time.monotonic()


class SensorState:
    def __init__(self, sensors=SENSORS, clock=time.monotonic):
        self._by_address = {s.address: s for s in sensors}
        self._by_name = {s.name: s for s in sensors}
        self._readings: dict[str, Reading] = {}
        self._rises: dict[str, float] = {}  # when a value last went from <= 0 to > 0
        self._clock = clock

    @property
    def addresses(self):
        return self._by_address.keys()

    def on_osc(self, address: str, *args) -> None:
        """python-osc handler.  A bad value is logged and dropped, never raised."""
        sensor = self._by_address.get(address)
        if sensor is None or not args:
            return
        try:
            value = float(args[0])
        except (TypeError, ValueError):
            logger.warning("Bad value for %s: %r", address, args)
            return
        previous = self._readings.get(sensor.name)
        now = self._clock()
        if value > 0 and (previous is None or previous.value <= 0):
            self._rises[sensor.name] = now
        self._readings[sensor.name] = Reading(value, now)

    def get(self, name: str, default: float | None = None) -> float | None:
        """The latest value, or `default` if never received or gone stale."""
        reading = self._readings.get(name)
        if reading is None or self._clock() - reading.at > self._by_name[name].stale_after:
            return default
        return reading.value

    def age(self, name: str) -> float | None:
        """Seconds since the last update, or None if never received."""
        reading = self._readings.get(name)
        return None if reading is None else self._clock() - reading.at

    def since_rise(self, name: str) -> float | None:
        """Seconds since the value last went from off to on -- a button press."""
        at = self._rises.get(name)
        return None if at is None else self._clock() - at
