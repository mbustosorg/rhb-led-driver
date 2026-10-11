"""Pattern registry.  Add a pattern by importing it and listing it here."""

from rhb_led_driver.patterns.instruments import Instruments
from rhb_led_driver.patterns.rainbow import Rainbow

PATTERNS = {p.name: p for p in (Rainbow, Instruments)}
