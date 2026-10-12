import asyncio
import base64
import json
from pathlib import Path

from rhb_led_driver.layout import load_layout
from rhb_led_driver.main import Driver
from rhb_led_driver.output import NullOutput
from rhb_led_driver.simulator import SimOutput, start_simulator

LAYOUT = load_layout(Path(__file__).resolve().parent.parent / "config" / "layout.toml")


async def request(port, method, path, body=b""):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"{method} {path} HTTP/1.1\r\nHost: x\r\nContent-Length: {len(body)}\r\n\r\n".encode() + body)
    await writer.drain()
    return reader, writer


async def exercise():
    sim = SimOutput(LAYOUT, NullOutput(LAYOUT))
    driver = Driver(LAYOUT, sim, "rainbow")
    server = await start_simulator(driver, sim, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    run = asyncio.create_task(driver.run())
    try:
        reader, writer = await request(port, "GET", "/layout")
        layout = json.loads((await reader.read()).split(b"\r\n\r\n", 1)[1])
        writer.close()
        assert [s["name"] for s in layout["segments"]] == ["hose_upper", "hose_lower", "handle", "gauge"]
        assert "honeycomb" in layout["patterns"]

        msg = json.dumps({"address": "/pressure", "args": [42.0]}).encode()
        reader, writer = await request(port, "POST", "/osc", msg)
        assert b"204" in await reader.readline()
        writer.close()
        assert driver.sensors.get("accumulator_pressure") == 42.0

        reader, writer = await request(port, "POST", "/osc", b'{"address": "/nope"}')
        assert b"404" in await reader.readline()
        writer.close()

        reader, writer = await request(port, "GET", "/events")
        events = {}
        while len(events) < 2:
            line = await asyncio.wait_for(reader.readline(), 2)
            if line.startswith(b"event: "):
                name = line[7:].strip().decode()
                events[name] = (await reader.readline())[6:].strip()
        writer.close()
        assert len(base64.b64decode(events["frame"])) == sum(s.pixels for s in LAYOUT.segments) * 3
        assert json.loads(events["state"])["sensors"]["accumulator_pressure"]["value"] == 42.0
    finally:
        run.cancel()
        server.close()


def test_simulator_serves_layout_osc_and_frames():
    asyncio.run(exercise())
