"""Frame output: E1.31 (sACN) to the Falcon F16V5, or nowhere for dev."""

import logging

import numpy as np

from rhb_led_driver.layout import PIXELS_PER_UNIVERSE, Layout

logger = logging.getLogger(__name__)

Frame = dict[str, np.ndarray]  # segment name -> (pixels, 3) float, 0..1


def to_bytes(rgb: np.ndarray, brightness: float) -> bytes:
    return (np.clip(rgb, 0.0, 1.0) * (255.0 * brightness)).astype(np.uint8).tobytes()


class SacnOutput:
    """Unicast sACN.  sacn's own thread transmits the latest data at layout.fps.

    Deliberately not manual_flush(): flush() uses E1.31 sync, which marks the
    data packets as "wait for a sync" and sends that sync by multicast.  A
    controller that honors the mark but never sees the multicast would hold
    every frame and stay dark.
    """

    def __init__(self, layout: Layout, bind_address: str | None = None):
        import sacn  # imported here so tests and --dry-run don't need it

        self._layout = layout
        kwargs = {"bind_address": bind_address} if bind_address else {}
        # Discovery broadcasts are pointless when unicasting to one controller.
        self._sender = sacn.sACNsender(fps=int(layout.fps), universeDiscovery=False, **kwargs)
        self._sender.start()
        for segment in layout.segments:
            for u in segment.universes:
                self._sender.activate_output(u)
                self._sender[u].destination = layout.host
        logger.info("sACN to %s, universes %s", layout.host, self._sender.get_active_outputs())

    def send(self, frame: Frame, brightness: float) -> None:
        chunk = PIXELS_PER_UNIVERSE * 3
        for segment in self._layout.segments:
            data = to_bytes(frame[segment.name], brightness)
            for i, u in enumerate(segment.universes):
                self._sender[u].dmx_data = data[i * chunk : (i + 1) * chunk]

    def close(self) -> None:
        self._sender.stop()


class NullOutput:
    """--dry-run: render everything, send nothing."""

    def __init__(self, layout: Layout):
        self._layout = layout

    def send(self, frame: Frame, brightness: float) -> None:
        for segment in self._layout.segments:
            to_bytes(frame[segment.name], brightness)

    def close(self) -> None:
        pass
