"""Pattern registry.  Add a pattern by importing it and listing it here."""

from rhb_led_driver.patterns.coronal_mass_ejection import CoronalMassEjection
from rhb_led_driver.patterns.honeycomb import Honeycomb
from rhb_led_driver.patterns.instruments import Instruments
from rhb_led_driver.patterns.rainbow import Rainbow
from rhb_led_driver.patterns.windfire import WindFire

PATTERNS = {p.name: p for p in (Rainbow, Instruments, Honeycomb, CoronalMassEjection, WindFire)}
