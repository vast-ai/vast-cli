"""
Websocket session example - Worker

Starts an aiohttp server (HTTP + Websocket) in the background, then runs
the Vast serverless worker on top. The start_server.sh bootstrap finds this
file as the entrypoint via `python3 -m worker`.

Server routes:
  POST /noop   - no-op benchmark (sleeps 1s, workload 100 -> perf 100)
  GET  /health - healthcheck for the worker SDK
  GET  /ws     - websocket endpoint (responds "pong" to "ping")

Usage with start_server.sh:
  Set PYWORKER_REPO to the vast-cli repo URL and PYWORKER_REF to the branch,
  then set BACKEND=websocket. Or point PYWORKER_REPO at a repo where this
  file lives at the root as worker.py.
"""

import asyncio
import logging
from aiohttp import web
from vastai import Worker, WorkerConfig, HandlerConfig, BenchmarkConfig, LogActionConfig

SERVER_PORT = 9001
LOG_FILE = "/workspace/ws_server.log"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


# --- HTTP + Websocket server ---

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


async def start_server():
    app = web.Application()
    app.router.add_post("/noop", handle_noop)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/ws", handle_ws)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", SERVER_PORT)
    await site.start()
    log.info(f"Server listening on port {SERVER_PORT}")

    # Write the log line the worker SDK watches for
    with open(LOG_FILE, "a") as f:
        f.write("Websocket server ready\n")
        f.flush()


# --- Vast worker ---

worker_config = WorkerConfig(
    model_server_url="http://127.0.0.1",
    model_server_port=SERVER_PORT,
    model_log_file=LOG_FILE,
    model_healthcheck_url="/health",
    handlers=[
        HandlerConfig(
            route="/noop",
            benchmark_config=BenchmarkConfig(
                dataset=[{"noop": True}],
                runs=1,
            ),
            workload_calculator=lambda req: 100,
        ),
    ],
    log_action_config=LogActionConfig(
        on_load=["Websocket server ready"],
        on_error=["Traceback (most recent call last):"],
    ),
    max_sessions=2,
)


async def main():
    await start_server()
    await Worker(worker_config).run_async()


if __name__ == "__main__":
    asyncio.run(main())
