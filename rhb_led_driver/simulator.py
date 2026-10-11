"""Live browser view of the LEDs: python -m rhb_led_driver --sim [--dry-run]

The real driver runs as usual; SimOutput tees each frame it sends, and a
small HTTP server (stdlib asyncio, no extra dependencies) streams those
frames to a page that draws every pixel at its layout x,y.  What the page
shows is exactly what goes to the F16V5, brightness cap included.

The page's controls post OSC-shaped messages that go through the same
routes as real OSC, so sliders, TouchOSC and the car's sensors can all
drive it at once.

    GET  /         the page (simulator.html)
    GET  /layout   segments with pixel x,y, and the pattern names
    GET  /events   Server-Sent Events: "frame" (base64 RGB, every segment in
                   layout order) at the frame rate, "state" 4x a second
    POST /osc      {"address": "/pressure", "args": [42.0]}
"""

import asyncio
import base64
import json
import logging
import time
from pathlib import Path

from rhb_led_driver.output import to_bytes
from rhb_led_driver.patterns import PATTERNS

logger = logging.getLogger(__name__)

PAGE = Path(__file__).with_name("simulator.html")
MAX_BODY = 64 * 1024
STATE_PERIOD = 0.25


class SimOutput:
    """Wraps the real output (sACN or Null) and keeps the latest frame's bytes."""

    def __init__(self, layout, inner):
        self._layout = layout
        self._inner = inner
        self.latest = b""
        self.seq = 0

    def send(self, frame, brightness: float) -> None:
        self._inner.send(frame, brightness)
        self.latest = b"".join(to_bytes(frame[s.name], brightness) for s in self._layout.segments)
        self.seq += 1

    def close(self) -> None:
        self._inner.close()


def layout_json(layout) -> dict:
    return {
        "segments": [
            {"name": s.name, "pixels": s.pixels, "xy": [[round(x, 2), round(y, 2)] for x, y in s.xy]}
            for s in layout.segments
        ],
        "patterns": sorted(PATTERNS),
        "fps": layout.fps,
        "max_brightness": layout.max_brightness,
    }


def _response(status: str, body: bytes = b"", content_type: str = "text/plain") -> bytes:
    head = (
        f"HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\n"
        f"Content-Length: {len(body)}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n"
    )
    return head.encode() + body


async def start_simulator(driver, sim: SimOutput, host: str, port: int) -> asyncio.Server:
    async def stream(writer: asyncio.StreamWriter) -> None:
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
            b"Cache-Control: no-store\r\nConnection: keep-alive\r\n\r\n"
        )
        last_seq, next_state = -1, 0.0
        while True:
            if sim.seq != last_seq:
                last_seq = sim.seq
                writer.write(b"event: frame\ndata: " + base64.b64encode(sim.latest) + b"\n\n")
            if time.monotonic() >= next_state:
                next_state = time.monotonic() + STATE_PERIOD
                writer.write(b"event: state\ndata: " + json.dumps(driver.state()).encode() + b"\n\n")
            await writer.drain()  # a slow client just skips frames
            await asyncio.sleep(1.0 / driver.layout.fps)

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            method, target, _ = (await reader.readline()).decode("latin-1").split(" ", 2)
            path = target.split("?", 1)[0]
            headers = {}
            while (line := await reader.readline()) not in (b"\r\n", b"\n", b""):
                key, _, value = line.decode("latin-1").partition(":")
                headers[key.strip().lower()] = value.strip()
            length = int(headers.get("content-length") or 0)
            if length > MAX_BODY:
                writer.write(_response("413 Payload Too Large"))
                return
            body = await reader.readexactly(length)

            if method == "GET" and path == "/":
                writer.write(_response("200 OK", PAGE.read_bytes(), "text/html; charset=utf-8"))
            elif method == "GET" and path == "/layout":
                writer.write(_response("200 OK", json.dumps(layout_json(driver.layout)).encode(), "application/json"))
            elif method == "GET" and path == "/events":
                await stream(writer)
            elif method == "POST" and path == "/osc":
                message = json.loads(body)
                ok = driver.handle(str(message["address"]), *message.get("args", []))
                writer.write(_response("204 No Content" if ok else "404 Not Found"))
            else:
                writer.write(_response("404 Not Found"))
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError, ValueError, KeyError, TypeError):
            pass  # a bad or vanished client must never touch the render loop
        finally:
            writer.close()

    server = await asyncio.start_server(handle, host, port)
    logger.info("Simulator on http://%s:%s/", host, port)
    return server
