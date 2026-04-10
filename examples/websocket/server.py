"""
Websocket session example - Server (placeholder)

This is a minimal stand-in for your own websocket backend. Replace the /ws
handler with your application logic. The only route required by the Vast
worker SDK is the healthcheck:

  GET /health - The worker SDK polls this to confirm the server is up.
  GET /ws     - Your websocket endpoint. Replace this with your own logic.
"""

import logging
from aiohttp import web

LOG_FILE = "/workspace/ws_server.log"
PORT = 9001

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Required route for Vast worker SDK integration
# ---------------------------------------------------------------------------

async def handle_health(request):
    """Healthcheck for the worker SDK."""
    return web.json_response({"status": "healthy"})


# ---------------------------------------------------------------------------
# Your websocket handler here
# ---------------------------------------------------------------------------

async def handle_ws(request):
    """Placeholder websocket handler. Replace with your own logic."""
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


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

def create_app():
    app = web.Application()
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
    web.run_app(app, host="0.0.0.0", port=PORT)
