"""vastai run benchmarks: benchmark a template against one or more GPUs.
Each GPU is rented in parallel; the per-GPU measured perf comes from the
template's pyworker benchmark.
"""

import argparse
import atexit
import json
import math
import random
import re
import signal
import sys
import threading
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from rich.console import Console
from rich.live import Live
from rich.table import Table

from vastai import VastAI
from vastai.cli.parser import argument
from vastai.cli.display import deindent
from vastai.cli.utils import get_parser as _get_parser, get_client  # noqa: F401  (used by test conftest)
from vastai.data.query import OP_TO_STR
from vastai.data import query as _query_consts


parser = _get_parser()


# Default GPUs (per-card VRAM in MB).
_DEFAULT_GPUS = {
    "RTX 5090":  32607,
    "RTX 4090":  24564,
    "RTX 3090":  24576,
    "RTX A6000": 49140,
}

_ENDPOINT_CONFIG = {"cold_workers": 1, "max_workers": 1, "min_load": 1.0}

_WORKER_POLL_INTERVAL = 10.0
_DEFAULT_BENCHMARK_TIMEOUT = 60 * 60  # seconds to wait for a benchmark to complete before giving up 
_RENTAL_TIMEOUT = 120  # fail fast if the autoscaler hasn't rented anything by then
_MAX_ABANDONS = 3  # bail after this many workers get abandoned without one reaching idle 
_PARALLEL_SUBMIT_DELAY = 4.0  # spacing between parallel submits 

# Worker states the autoscaler does NOT recover from. 
# these will timeout if they persist for >_TERMINAL_GRACE_SECONDS without any worker reaching idle
# `error` is excluded since the autoscaler retries with error -> rebooting -> model_loading.
_TERMINAL_STATES = {"stopped", "destroying", "unavail"}
_TERMINAL_GRACE_SECONDS = 30  # how long a worker can sit in a terminal state before we give up on it
# statuses to use for the live table
_TERMINAL_STATUSES = {"done", "skipped", "timeout", "failed", "no_worker"}

# key in worker states that says "no worker rented yet"
_WAITING_KEY = "__waiting__"


def _format_time_elapsed(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _parse_gpu_spec(token, default_num_gpus):
    """parses the gpu arg into (gpu_name, num_gpus)
    ex. "2x RTX_4090" -> ("RTX 4090", 2)

    if both --num_gpus and inline Nx (1x, 2x, etc) prefix are given, Nx wins
    if no count per gpu isprovided, uses default num_gpus
    """

    # so users can input "rtx_4090" or "RTX 4090" or "Rtx_4090" and all resolves to "RTX 4090" 
    canonical = {
        v.lower(): v for k, v in vars(_query_consts).items()
        if isinstance(v, str) and not k.startswith("_")
    }

    token = token.strip()
    # converts "2x RTX_4090" to ("RTX 4090", 2)
    m = re.match(r"^(\d+)[\s_]*x[\s_]*(.+)$", token, re.IGNORECASE)
    if m:
        raw_name, n = m.group(2).strip().replace("_", " "), int(m.group(1))
    else:
        raw_name, n = token.replace("_", " "), default_num_gpus
    return (canonical.get(raw_name.lower(), raw_name), n)


def _format_filter_query(filters):
    """Render extra_filters dict into comparison string.
    e.g. {"gpu_ram": {"gte": 16000}} -> "gpu_ram>=16000"
    """
    parts = []
    for field, ops in (filters or {}).items():
        if not isinstance(ops, dict):
            continue
        for op, value in ops.items():
            sym = OP_TO_STR.get(op, op)
            parts.append(f"{field}{sym}{value}")
    return ", ".join(parts)


# ------------------------------------------------------------------------------------
# the next few functions are pre flight helpers 
# they check whether each (template, gpu_name, and num_gpus) is rentable
# so we dont run the benchmark only for it to fail due to 0 matching offers
# if no mathcing offers, returns user friendly msg 
# -----------------------------------------------------------------------------------


def _has_matching_offer(vast, *, gpu_name, num_gpus, extra_filters):
    """True if any verified+rentable offer matches the template's filters"""
    query = dict(extra_filters or {})
    query["gpu_name"] = {"eq": gpu_name}
    query["num_gpus"] = {"eq": num_gpus}
    return bool(vast.search_offers(query=query, limit=1))


def _format_skip_message(vast, *, gpu_name, num_gpus, extra_filters):
    """Build a user friendlyexplanation for why a GPU has 0 matching offers.
    Calls search offers to find the blocking filter
    """
    if not extra_filters:
        return (f"no offers for {gpu_name} (num_gpus={num_gpus})")

    diag = _find_blockers(
        vast, gpu_name=gpu_name, num_gpus=num_gpus,
        extra_filters=extra_filters,
    )
    if diag["base_count"] == 0:
        return (f"no offers for {gpu_name} (num_gpus={num_gpus}), "
                f"independent of template filters")

    blockers = diag["single_blockers"]
    if blockers:
        sample = diag.get("sample_offer") or {}
        blocker_lines = []
        for key in blockers:
            ops = extra_filters.get(key)
            if not isinstance(ops, dict):
                blocker_lines.append(f"  {key}")
                continue
            gpu_value = sample.get(key)
            for op, threshold in ops.items():
                if _check_template_filter(gpu_value, op, threshold) is True:
                    continue  # search-engine quirk, skip
                sym = OP_TO_STR.get(op, op)
                if gpu_value is None:
                    detail = "no sample available to check"
                else:
                    detail = f"{gpu_name} has {gpu_value}"
                blocker_lines.append(f"  {key}{sym}{threshold}: {detail}")

        if blocker_lines:
            plural = "s" if len(blocker_lines) > 1 else ""
            lines = [f"blocked by template filter{plural}:"] + blocker_lines
            # Only hint num_gpus when gpu_total_ram is the sole blocker; otherwise bumping it won't fix the run.
            if blockers == ["gpu_total_ram"]:
                ops = extra_filters.get("gpu_total_ram") or {}
                if ops:
                    op, value = next(iter(ops.items()))
                    raw = _min_gpus_for_ram(
                        value, op, diag.get("per_card_gpu_ram"))
                    if raw and raw > num_gpus:
                        viable = _get_gpu_chunk_size(raw)
                        lines.append(
                            f"  hint: try {viable}x {gpu_name} "
                            f"(host total then satisfies {value})")
            return "\n".join(lines)
        # All "blockers" turned out to be quirks; fall through to generic failure message

    return ("0 offers match. No single filter is the culprit; the combination "
            f"of template filters excludes {gpu_name} "
            f"({_format_filter_query(extra_filters)})")


def _find_blockers(vast, *, gpu_name, num_gpus, extra_filters):
    """Identify why ``_has_matching_offer`` returned False.

    Skips filters the GPU mathematically satisfies (avoids API call + dodges
    Vast search-engine quirks where a passing filter still returns 0). Bails
    on the first real blocker (user fixes one and re-runs). Returns a dict
    {base_count, single_blockers, per_card_gpu_ram, sample_offer}.
    """
    base_query = {"gpu_name": {"eq": gpu_name},
                  "num_gpus": {"eq": num_gpus}}
    base_offers = vast.search_offers(query=base_query, limit=1)
    base = len(base_offers)
    sample = base_offers[0] if base_offers else None
    per_card = sample.get("gpu_ram") if sample else None
    blockers = []
    if base > 0:
        for key, ops in (extra_filters or {}).items():
            # if GPU satisfies the given filter, its not a blocker so skip
            if isinstance(ops, dict) and sample is not None:
                gpu_value = sample.get(key)
                if gpu_value is not None and all(
                    _check_template_filter(gpu_value, op, threshold) is True
                    for op, threshold in ops.items()
                ):
                    continue
            if not _has_matching_offer(
                vast, gpu_name=gpu_name, num_gpus=num_gpus,
                extra_filters={key: ops},
            ):
                blockers.append(key)
                break
    return {"base_count": base, "single_blockers": blockers,
            "per_card_gpu_ram": per_card, "sample_offer": sample}


def _check_template_filter(gpu_value, op, threshold):
    """Checks if gpu_value matches the template filters (e.g. gpu_total_ram>=16000)"""
    if gpu_value is None or threshold is None:
        return None
    try:
        a, t = float(gpu_value), float(threshold)
    except (TypeError, ValueError):
        return None
    if op == "gt":  return a > t
    if op == "gte": return a >= t
    if op == "lt":  return a < t
    if op == "lte": return a <= t
    if op == "eq":  return a == t
    if op == "neq": return a != t
    return None


def _min_gpus_for_ram(threshold, op, per_card_gpu_ram):
    """Smallest ``num_gpus`` such that ``num_gpus * per_card_gpu_ram``
    satisfies the template's ``gpu_total_ram`` filter. Returns None if any
    input is missing or the operator isn't a comparison we can solve.
    """
    if not per_card_gpu_ram or not threshold:
        return None
    if op == "gt":
        return int(threshold // per_card_gpu_ram) + 1
    if op == "gte":
        return int(math.ceil(threshold / per_card_gpu_ram))
    return None


def _get_gpu_chunk_size(n):
    """Round n up to the next common GPU chunk size (1, 2, 4, 8). Returns n
    unchanged for >8 since that's rare enough we'd rather be honest than guess.
    """
    for c in (1, 2, 4, 8):
        if n <= c:
            return c
    return n


def _pick_num_gpus(gpu_name, extra_filters):
    """Smallest num_gpus where ``num_gpus * per_card_ram`` satisfies the
    template's ``gpu_total_ram`` filter, rounded up to a chassis size.
    Falls back to 1 when the template has no such filter or one card
    already satisfies it.
    """
    per_card = _DEFAULT_GPUS.get(gpu_name)
    if per_card is None:
        return 1
    ops = (extra_filters or {}).get("gpu_total_ram") or {}
    if not ops:
        return 1
    op, threshold = next(iter(ops.items()))
    raw_min = _min_gpus_for_ram(threshold, op, per_card)
    if raw_min is None or raw_min <= 1:
        return 1
    return _get_gpu_chunk_size(raw_min)


def _update_worker_states(worker_states, current_workers, gpu_name):
    """Update worker_states with current poll, and print only on worker
    rotation (the live rich table already shows current status / elapsed).
    Tracks state_started per worker for the terminal-state grace check.
    Returns the count of workers abandoned during this poll.
    """
    now = time.monotonic()
    abandoned = 0

    if not current_workers:
        worker_states.setdefault(_WAITING_KEY, {"started": now})
        return abandoned

    worker_states.pop(_WAITING_KEY, None)

    seen = set()
    for w in current_workers:
        wid = w.get("id")
        if wid is None:
            continue
        seen.add(wid)
        status = str(w.get("status", "")).lower()
        prev = worker_states.get(wid)
        if prev is None:
            worker_states[wid] = {"status": status, "state_started": now}
            continue
        if prev["status"] != status:
            prev["status"] = status
            prev["state_started"] = now

    for wid in list(worker_states):
        if not isinstance(wid, int):
            continue  # sentinel keys (e.g. _WAITING_KEY)
        if wid not in seen:
            # Worker abandoned; live table only shows current worker, so rotation is otherwise invisible.
            prev = worker_states[wid]
            elapsed = _format_time_elapsed(now - prev["state_started"])
            print(f"[{gpu_name}] worker {wid} abandoned "
                  f"(last state={prev['status']} for {elapsed})",
                  file=sys.stderr)
            del worker_states[wid]
            abandoned += 1
    return abandoned


def _update_row(class_states, row_id, **fields):
    """Update one GPU's row in the live-table state dict. Sets
    ``run_started`` on first non-``queued`` status and ``run_ended`` on
    terminal status (so elapsed freezes); each thread only writes its own
    key so no lock needed.
    """
    if class_states is None:
        return
    cur = class_states.setdefault(row_id, {})
    new_status = fields.get("status")
    now_ts = time.monotonic()
    if new_status and new_status != cur.get("status"):
        if "run_started" not in cur and new_status != "queued":
            cur["run_started"] = now_ts
        if new_status in _TERMINAL_STATUSES:
            cur["run_ended"] = now_ts
        else:
            cur.pop("run_ended", None)  # recovered from a transient terminal status; unfreeze elapsed
    cur.update(fields)


def _render_table(class_states):
    """Render the per-GPU progress as a rich.Table for the live display."""
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("GPU", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Endpoint", justify="right", no_wrap=True)
    table.add_column("Worker", justify="right", no_wrap=True)
    table.add_column("Elapsed", justify="right", no_wrap=True)
    table.add_column("Perf", justify="right", no_wrap=True)
    table.add_column("$/hr", justify="right", no_wrap=True)
    table.add_column("Perf/$/hr", justify="right", no_wrap=True)
    now = time.monotonic()
    for gpu in sorted(class_states):
        s = class_states[gpu]
        status = s.get("status") or "-"
        # Skipped rows are noise during the run; reason already printed at pre-flight, final summary still includes them.
        if status == "skipped":
            continue
        run_started = s.get("run_started")
        run_ended = s.get("run_ended")
        # Blank for not-yet-running, frozen for terminal, live otherwise.
        if run_started is None:
            elapsed_str = "-"
        elif run_ended is not None:
            elapsed_str = _format_time_elapsed(run_ended - run_started)
        else:
            elapsed_str = _format_time_elapsed(now - run_started)
        perf = s.get("perf")
        dph = s.get("dph")
        pps = (perf / dph) if (perf and dph) else None
        table.add_row(
            gpu,
            status,
            str(s.get("endpoint_id") or "-"),
            str(s.get("worker_id") or "-"),
            elapsed_str,
            f"{perf:.1f}" if perf else "-",
            f"${dph:.3f}" if dph else "-",
            f"{pps:.1f}" if pps else "-",
        )
    return table


def _benchmark_gpu(vast, *, gpu_name, num_gpus, timeout,
                   workergroups, endpoints,
                   template_hash=None, template_id=None,
                   auto_instance=None, autoscaler_url=None,
                   class_states=None, stop_event=None):
    """Rent one instance for ``gpu_name``, poll until idle + measured_perf,
    tear down. Each call owns its own endpoint + workergroup so it can run
    in parallel safely. Returns ``(gpu_name, num_gpus, status, perf, err, dph_total)``.
    """
    endpoint_id = None
    workergroup_id = None
    # need the uuid so the endpoint name is unique if we benchmark the same GPU in parallel
    endpoint_name = f"benchmark {num_gpus}x {gpu_name} ({uuid.uuid4().hex[:8]})"
    row_id = f"{num_gpus}x {gpu_name}" # id for the live table so 1x/2x/4x of the same GPU gets its own row
    start = time.monotonic()
    _update_row(class_states, row_id, status="provisioning")
    search = f"gpu_name={gpu_name.replace(' ', '_')} num_gpus={num_gpus}"
    if autoscaler_url:
        status_vast = VastAI(api_key=vast.client.api_key, server_url=autoscaler_url, retry=vast.client.retry)
    else:
        status_vast = vast

    try:
        endpoint_kwargs = dict(_ENDPOINT_CONFIG, endpoint_name=endpoint_name)
        if auto_instance is not None:
            endpoint_kwargs["auto_instance"] = auto_instance
        ep_resp = vast.create_endpoint(**endpoint_kwargs)
        # autoscaler returns the new id under either "result" or "id" depending on resource
        endpoint_id = ep_resp.get("result", ep_resp.get("id")) if isinstance(ep_resp, dict) else None
        if not isinstance(endpoint_id, int):
            return (gpu_name, num_gpus, "error", None,
                    f"create_endpoint returned no id: {ep_resp!r}", None)
        endpoints.add(endpoint_id)
        _update_row(class_states, row_id, endpoint_id=endpoint_id)

        # cold_workers and min_load are set on _ENDPOINT_CONFIG, not here; the autoscaler reads
        # both from the endpoint group, not the workergroup (verified via autoscaler.cpp).
        workergroup_kwargs = dict(
            endpoint_id=endpoint_id,
            endpoint_name=endpoint_name,
            search_params=search,
        )
        if template_id is not None:
            workergroup_kwargs["template_id"] = template_id
        elif template_hash is not None:
            workergroup_kwargs["template_hash"] = template_hash
        if auto_instance is not None:
            workergroup_kwargs["auto_instance"] = auto_instance
        resp = vast.create_workergroup(**workergroup_kwargs)
        workergroup_id = resp.get("result", resp.get("id")) if isinstance(resp, dict) else None
        if not isinstance(workergroup_id, int):
            return (gpu_name, num_gpus, "error", None,
                    f"create_workergroup returned no id: {resp!r}", None)
        workergroups.add(workergroup_id)
        _update_row(class_states, row_id, status="waiting_for_worker")
        worker_states = {}
        dph_by_worker = {}  # cache so we don't re-fetch dph on every poll
        abandoned_count = 0  # bail when this hits _MAX_ABANDONS; autoscaler is renting + giving up repeatedly, no progress

        while time.monotonic() - start < timeout:
            if stop_event is not None and stop_event.is_set():
                _update_row(class_states, row_id, status="aborted")
                return (gpu_name, num_gpus, "aborted", None, "user aborted", None)
            # calls get endpoint workers which includes measured perf(get workergroup workers doesnt)  
            resp = status_vast.get_endpoint_workers(endpoint_id)
            if isinstance(resp, list):
                workers = resp
            elif isinstance(resp, dict) and isinstance(resp.get("workers"), list):
                workers = resp["workers"]
            else:
                workers = []
            abandoned_count += _update_worker_states(worker_states, workers, gpu_name)
            if abandoned_count >= _MAX_ABANDONS:
                _update_row(class_states, row_id, status="failed")
                return (gpu_name, num_gpus, "failed", None,
                        f"autoscaler abandoned {abandoned_count} workers without "
                        f"any reaching idle (likely template + GPU config not loadable "
                        f"on these hosts)", None)
            if workers:
                primary = workers[0]
                primary_id = primary.get("id")
                fields = {
                    "status": str(primary.get("status") or "?").lower(),
                    "worker_id": primary_id,
                }
                # Fetch dph once per new worker_id; surfaces $/hr in the live table as soon as the autoscaler rents (before model loads).
                if primary_id and primary_id not in dph_by_worker:
                    try:
                        inst = vast.show_instance(id=primary_id)
                        dph_by_worker[primary_id] = inst.get("dph_total")
                    except Exception as e:
                        # Cache None so we don't re-attempt every poll, but log so a real bug isn't silently swallowed.
                        dph_by_worker[primary_id] = None
                        print(f"[warn] failed to fetch dph for worker {primary_id}: {e}",
                              file=sys.stderr)
                if primary_id and dph_by_worker.get(primary_id) is not None:
                    fields["dph"] = dph_by_worker[primary_id]
                _update_row(class_states, row_id, **fields)
            # measured_perf is only real once status==idle; before that it's a dlperf placeholder.
            ready = [w for w in workers
                     if str(w.get("status", "")).lower() == "idle"
                     and (w.get("measured_perf") or 0) > 0]
            if ready:
                # dph was already fetched and cached when this worker_id first appeared in polling.
                worker_id = ready[0].get("id")
                dph = dph_by_worker.get(worker_id) if worker_id else None
                _update_row(class_states, row_id, status="done",
                                 perf=ready[0]["measured_perf"], dph=dph)
                return (gpu_name, num_gpus, "ok", ready[0]["measured_perf"], None, dph)
            # Fail fast: every worker stuck terminal past the grace period, none reached idle.
            now_ts = time.monotonic()
            terminal_workers_long = workers and all(
                str(w.get("status", "")).lower() in _TERMINAL_STATES
                and isinstance(w.get("id"), int)
                and w["id"] in worker_states
                and now_ts - worker_states[w["id"]]["state_started"]
                    > _TERMINAL_GRACE_SECONDS
                for w in workers
            )
            if terminal_workers_long:
                states = sorted({str(w.get("status", "")).lower()
                                 for w in workers})
                _update_row(class_states, row_id, status="failed")
                return (gpu_name, num_gpus, "failed", None,
                        f"all workers terminal ({', '.join(states)}) for "
                        f">{_TERMINAL_GRACE_SECONDS}s without reaching idle; "
                        f"autoscaler not rotating", None)
            # Fail fast if no real worker (int id) has ever appeared.
            if (not any(isinstance(k, int) for k in worker_states)
                    and time.monotonic() - start > _RENTAL_TIMEOUT):
                _update_row(class_states, row_id, status="no_worker")
                return (gpu_name, num_gpus, "no_worker", None,
                        f"autoscaler did not rent in {_RENTAL_TIMEOUT}s "
                        f"(possible causes: insufficient credit, scoring issue, "
                        f"all candidates failed silently, or template+GPU mismatch "
                        f"missed by pre-flight)", None)
            # Jitter so N parallel threads don't all hit the autoscaler at the same instant.
            delay = _WORKER_POLL_INTERVAL + random.uniform(0, 2.0)
            if stop_event is not None:
                if stop_event.wait(timeout=delay):
                    _update_row(class_states, row_id, status="aborted")
                    return (gpu_name, num_gpus, "aborted", None, "user aborted", None)
            else:
                time.sleep(delay)

        _update_row(class_states, row_id, status="timeout")
        return (gpu_name, num_gpus, "timeout", None,
                f"no measured_perf in {timeout}s", None)
    finally:
        # Workergroup first (stops new workers), then endpoint. atexit sweeps anything we miss.
        # 404s are silently absorbed since "already gone" is the desired end state.
        if workergroup_id is not None:
            try:
                vast.delete_workergroup(id=workergroup_id)
                workergroups.discard(workergroup_id)
            except Exception as e:
                if getattr(getattr(e, "response", None), "status_code", None) != 404:
                    print(f"[cleanup] failed to delete workergroup {workergroup_id}: {e}",
                          file=sys.stderr)
                else:
                    workergroups.discard(workergroup_id)
        if endpoint_id is not None:
            try:
                vast.delete_endpoint(id=endpoint_id)
                endpoints.discard(endpoint_id)
            except Exception as e:
                if getattr(getattr(e, "response", None), "status_code", None) != 404:
                    print(f"[cleanup] failed to delete endpoint {endpoint_id}: {e}",
                          file=sys.stderr)
                else:
                    endpoints.discard(endpoint_id)


@parser.command(
    argument("--template_hash", type=str, default=None,
             help="(required, one of --template_hash or --template_id) template hash to benchmark"),
    argument("--template_id", type=int, default=None,
             help="(required, one of --template_hash or --template_id) template id"),
    argument("--gpus", type=str,
             help="comma-separated GPU names (e.g. RTX_4090,RTX_3090); optional Nx prefix takes precedence over --num_gpus (e.g. \"2x RTX_4090\")"),
    argument("--num_gpus", type=int, default=None,
             help="GPUs per instance for tokens without an Nx prefix (default 1); overridden by inline Nx in --gpus"),
    argument("--timeout", type=int, default=_DEFAULT_BENCHMARK_TIMEOUT,
             help=f"max seconds to wait for a benchmark before giving up (default {_DEFAULT_BENCHMARK_TIMEOUT})"),
    argument("-y", "--yes", action="store_true",
             help="Skip confirmation prompt"),
    argument("--auto_instance", type=str, default=None, help=argparse.SUPPRESS),
    argument("--autoscaler_url", type=str, default=None, help=argparse.SUPPRESS),
    usage="vastai run benchmarks [OPTIONS]",
    help="Benchmark a template against one or more GPUs",
    epilog=deindent("""
        Rents one instance per GPU in parallel, measures perf, tears down.
        Each rental runs for up to --timeout seconds and costs real money.

        Examples:
            # auto-sweep the default GPUs against TGI
            vastai run benchmarks --template_hash 79ebdd2ebfb9d42cedf7a221c42d37a5

            # specific GPUs against vLLM
            vastai run benchmarks --template_hash 393fa8572e6c73c927c8275fe4dffd53 --gpus RTX_4090,RTX_3090

            # multi-GPU configurations via inline Nx prefix against ComfyUI
            vastai run benchmarks --template_hash 40ef49becc953aa910ee05bd4653b9b3 --gpus "2x RTX_4090, 2x RTX_3090"

            # default count for tokens without an Nx prefix
            vastai run benchmarks --template_hash 79ebdd2ebfb9d42cedf7a221c42d37a5 --gpus RTX_4090,RTX_3090 --num_gpus 2

            # shorter timeout (30 min), skipping the cost prompt
            vastai run benchmarks --template_hash 393fa8572e6c73c927c8275fe4dffd53 --timeout 1800 -y

            # raw JSON output for piping into another tool
            vastai run benchmarks --template_hash 40ef49becc953aa910ee05bd4653b9b3 --raw
    """),
)
def run__benchmarks(args):
    if args.template_id is None and args.template_hash is None:
        print("error: one of --template_id or --template_hash is required "
              "(run `vastai run benchmarks --help` for usage)",
              file=sys.stderr)
        return 1
    # bump retry budget so parallel polls don't exhaust VastClient's tiny default (3 attempts, ~0.7s) under autoscaler rate limits.
    retry = max(args.retry, 8)
    vast = VastAI(api_key=args.api_key, server_url=args.url, retry=retry,
                  explain=getattr(args, 'explain', False),
                  curl=getattr(args, 'curl', False))

    if args.template_id is not None:
        query = {"id": {"eq": args.template_id}}
        ident = f"id={args.template_id}"
    else:
        query = {"hash_id": {"eq": args.template_hash}}
        ident = f"hash={args.template_hash}"
    templates = vast.search_templates(query=query)
    if not templates:
        print(f"error: template not found ({ident})", file=sys.stderr)
        return 1
    template = templates[0]
    try:
        extra_filters = json.loads(template.get("extra_filters") or "{}")
    except (ValueError, TypeError):
        extra_filters = {}

    template_name = template.get("name") or template.get("title") or "?"
    filter_summary = _format_filter_query(extra_filters) or "none"
    print(f"\nTemplate id={template.get('id')} {template_name}, filters: {filter_summary}")

    # if user provides specific GPU count like "2x RTX 4090", that takes precedence over --num_gpus
    if args.gpus:
        gpu_specs = [_parse_gpu_spec(t, args.num_gpus or 1)
                     for t in args.gpus.split(",") if t.strip()]
    elif args.num_gpus is not None:
        gpu_specs = [(g, args.num_gpus) for g in _DEFAULT_GPUS]
    else:
        gpu_specs = [
            (g, _pick_num_gpus(g, extra_filters))
            for g in _DEFAULT_GPUS
        ]

    console = Console(stderr=True)

    # deduplicates (gpu, num_gpus) so we dont benchmark the same GPU config twice 
    seen = set()
    deduped = []
    for g, n in gpu_specs:
        if (g, n) in seen:
            console.print(f"[yellow]skipping duplicate spec {n}x {g}[/yellow]",
                          highlight=False)
            continue
        seen.add((g, n))
        deduped.append((g, n))
    gpu_specs = deduped

    # Pre-flight: skip GPU specs that have 0 matching offers before prompting,
    # so the user sees skip reasons before approving the rentals.
    compatible_specs = []
    skipped_results = []
    for g, n in gpu_specs:
        if not _has_matching_offer(
            vast, gpu_name=g, num_gpus=n,
            extra_filters=extra_filters,
        ):
            msg = _format_skip_message(
                vast, gpu_name=g, num_gpus=n,
                extra_filters=extra_filters,
            )
            console.print(f"[yellow][{n}x {g}] skipping:[/yellow] {msg}",
                          highlight=False)
            skipped_results.append((g, n, "skipped", None, msg, None))
        else:
            compatible_specs.append((g, n))

    timeout_minutes = args.timeout / 60.0
    n = len(compatible_specs)
    if n == 0:
        console.print(
            "\nNo compatible GPUs to benchmark for this template.",
            style="bold red")
        return _print_results(args, skipped_results)

    spec_strs = [f"{cnt}x {gpu}" for gpu, cnt in compatible_specs]
    spec_summary = ", ".join(spec_strs)
    if n == 1:
        print(f"\nWill rent 1 GPU configuration ({spec_summary}). "
              f"Each runs ~2 to {timeout_minutes:.0f} min.")
    else:
        print(f"\nWill rent {n} GPU configurations in parallel "
              f"({spec_summary}). Each runs ~2 to {timeout_minutes:.0f} min.")
    print("This rents real GPUs and charges your account for usage.")
    if not args.yes:
        if input("Continue? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Aborted.", file=sys.stderr)
            sys.exit(130)
    print()

    # Backing sets for the atexit sweep; per-GPU teardown discards on success.
    workergroups = set()
    endpoints = set()
    stop_event = threading.Event()

    def _cleanup():
        # Mask SIGINT + catch BaseException so a second Ctrl+C can't leak records mid-iteration.
        prev_handler = None
        try:
            prev_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        except (ValueError, OSError):
            pass
        try:
            for workergroup_id in list(workergroups):
                try:
                    vast.delete_workergroup(id=workergroup_id)
                    workergroups.discard(workergroup_id)
                except BaseException:
                    pass
            for ep_id in list(endpoints):
                try:
                    vast.delete_endpoint(id=ep_id)
                    endpoints.discard(ep_id)
                except BaseException:
                    pass
        finally:
            if prev_handler is not None:
                try:
                    signal.signal(signal.SIGINT, prev_handler)
                except (ValueError, OSError):
                    pass
    atexit.register(_cleanup)

    # Live-table state. Pre-populate every GPU so the table is complete.
    class_states = {}
    for g, n in compatible_specs:
        _update_row(class_states, f"{n}x {g}", status="queued")
    for sr in skipped_results:
        _update_row(class_states, f"{sr[1]}x {sr[0]}", status="skipped")

    def _run_one_gpu(g, n):
        try:
            return _benchmark_gpu(
                vast,
                gpu_name=g,
                num_gpus=n,
                timeout=args.timeout,
                workergroups=workergroups,
                endpoints=endpoints,
                template_hash=args.template_hash,
                template_id=args.template_id,
                auto_instance=args.auto_instance,
                autoscaler_url=args.autoscaler_url,
                class_states=class_states,
                stop_event=stop_event,
            )
        except Exception as e:
            _update_row(class_states, f"{n}x {g}", status="error")
            # Surface response body for HTTPError so backend rate-limit / validation
            # messages aren't swallowed (default __str__ on HTTPError just shows the URL).
            body = ""
            resp = getattr(e, "response", None)
            if resp is not None:
                try:
                    body = f" | body: {resp.text[:500]}"
                except Exception:
                    pass
            return (g, n, "error", None, f"{type(e).__name__}: {e}{body}", None)

    run_results = []
    executor = ThreadPoolExecutor(max_workers=len(compatible_specs))
    try:
        # Stagger submits to keep cold-start POSTs from tripping rate limits.
        futures = []
        for i, (g, n_for_class) in enumerate(compatible_specs):
            futures.append(executor.submit(_run_one_gpu, g, n_for_class))
            if i < len(compatible_specs) - 1:
                time.sleep(_PARALLEL_SUBMIT_DELAY)
        try:
            with Live(_render_table(class_states), console=console,
                      refresh_per_second=2, transient=False) as live:
                pending = set(futures)
                while pending:
                    done, pending = wait(pending, timeout=0.5,
                                         return_when=FIRST_COMPLETED)
                    for fut in done:
                        result = fut.result()
                        run_results.append(result)
                        # Surface failures live above the table.
                        g, n, status, _perf, err, _price = result
                        if status not in ("ok", "skipped") and err:
                            console.print(
                                f"[red][{n}x {g}] {status}:[/red] {err}",
                                highlight=False)
                    live.update(_render_table(class_states))
        except KeyboardInterrupt:
            # Set stop_event so threads exit their poll/sleep immediately, then cleanup synchronously.
            console.print(
                "\n[yellow]Deleting endpoints, please wait... "
                "If you exit now, you'll need to delete them manually with `vastai delete endpoint`.[/yellow]",
                highlight=False)
            stop_event.set()
            executor.shutdown(wait=False, cancel_futures=True)
            _cleanup()
            sys.exit(130)
    finally:
        executor.shutdown(wait=True)
        _cleanup()

    results = skipped_results + run_results
    return _print_results(args, results)


def _print_results(args, results):
    rows = []
    for gpu, num_gpus, status, perf, err, price in results:
        pps = (perf / price) if (perf and price) else None
        rows.append({
            "gpu_name": gpu,
            "num_gpus": num_gpus,
            "rental_dph": price,
            "measured_perf": perf,
            "status": status,
            "perf_per_dollar": pps,
        })
    rows.sort(key=lambda r: (r["perf_per_dollar"] or -1), reverse=True)

    if args.raw:
        return rows

    n_ok = sum(1 for r in rows if r["status"] == "ok")
    print(f"\nBenchmark complete: {n_ok}/{len(rows)} GPUs measured.")
