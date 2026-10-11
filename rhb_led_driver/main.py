"""Entry point: listen for sensors and control over OSC, render, send to the F16V5.

    python -m rhb_led_driver [--dry-run] [--sim [--sim-host H] [--sim-port P]]

Run from the directory holding settings.toml (ConfigReader reads it from the
cwd).  OSC control, besides the sensor addresses in sensors.py:

    /led/pattern <name>        switch pattern (see patterns/__init__.py)
    /led/brightness <0..1>     scale under the layout's max_brightness
"""

import argparse
import asyncio
import logging
import signal
import time
from pathlib import Path

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer

from rhb_led_driver.adopted.config_reader import get_config
from rhb_led_driver.adopted.log_setup import configure_logging
from rhb_led_driver.layout import load_layout
from rhb_led_driver.output import NullOutput, SacnOutput
from rhb_led_driver.patterns import PATTERNS
from rhb_led_driver.patterns.base import blank_frame
from rhb_led_driver.sensors import SensorState
from rhb_led_driver.simulator import SimOutput, start_simulator

logger = logging.getLogger(__name__)

REQUIRED_KEYS = {"OSC_LISTEN_IP", "OSC_LISTEN_PORT", "LAYOUT_FILE", "DEFAULT_PATTERN", "LOG_LEVEL"}


class Driver:
    def __init__(self, layout, output, default_pattern: str):
        self.layout = layout
        self.output = output
        self.sensors = SensorState()
        self.brightness = 1.0
        self.frame = blank_frame(layout)
        self.pattern = PATTERNS[default_pattern](layout)

    def set_pattern(self, _address, name, *_):
        if name not in PATTERNS:
            logger.warning("Unknown pattern %r; have %s", name, sorted(PATTERNS))
            return
        logger.info("Pattern -> %s", name)
        self.pattern = PATTERNS[name](self.layout)

    def set_brightness(self, _address, value, *_):
        try:
            self.brightness = min(1.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            logger.warning("Bad brightness %r", value)

    def routes(self) -> dict:
        """OSC address -> handler(address, *args).  Real OSC and the simulator both go through here."""
        routes = {address: self.sensors.on_osc for address in self.sensors.addresses}
        routes["/led/pattern"] = self.set_pattern
        routes["/led/brightness"] = self.set_brightness
        return routes

    def handle(self, address: str, *args) -> bool:
        handler = self.routes().get(address)
        if handler is None:
            return False
        handler(address, *args)
        return True

    def dispatcher(self) -> Dispatcher:
        d = Dispatcher()
        for address, handler in self.routes().items():
            d.map(address, handler)
        d.set_default_handler(lambda *_: None)  # the rig broadcasts plenty we don't use
        return d

    def state(self) -> dict:
        return {
            "pattern": self.pattern.name,
            "brightness": self.brightness,
            "sensors": self.sensors.snapshot(),
        }

    async def run(self) -> None:
        period = 1.0 / self.layout.fps
        next_frame = time.monotonic()
        while True:
            now = time.monotonic()
            try:
                self.pattern.render(now, self.sensors, self.frame)
                self.output.send(self.frame, self.brightness * self.layout.max_brightness)
            except Exception:
                # One bad frame must not take the lights down; log and keep going.
                logger.exception("Frame failed in %s", self.pattern.name)
            next_frame += period
            delay = next_frame - time.monotonic()
            if delay < 0:  # fell behind; don't try to catch up with a burst
                next_frame = time.monotonic()
                delay = 0
            await asyncio.sleep(delay)

    def blackout(self) -> None:
        self.output.send(blank_frame(self.layout), 0.0)


async def amain(args) -> None:
    cfg = get_config(REQUIRED_KEYS)
    layout = load_layout(Path(cfg.LAYOUT_FILE))
    output = NullOutput(layout) if args.dry_run else SacnOutput(layout, cfg.if_exists("SACN_BIND_IP") or None)
    if args.sim:
        output = SimOutput(layout, output)
    driver = Driver(layout, output, cfg.DEFAULT_PATTERN)
    sim_server = await start_simulator(driver, output, args.sim_host, args.sim_port) if args.sim else None

    server = AsyncIOOSCUDPServer(
        (cfg.OSC_LISTEN_IP, int(cfg.OSC_LISTEN_PORT)), driver.dispatcher(), asyncio.get_running_loop()
    )
    transport, _ = await server.create_serve_endpoint()
    logger.info("OSC on %s:%s, pattern %s", cfg.OSC_LISTEN_IP, cfg.OSC_LISTEN_PORT, driver.pattern.name)

    # systemd stops us with SIGTERM; make it, and Ctrl-C, go through the blackout.
    task = asyncio.current_task()
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(sig, task.cancel)
    try:
        await driver.run()
    except asyncio.CancelledError:
        logger.info("Stopping")
    finally:
        transport.close()
        if sim_server:
            sim_server.close()
        driver.blackout()
        output.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="RHB LED driver")
    parser.add_argument("--dry-run", action="store_true", help="render frames but send nothing")
    parser.add_argument("--sim", action="store_true", help="serve a live browser view of the LEDs")
    parser.add_argument("--sim-host", default="127.0.0.1", help="0.0.0.0 to view from another device")
    parser.add_argument("--sim-port", type=int, default=8080)
    args = parser.parse_args()
    configure_logging()
    level = get_config(REQUIRED_KEYS).LOG_LEVEL
    logging.getLogger().setLevel(level.upper())
    asyncio.run(amain(args))


if __name__ == "__main__":
    main()
