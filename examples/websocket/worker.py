"""
Websocket session example - Worker

Configures the Vast serverless worker SDK to proxy to server.py.
The server must be started first. The worker watches the log file for the
"Websocket server ready" line to know it's up, then runs a benchmark and
begins accepting sessions.

You should not need to modify this file much. The key things to adjust:
  - SERVER_PORT: must match the port your server listens on
  - max_sessions: how many concurrent websocket sessions per worker
  - The /noop benchmark config (dataset, runs, workload_calculator)
"""

import os
from vastai import Worker, WorkerConfig, HandlerConfig, BenchmarkConfig, LogActionConfig

SERVER_PORT = 9001
LOG_FILE = "/workspace/ws_server.log"


async def benchmark(**kwargs):
    """Benchmark handler. Sleeps 1s with workload 1000 -> perf ~1000."""
    import asyncio
    await asyncio.sleep(1)
    return {"status": "ok"}


async def get_ws_port(**kwargs):
    """Return the external port mapped to our websocket server.

    Vast containers expose internal ports on different external ports.
    The mapping is available via the VAST_TCP_PORT_<port> env var.
    """
    ext_port = os.environ.get(f"VAST_TCP_PORT_{SERVER_PORT}")
    if ext_port is None:
        raise RuntimeError(f"VAST_TCP_PORT_{SERVER_PORT} not set")
    return {"port": int(ext_port)}


worker_config = WorkerConfig(
    model_server_url="http://127.0.0.1",
    model_server_port=SERVER_PORT,
    model_log_file=LOG_FILE,
    model_healthcheck_url="/health",
    handlers=[
        HandlerConfig(
            route="/benchmark",
            is_remote_dispatch=True,
            remote_function=benchmark,
            benchmark_config=BenchmarkConfig(
                dataset=[{"benchmark": True}],
                runs=1,
            ),
            workload_calculator=lambda req: 1000,
        ),
        HandlerConfig(
            route="/ws_port",
            is_remote_dispatch=True,
            remote_function=get_ws_port,
        ),
    ],
    log_action_config=LogActionConfig(
        on_load=["Websocket server ready"],
        on_error=["Traceback (most recent call last):"],
    ),
    max_sessions=2,
)

Worker(worker_config).run()
