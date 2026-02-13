import asyncio
from vastai import Serverless
import os
import random
import collections
import time
import uuid
from prometheus_client import start_http_server, Gauge, Histogram

API_KEY = os.environ.get("VAST_API_KEY")

# Generate unique run ID for this session
RUN_ID = time.strftime("ComfyUI_Image_%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]

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


latencies = collections.deque(maxlen=50)


async def status_reporter(responses, latencies, window_size=50):
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
    client = Serverless()
    endpoint = await client.get_endpoint(name="comfy")

    prompts = [
        "a page from a peanuts comic strip",
    ]

    responses = []

    asyncio.create_task(status_reporter(responses, latencies))

    LOAD_PER_REQUEST = 100
    MAX_LOAD = 1000
    MIN_LOAD = 50
    RAMP_TIME = 15 * 60 # seconds
    BACKWARDS = False
    start_time = time.time()

    while True:
        payload = {
            "input": {
                "modifier": "Text2Image",
                "modifications": {
                    "prompt": random.choice(prompts),
                    "width": 512,
                    "height": 512,
                    "steps": 10,
                    "seed": random.randint(1, 10000)
                }
            }
        }
        CUR_LOAD = cur_load(start_time, RAMP_TIME, MIN_LOAD, MAX_LOAD, backwards=BACKWARDS)
        CUR_LOAD = 1000 # Hardcode a set load
        request = endpoint.request("/generate/sync", payload, cost=LOAD_PER_REQUEST).then(latency_callback)
        responses.append(request)
        await asyncio.sleep(LOAD_PER_REQUEST / CUR_LOAD)


if __name__ == "__main__":
    start_http_server(8000)
    asyncio.run(main())
