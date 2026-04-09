"""
Websocket session example - Worker

Configures the Vast serverless worker to proxy to the server process (server.py).
The server must be started first - the worker watches its log file for the
"Websocket server ready" line to know it's up.

Benchmark: POSTs to /noop on the server, which sleeps 1s with workload 100 -> perf 100.
"""

from vastai import Worker, WorkerConfig, HandlerConfig, BenchmarkConfig, LogActionConfig

SERVER_PORT = 9001
LOG_FILE = "/workspace/ws_server.log"

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

Worker(worker_config).run()
