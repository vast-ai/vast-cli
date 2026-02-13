import asyncio
from vastai import Serverless
import os
import random
import collections
import time
import uuid
from prometheus_client import start_http_server, Gauge, Histogram
from typing import Dict, Any
import nltk

API_KEY = os.environ.get("VAST_API_KEY")


nltk.download("words")
WORD_LIST = nltk.corpus.words.words()
# Generate unique run ID for this session
RUN_ID = time.strftime("vLLM_%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]

# Prometheus metrics
REQUEST_STATUS = Gauge(
    "vast_request_status_current",
    "Current number of requests by status",
    ["status", "run_id"]
)
LATENCY = Histogram(
    "vast_request_latency_seconds",
    "Latency of responses (seconds)",
    ["run_id"]
)

LATENCY_AVG = Gauge(
    "vast_request_latency_avg_seconds",
    "Rolling average latency (seconds) over recent responses",
    ["run_id"]
)

CURRENT_LOAD = Gauge(
    "vast_current_load",
    "Current request load (tokens per second or arbitrary units)",
    ["run_id"]
)

WORKER_STATUS = Gauge(
    "vast_workers_status_current",
    "Current number of workers by status",
    ["status", "run_id"]
)

WORKERS_TOTAL = Gauge(
    "vast_workers_total",
    "Total number of workers returned by get_endpoint_workers",
    ["run_id"]
)

WORKER_CUR_LOAD_TOTAL = Gauge(
    "vast_workers_cur_load_total",
    "Sum of current load across workers",
    ["run_id"]
)

WORKER_NEW_LOAD_TOTAL = Gauge(
    "vast_workers_new_load_total",
    "Sum of new load across workers",
    ["run_id"]
)

WORKER_REQS_WORKING_TOTAL = Gauge(
    "vast_workers_requests_working_total",
    "Sum of requests_working across workers",
    ["run_id"]
)

# Averages
WORKERS_AVG_CUR_PERF = Gauge("vast_workers_avg_cur_perf", "Average cur_perf", ["run_id"])
WORKERS_AVG_PERF = Gauge("vast_workers_avg_perf", "Average perf", ["run_id"])
WORKERS_AVG_MEASURED_PERF = Gauge("vast_workers_avg_measured_perf", "Average measured_perf", ["run_id"])
WORKERS_AVG_DLPERF = Gauge("vast_workers_avg_dlperf", "Average dlperf", ["run_id"])
WORKERS_AVG_RELIABILITY = Gauge("vast_workers_avg_reliability", "Average reliability", ["run_id"])
WORKERS_AVG_CUR_LOAD_ROLLING = Gauge("vast_workers_avg_cur_load_rolling", "Average cur_load_rolling_avg", ["run_id"])
WORKERS_AVG_DISK_USAGE = Gauge("vast_workers_avg_disk_usage", "Average disk_usage", ["run_id"])

# Per-worker gauges (also labeled with worker_id)
WORKER_MEASURED_PERF = Gauge(
    "vast_worker_measured_perf",
    "Measured perf per worker",
    ["worker_id", "run_id"]
)
WORKER_CUR_LOAD = Gauge(
    "vast_worker_cur_load",
    "Current load per worker",
    ["worker_id", "run_id"]
)
WORKER_REQS_WORKING = Gauge(
    "vast_worker_requests_working",
    "Current requests_working per worker",
    ["worker_id", "run_id"]
)
WORKER_STATUS_LIVE = Gauge(
    "vast_worker_status_current",
    "Status (1 for present) per worker; useful for per-worker dashboards",
    ["worker_id", "status", "run_id"]
)


latencies = collections.deque(maxlen=50)

def export_to_prom(agg: dict, run_id: str) -> None:
    """
    Push aggregate + per-worker metrics with run_id label.
    Call this after aggregate_workers(workers).
    """

    # --- status counts: clear existing for this run_id, then set ---
    # (Same internal reset pattern you used.)
    for (label_status, label_run_id) in list(WORKER_STATUS._metrics.keys()):
        if label_run_id == run_id:
            WORKER_STATUS.labels(status=label_status, run_id=run_id).set(0)

    for status, count in agg["status_counts"].items():
        WORKER_STATUS.labels(status=status, run_id=run_id).set(count)

    # --- totals / averages ---
    WORKERS_TOTAL.labels(run_id=run_id).set(agg["total_workers"])
    WORKER_CUR_LOAD_TOTAL.labels(run_id=run_id).set(agg["total_cur_load"])
    WORKER_NEW_LOAD_TOTAL.labels(run_id=run_id).set(agg["total_new_load"])
    WORKER_REQS_WORKING_TOTAL.labels(run_id=run_id).set(agg["total_reqs_working"])

    WORKERS_AVG_CUR_PERF.labels(run_id=run_id).set(agg["avg_cur_perf"])
    WORKERS_AVG_PERF.labels(run_id=run_id).set(agg["avg_perf"])
    WORKERS_AVG_MEASURED_PERF.labels(run_id=run_id).set(agg["avg_measured_perf"])
    WORKERS_AVG_DLPERF.labels(run_id=run_id).set(agg["avg_dlperf"])
    WORKERS_AVG_RELIABILITY.labels(run_id=run_id).set(agg["avg_reliability"])
    WORKERS_AVG_CUR_LOAD_ROLLING.labels(run_id=run_id).set(agg["avg_cur_load_rolling"])
    WORKERS_AVG_DISK_USAGE.labels(run_id=run_id).set(agg["avg_disk_usage"])

    # --- per-worker: set gauges keyed by worker_id + run_id ---
    # First, clear any old per-worker status rows for this run_id
    for (wid, status, label_run_id) in list(WORKER_STATUS_LIVE._metrics.keys()):
        if label_run_id == run_id:
            WORKER_STATUS_LIVE.labels(worker_id=wid, status=status, run_id=run_id).set(0)

    for row in agg["per_worker"]:
        wid = str(row["id"])
        WORKER_MEASURED_PERF.labels(worker_id=wid, run_id=run_id).set(row["measured_perf"])
        WORKER_CUR_LOAD.labels(worker_id=wid, run_id=run_id).set(row["cur_load"])
        WORKER_REQS_WORKING.labels(worker_id=wid, run_id=run_id).set(row["reqs_working"])
        # Mark this worker present in its current status (value=1)
        WORKER_STATUS_LIVE.labels(worker_id=wid, status=row["status"], run_id=run_id).set(1)

async def status_reporter(client, endpoint, responses, latencies, window_size=50):
    """Continuously updates gauges to reflect live status counts."""
    while True:
        status_counts = collections.Counter()

        for r in responses:
            try:
                status = getattr(r, "status", None)
                if callable(status):
                    status = status()
                if status is None:
                    status = "unknown"
                status_counts[status] += 1
            except Exception:
                status_counts["error"] += 1

        # Reset gauges before updating
        for label_tuple in list(REQUEST_STATUS._metrics.keys()):
            label_status, label_run_id = label_tuple
            if label_run_id == RUN_ID:
                REQUEST_STATUS.labels(status=label_status, run_id=RUN_ID).set(0)

        # Update gauges to reflect current counts
        for status, count in status_counts.items():
            REQUEST_STATUS.labels(status=status, run_id=RUN_ID).set(count)

        # Compute rolling latency average
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        # Record it in Prometheus
        LATENCY_AVG.labels(run_id=RUN_ID).set(avg_latency)

        #workers = await endpoint.get_workers()
        #aggregate = client.aggregate_workers(workers)
        #export_to_prom(aggregate)

        # Console display
        print("\n=== Live Response Status ===")
        for status, count in status_counts.items():
            print(f"{status:>12}: {count}")
        print(f"Rolling Avg Latency (last {len(latencies)}): {avg_latency:.2f} s")
        print("=============================\n")

        await asyncio.sleep(1)


def latency_callback(response):
    latency = response.get("latency")
    if latency is not None:
        latencies.append(latency)
        LATENCY.labels(run_id=RUN_ID).observe(latency)


def cur_load(start_time, ramp_time, min_load, max_load, backwards=False):
    # progress clamped to [0,1]
    t = max(0.0, min((time.time() - start_time) / ramp_time, 1.0))
    e = t * t  # quadratic ease-in; keep as-is for reverse too
    a, b = (max_load, min_load) if backwards else (min_load, max_load)
    return a + (b - a) * e

async def main():
    async with Serverless() as client:
        endpoint = await client.get_endpoint(name="big")

        system_prompt = """
        You are Qwen.
        You are to only speak in English.
        You are to use the <stop> token when you are done generating tokens. Do *not* use the <stop> token unless you intend to stop responding.
        Your task is to return Yes or No to the following question:
        Does the document contain the word "establish"?
        """


        user_prompt = """
        Who is your favorite character from late 2000's Disney/Nickelodeon?
        """
        responses = []

        asyncio.create_task(status_reporter(client, endpoint, responses, latencies))

        LOAD_PER_REQUEST = 10
        MAX_LOAD = 10000
        MIN_LOAD = 500
        RAMP_TIME = 15 * 60 # seconds
        BACKWARDS = False
        start_time = time.time()

        while True:
            user_prompt = " ".join(random.choices(WORD_LIST, k=int(random.randint(300,1500))))
            payload = {
                "input" : {
                    "model": "Qwen/Qwen2-72B",
                    "prompt" : f"Random_Hash: {random.randint(1, 10000)}\nSystem: {system_prompt}\n<document>\n{user_prompt}</document>\nAssistant: ",
                    "max_tokens" : 500,
                    "temperature" : 0.7,
                    "stop" : ["<stop>"]

                }
            }
            CUR_LOAD = cur_load(start_time, RAMP_TIME, MIN_LOAD, MAX_LOAD, backwards=BACKWARDS)
            CUR_LOAD = 1000 # Hardcode a set load
            CURRENT_LOAD.labels(run_id=RUN_ID).set(CUR_LOAD)
            request = endpoint.request("/v1/completions", payload, cost=LOAD_PER_REQUEST).then(latency_callback)
            responses.append(request)
            await asyncio.sleep(LOAD_PER_REQUEST / CUR_LOAD)


if __name__ == "__main__":
    start_http_server(8000)
    asyncio.run(main())
