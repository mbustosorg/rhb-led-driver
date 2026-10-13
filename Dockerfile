# The simulator alone, for hosting it publicly: renders patterns and serves
# the browser view, sends no sACN.  To keep bandwidth down it streams at
# 20 fps and pauses a viewer's stream after 15 idle minutes.  Not how the Pi runs (see README.md).
#
#   docker build -t rhb-led-sim . && docker run -p 8080:8080 rhb-led-sim
#
# Hosts that assign a port (Fly.io, Render, Cloud Run) pass it in $PORT.
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY rhb_led_driver rhb_led_driver
COPY config config

ENV OSC_LISTEN_IP=127.0.0.1 \
    OSC_LISTEN_PORT=8888 \
    LAYOUT_FILE=config/layout.toml \
    DEFAULT_PATTERN=coronal_mass_ejection \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1

CMD python -m rhb_led_driver --dry-run --sim --sim-host 0.0.0.0 --sim-port ${PORT:-8080} --sim-fps 20 --sim-idle 15
