"""
Websocket session example - Server

A simple server that handles:
- HTTP POST /noop  (for the worker SDK benchmark - sleeps 1s, returns OK)
- HTTP GET  /health (healthcheck for the worker SDK)
- Websocket /ws     (actual client traffic - responds "pong" to "ping")

Run this before worker.py. The worker SDK will proxy benchmark requests here
over HTTP, while clients connect to the websocket endpoint directly.
"""

import asyncio
import json
import logging
from aiohttp import web

LOG_FILE = "/var/log/ws_server.log"
PORT = 9001

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def handle_noop(request):
    """No-op benchmark handler. Sleeps 1s so workload(100) / time(1s) = perf 100."""
    await asyncio.sleep(1)
    return web.json_response({"status": "ok"})


async def handle_health(request):
    return web.json_response({"status": "healthy"})


async def handle_ws(request):
    """Websocket handler - responds 'pong' to 'ping', echoes everything else."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    log.info("Websocket client connected")

    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            if msg.data == "ping":
                await ws.send_str("pong")
            else:
                await ws.send_str(f"echo: {msg.data}")
        elif msg.type == web.WSMsgType.ERROR:
            log.error(f"Websocket error: {ws.exception()}")

    log.info("Websocket client disconnected")
    return ws


def create_app():
    app = web.Application()
    app.router.add_post("/noop", handle_noop)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/ws", handle_ws)
    return app


if __name__ == "__main__":
    app = create_app()

    # Write the log line the worker SDK watches for
    with open(LOG_FILE, "a") as f:
        f.write("Websocket server ready\n")
        f.flush()

    log.info(f"Server starting on port {PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT, print=None)
