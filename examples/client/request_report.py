"""
Send N requests to a Vast.ai Serverless endpoint and generate a success/failure report.

Usage:
    python3 examples/client/request_report.py --endpoint <name> [--count 100] [--concurrency 50] [--instance prod]
"""

import asyncio
import argparse
import time
import statistics
from collections import Counter
from vastai import Serverless, ServerlessRequest


async def main():
    parser = argparse.ArgumentParser(description="Serverless endpoint request report")
    parser.add_argument("--endpoint", required=True, help="Endpoint name")
    parser.add_argument("--route", default="/generate/sync", help="Worker route (default: /generate/sync)")
    parser.add_argument("--count", type=int, default=100, help="Number of requests to send (default: 100)")
    parser.add_argument("--concurrency", type=int, default=50, help="Max concurrent requests (default: 50)")
    parser.add_argument("--instance", default="prod", choices=["prod", "alpha", "candidate"], help="Environment (default: prod)")
    parser.add_argument("--cost", type=int, default=100, help="Cost per request (default: 100)")
    parser.add_argument("--timeout", type=float, default=120.0, help="Per-request timeout in seconds (default: 120)")
    args = parser.parse_args()

    payload = {
        "input": {
            "modifier": "Text2Image",
            "modifications": {
                "prompt": "A simple test image.",
                "width": 512,
                "height": 512,
                "steps": 10,
                "seed": 42,
            }
        }
    }

    print(f"Connecting to {args.instance} environment...")
    async with Serverless(instance=args.instance, debug=False) as client:
        endpoint = await client.get_endpoint(name=args.endpoint)
        print(f"Found endpoint: {args.endpoint}")
        print(f"Sending {args.count} requests (concurrency={args.concurrency}, cost={args.cost}, timeout={args.timeout}s)")
        print("-" * 60)

        semaphore = asyncio.Semaphore(args.concurrency)
        results = []
        wall_start = time.time()

        async def send_one(idx: int):
            async with semaphore:
                req = ServerlessRequest()
                future = endpoint.request(
                    route=args.route,
                    payload=payload,
                    serverless_request=req,
                    cost=args.cost,
                )
                try:
                    result = await asyncio.wait_for(future, timeout=args.timeout)
                    results.append({
                        "idx": idx,
                        "ok": result.get("ok", False),
                        "status": result.get("status"),
                        "latency": result.get("latency"),
                        "request_status": req.status,
                        "error": None,
                    })
                except asyncio.TimeoutError:
                    results.append({
                        "idx": idx,
                        "ok": False,
                        "status": None,
                        "latency": None,
                        "request_status": req.status,
                        "error": "TimeoutError",
                    })
                except Exception as ex:
                    results.append({
                        "idx": idx,
                        "ok": False,
                        "status": None,
                        "latency": None,
                        "request_status": req.status,
                        "error": f"{type(ex).__name__}: {ex}",
                    })

        tasks = [send_one(i) for i in range(args.count)]
        await asyncio.gather(*tasks)
        wall_elapsed = time.time() - wall_start

    # ── Report ──────────────────────────────────────────────
    total = len(results)
    successes = [r for r in results if r["ok"]]
    failures = [r for r in results if not r["ok"]]
    success_latencies = [r["latency"] for r in successes if r["latency"] is not None]

    print()
    print("=" * 60)
    print("  REQUEST REPORT")
    print("=" * 60)
    print(f"  Endpoint:       {args.endpoint}")
    print(f"  Environment:    {args.instance}")
    print(f"  Route:          {args.route}")
    print(f"  Total requests: {total}")
    print(f"  Wall time:      {wall_elapsed:.2f}s")
    print(f"  Throughput:     {total / wall_elapsed:.2f} req/s")
    print()

    print("  ── Outcomes ──")
    print(f"  Succeeded: {len(successes):>6}  ({len(successes)/total*100:.1f}%)")
    print(f"  Failed:    {len(failures):>6}  ({len(failures)/total*100:.1f}%)")
    print()

    if success_latencies:
        print("  ── Latency (successful requests) ──")
        print(f"  Min:    {min(success_latencies):>8.3f}s")
        print(f"  Max:    {max(success_latencies):>8.3f}s")
        print(f"  Mean:   {statistics.mean(success_latencies):>8.3f}s")
        print(f"  Median: {statistics.median(success_latencies):>8.3f}s")
        if len(success_latencies) >= 2:
            print(f"  Stdev:  {statistics.stdev(success_latencies):>8.3f}s")
        p90 = sorted(success_latencies)[int(len(success_latencies) * 0.9)]
        p99 = sorted(success_latencies)[min(int(len(success_latencies) * 0.99), len(success_latencies) - 1)]
        print(f"  P90:    {p90:>8.3f}s")
        print(f"  P99:    {p99:>8.3f}s")
        print()

    if failures:
        print("  ── Failure Breakdown ──")

        # By HTTP status
        status_counts = Counter(r["status"] for r in failures if r["status"] is not None)
        if status_counts:
            print("  HTTP status codes:")
            for code, count in status_counts.most_common():
                print(f"    {code}: {count}")

        # By error type
        error_counts = Counter(r["error"] for r in failures if r["error"] is not None)
        if error_counts:
            print("  Exceptions:")
            for err, count in error_counts.most_common():
                print(f"    {err}: {count}")

        # By request status
        req_status_counts = Counter(r["request_status"] for r in failures)
        print("  Request status at failure:")
        for status, count in req_status_counts.most_common():
            print(f"    {status}: {count}")
        print()

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
