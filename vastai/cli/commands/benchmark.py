"""vastai benchmark run — rent instances, measure perf/$, tear down.

Serial execution. One ephemeral endpoint per run (named ``benchmark-<uuid8>``),
deleted at the end. Per-class workergroup is created, polled for
``measured_perf``, and torn down in a ``finally`` block. An ``atexit``
hook is the fallback if the process exits through ``sys.exit`` before the
finally runs.

Template is supplied by the caller via --template-id or --template-hash.
Note: not every template produces a usable perf score across GPU classes —
some saturate. TGI 1.0.3 (id 79663) has been verified not to saturate.
"""

import argparse
import atexit
import json
import math
import sys
import time
import uuid

from vastai.cli.parser import argument
from vastai.cli.display import deindent, display_table
from vastai.cli.utils import get_parser as _get_parser, get_client

from vastai.api import endpoints as endpoints_api
from vastai.api import instances as instances_api
from vastai.api import offers as offers_api


parser = _get_parser()


# Default class list — most popular serverless GPUs. Placeholder picks until
# we have real popularity data; the consumer flagships (4090, 5090) plus the
# two datacenter staples (H100, A100). Caller's template extra_filters may
# silently exclude classes that don't fit its VRAM/CUDA gates, so this list
# only matters when the template is permissive enough to accept all of them.
_DEFAULT_GPUS = [
    "RTX 4090",
    "RTX 5090",
    "H100 SXM",
    "A100 SXM4",
]

# cold_workers=1 at endpoint level is what drives min_to_create=1 in the
# autoscaler (asm_ratio_manager.cpp:1055-1058). Without it, scale-to-zero
# keeps the workergroup from ever renting.
_ENDPOINT_CONFIG = {
    "cold_workers": 1,
    "min_load": 0.0,
    "min_cold_load": 0.0,
    "max_workers": 10,
}

_POLL_INTERVAL = 10.0
# 30 min default: the autoscaler's own loading timeout is ~13 min (measured
# 2026-04-27: 788s on a RTX 3060 run), so one bad host burns 13 min before
# the autoscaler reboots/rotates; the next attempt needs ~3 min Docker pull
# + ~3 min model load + ~1 min first benchmark batch. 30 min covers one bad
# host + one good host with a few minutes of slack.
_DEFAULT_TIMEOUT = 30 * 60

# If the autoscaler hasn't rented anything in this window, something's wrong
# (zero matching offers, scoring issue, all candidates failing silently).
# Bailing here costs at most ~2 min instead of the full --timeout.
_NO_WORKER_TIMEOUT = 120


def _extract_id(resp, *keys):
    if not isinstance(resp, dict):
        return None
    for k in keys:
        v = resp.get(k)
        if isinstance(v, int):
            return v
    results = resp.get("results") if "results" in resp else None
    if isinstance(results, dict):
        for k in keys:
            v = results.get(k)
            if isinstance(v, int):
                return v
    return None


def _normalize_workers(resp):
    if isinstance(resp, list):
        return resp
    if isinstance(resp, dict):
        workers = resp.get("workers")
        if isinstance(workers, list):
            return workers
    return []


def _format_elapsed(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _fetch_template(client, *, template_id=None, template_hash=None):
    """Look up a template by id (preferred) or hash. Returns dict or None."""
    if template_id is not None:
        templates = offers_api.search_templates(
            client, query={"id": {"eq": template_id}})
    elif template_hash is not None:
        templates = offers_api.search_templates(
            client, query={"hash_id": {"eq": template_hash}})
    else:
        return None
    return templates[0] if templates else None


def _parse_extra_filters(extra_filters_json):
    """Parse the JSON-string extra_filters field from a template.

    Returns an empty dict on missing/invalid input — pre-flight just degrades
    to "GPU-name + num_gpus only" rather than failing loudly.
    """
    if not extra_filters_json:
        return {}
    try:
        return json.loads(extra_filters_json)
    except (ValueError, TypeError):
        return {}


_FILTER_OP_SYMBOL = {
    "gt": ">", "gte": ">=", "lt": "<", "lte": "<=",
    "eq": "==", "neq": "!=", "in": "in", "notin": "notin",
}


def _format_filter_query(filters):
    """Render an extra_filters dict back into comparison strings.

    e.g. {"gpu_ram": {"gte": 16000}} -> "gpu_ram>=16000"
    Unknown operators fall through as-is rather than being dropped, so a
    surprise from the backend is visible rather than silently swallowed.
    """
    parts = []
    for field, ops in (filters or {}).items():
        if not isinstance(ops, dict):
            continue
        for op, value in ops.items():
            sym = _FILTER_OP_SYMBOL.get(op, op)
            if op in ("in", "notin"):
                parts.append(f"{field} {sym} {value}")
            else:
                parts.append(f"{field}{sym}{value}")
    return ", ".join(parts)


def _count_matching_offers(client, *, gpu_class, num_gpus, extra_filters):
    """Return how many verified+rentable offers match the template's filters.

    Uses ``search_offers`` (default filters add verified=True, rentable=True,
    rented=False, external=False) plus the template's ``extra_filters`` plus
    the same ``geolocation=US`` we apply at workergroup creation. ``limit=1``
    because we only need to know if any exist.
    """
    query = dict(extra_filters or {})
    query["gpu_name"] = {"eq": gpu_class}
    query["num_gpus"] = {"eq": num_gpus}
    query["geolocation"] = {"eq": "US"}
    offers = offers_api.search_offers(client, query=query, limit=1)
    return len(offers)


def _skip_message_for_zero_offers(client, *, gpu_class, num_gpus, extra_filters):
    """Build a human-readable explanation for why a class has 0 matching offers.

    Skips the diagnostic API calls when there are no template filters (nothing
    to attribute the zero to). When there are filters, runs the diagnosis and
    surfaces the actual blocker (single filter, multi-filter, or no offers at
    all for the GPU class).
    """
    if not extra_filters:
        return (f"no offers for {gpu_class} (num_gpus={num_gpus}, geo=US)")

    diag = _diagnose_offer_zero(
        client, gpu_class=gpu_class, num_gpus=num_gpus,
        extra_filters=extra_filters,
    )
    if diag["base_count"] == 0:
        return (f"no offers for {gpu_class} (num_gpus={num_gpus}, geo=US) "
                f"— independent of template filters")

    blockers = diag["single_blockers"]
    if blockers:
        sample = diag.get("sample_offer") or {}
        plural = "s" if len(blockers) > 1 else ""
        lines = [f"blocked by template filter{plural}:"]
        for key in blockers:
            ops = extra_filters.get(key)
            if not isinstance(ops, dict):
                lines.append(f"  {key}")
                continue
            for op, threshold in ops.items():
                sym = _FILTER_OP_SYMBOL.get(op, op)
                actual = sample.get(key)
                # Compose "{key}{sym}{threshold}: detail"
                if actual is None:
                    detail = "no sample available to check"
                elif _filter_satisfied(actual, op, threshold) is True:
                    # Filter is supposed to admit this value but the search
                    # endpoint returned 0 offers. Most likely a search-engine
                    # quirk (we've seen this with cuda_max_good comparisons).
                    detail = (f"{gpu_class} has {actual}, should pass "
                              f"(possible search-engine quirk)")
                else:
                    detail = f"{gpu_class} has {actual}"
                lines.append(f"  {key}{sym}{threshold}: {detail}")
        # Suggest a higher --num-gpus when gpu_total_ram is the ONLY blocker.
        # If there are other single-filter blockers (e.g., compute_cap on a
        # too-new GPU), bumping num_gpus alone won't fix the run, so we stay
        # quiet rather than mislead.
        if blockers == ["gpu_total_ram"]:
            ops = extra_filters.get("gpu_total_ram") or {}
            if ops:
                op, value = next(iter(ops.items()))
                suggested = _min_num_gpus_for_total_ram(
                    value, op, diag.get("per_card_gpu_ram"))
                if suggested and suggested > num_gpus:
                    lines.append(f"  hint: try --num-gpus {suggested} for "
                                 f"{gpu_class} (host total then satisfies "
                                 f"{value})")
        return "\n".join(lines)

    # No single filter is sufficient — combination of filters is the culprit.
    return ("0 offers match — no single filter is the culprit, the combination "
            f"of template filters excludes {gpu_class} "
            f"({_format_filter_query(extra_filters)})")


def _suggest_compatible_gpus(client, *, num_gpus, extra_filters, top_k=8,
                             sample_limit=200):
    """Discover GPU classes that have offers matching the template's filters.

    Queries offers with the template's ``extra_filters`` but no ``gpu_name``
    constraint, groups results by ``gpu_name``, and returns the top-K classes
    by offer count (which roughly corresponds to supply / availability).
    """
    query = dict(extra_filters or {})
    query["num_gpus"] = {"eq": num_gpus}
    query["geolocation"] = {"eq": "US"}
    offers = offers_api.search_offers(client, query=query, limit=sample_limit)
    counts = {}
    for o in offers:
        name = o.get("gpu_name")
        if name:
            counts[name] = counts.get(name, 0) + 1
    return [name for name, _ in
            sorted(counts.items(), key=lambda x: -x[1])[:top_k]]


def _diagnose_offer_zero(client, *, gpu_class, num_gpus, extra_filters):
    """Identify why ``_count_matching_offers`` returned 0.

    Performs N+1 small offer searches (N = number of template filters) to find
    out:
      - whether the GPU class has any offers at all (independent of template)
      - which individual filters alone exclude every offer for this class
      - the per-card ``gpu_ram`` for this class (read from the same base
        query, so callers can suggest a higher --num-gpus when
        ``gpu_total_ram`` is the blocker)

    Returns a dict {base_count, single_blockers, per_card_gpu_ram}.
    """
    base_query = {"gpu_name": {"eq": gpu_class},
                  "num_gpus": {"eq": num_gpus},
                  "geolocation": {"eq": "US"}}
    base_offers = offers_api.search_offers(client, query=base_query, limit=1)
    base = len(base_offers)
    sample = base_offers[0] if base_offers else None
    per_card = sample.get("gpu_ram") if sample else None
    blockers = []
    if base > 0:
        for key, op in (extra_filters or {}).items():
            single = _count_matching_offers(
                client, gpu_class=gpu_class, num_gpus=num_gpus,
                extra_filters={key: op},
            )
            if single == 0:
                blockers.append(key)
    return {"base_count": base, "single_blockers": blockers,
            "per_card_gpu_ram": per_card, "sample_offer": sample}


def _filter_satisfied(actual, op, threshold):
    """Does ``actual`` satisfy the comparison ``op threshold``? Returns True,
    False, or None if either input is missing or the operator is unsupported.
    """
    if actual is None or threshold is None:
        return None
    try:
        a, t = float(actual), float(threshold)
    except (TypeError, ValueError):
        if op in ("eq",):  return actual == threshold
        if op in ("neq",): return actual != threshold
        return None
    if op == "gt":  return a > t
    if op == "gte": return a >= t
    if op == "lt":  return a < t
    if op == "lte": return a <= t
    if op == "eq":  return a == t
    if op == "neq": return a != t
    return None


def _min_num_gpus_for_total_ram(threshold, op, per_card_gpu_ram):
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


# Worker states surfaced by the autoscaler (vast/autoscaler/types.h ObservedState):
# happy path:   pending -> creating -> created -> loading -> model_loading -> idle
# failure:      error, unavail, destroying, stopping, stopped
# transient:    starting, rebooting
_HEARTBEAT_INTERVAL = 120

# Terminal states: a worker that lands here won't return to idle on its own.
# When all current workers are in one of these and no measured_perf has been
# produced, the run is dead and we should fail fast rather than wait out the
# full --timeout. Excludes ``stopping`` (still transitioning), ``rebooting``
# (recovering), and ``error`` (autoscaler restarts errored workers via
# ``error -> rebooting -> model_loading`` — observed live 2026-04-27 on a
# RTX 3060 run that hit the autoscaler's loading timeout).
_TERMINAL_STATES = {"stopped", "destroying", "unavail"}

# Seconds a worker must remain in a terminal state before we declare the run
# dead. Just a margin for brief transient blips during autoscaler rotation
# (rotations we've observed complete within ~2 seconds, so 30s is generous).
# We rely on "ALL workers terminal" — if autoscaler rotates by spawning a new
# worker, that worker is in pending/creating and breaks the all-terminal check
# regardless of debounce length.
_TERMINAL_DEBOUNCE = 30


# Sentinel key in worker_states for tracking "autoscaler hasn't rented yet"
# heartbeats. String-keyed so it can never collide with a real worker id (int).
_WAITING_KEY = "__waiting__"


def _emit_progress(worker_states, current_workers, gpu_class):
    """Print worker state-transition events to stderr.

    Tracks each worker by id; prints on first sight, on status change,
    every _HEARTBEAT_INTERVAL seconds while a worker stays in the same
    state (so a 5-min Docker pull doesn't go silent), and on abandonment
    (worker_id disappears — usually the autoscaler rotating a stuck host).
    Also emits a "waiting for autoscaler" heartbeat before the first worker
    appears, so the user isn't staring at a blank terminal during the
    initial rent-decision window. Mutates worker_states.
    """
    now = time.monotonic()

    if not current_workers:
        meta = worker_states.get(_WAITING_KEY)
        if meta is None:
            print(f"[{gpu_class}] waiting for autoscaler to rent a "
                  f"{gpu_class}...", file=sys.stderr)
            worker_states[_WAITING_KEY] = {"started": now, "last_heartbeat": now}
        elif now - meta["last_heartbeat"] >= _HEARTBEAT_INTERVAL:
            elapsed = _format_elapsed(now - meta["started"])
            print(f"[{gpu_class}] still waiting for a {gpu_class} offer "
                  f"({elapsed})", file=sys.stderr)
            meta["last_heartbeat"] = now
        return

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
            print(f"[{gpu_class}] worker {wid}: {status}", file=sys.stderr)
            worker_states[wid] = {
                "status": status,
                "state_started": now,
                "last_heartbeat": now,
            }
            continue
        if prev["status"] != status:
            elapsed = _format_elapsed(now - prev["state_started"])
            print(f"[{gpu_class}] worker {wid}: {prev['status']} -> {status} "
                  f"({elapsed})", file=sys.stderr)
            prev["status"] = status
            prev["state_started"] = now
            prev["last_heartbeat"] = now
        elif now - prev["last_heartbeat"] >= _HEARTBEAT_INTERVAL:
            in_state = _format_elapsed(now - prev["state_started"])
            extra = ""
            if status == "loading" and w.get("disk_usage"):
                extra = f", {w['disk_usage']:.1f} GB pulled"
            print(f"[{gpu_class}] worker {wid}: still {status} "
                  f"({in_state}{extra})", file=sys.stderr)
            prev["last_heartbeat"] = now

    for wid in list(worker_states):
        if not isinstance(wid, int):
            continue  # sentinel keys (e.g. _WAITING_KEY)
        if wid not in seen:
            prev = worker_states[wid]
            elapsed = _format_elapsed(now - prev["state_started"])
            print(f"[{gpu_class}] worker {wid} abandoned "
                  f"(last state={prev['status']} for {elapsed})",
                  file=sys.stderr)
            del worker_states[wid]


def _instance_dph_total(client, instance_id):
    """Look up the actual ``dph_total`` for a rented instance.

    Returns the instance's billed price-per-hour (host base + storage; Vast's
    fee is already embedded in the host base). Falls back to None on lookup
    failure so a missing price doesn't kill the benchmark result.
    """
    try:
        inst = instances_api.show_instance(client, id=instance_id)
        return inst.get("dph_total")
    except Exception:
        return None


def _autoscaler_status_client(client, autoscaler_url):
    """Return a client whose ``server_url`` targets the autoscaler we're
    debugging. ``get_endpoint_workers`` builds its URL from the client's
    ``server_url``, so handing it a localhost-pointing client routes status
    polls to a dev autoscaler shard instead of run.vast.ai.
    """
    if not autoscaler_url:
        return client
    from vastai.api.client import VastClient
    return VastClient(api_key=client.api_key, server_url=autoscaler_url)


def _benchmark_one(client, *, endpoint_id, endpoint_name, gpu_class,
                   num_gpus, timeout, active, template_hash=None,
                   template_id=None, auto_instance=None, autoscaler_url=None):
    """Rent one instance, poll for measured_perf, tear down.

    Teardown runs in the ``finally`` regardless of exit path. ``active`` is
    the orchestrator's set of undeleted workergroup IDs; we add on create
    and remove on confirmed delete so the atexit sweep can catch anything
    we miss.

    Returns a 5-tuple ``(gpu_class, status, perf, err, dph_total)`` where
    ``dph_total`` is the rented instance's actual ``$/hr`` (None unless
    status == "ok" and the instance lookup succeeds).
    """
    wg_id = None
    start = time.monotonic()
    # US-only until we understand why the autoscaler's scoring keeps picking
    # trans-pacific hosts whose Docker pull stalls or silently fails. See
    # the 2026-04-24 session log for the failure pattern (2/2 runs killed
    # by CN hosts even with a 30-min timeout).
    search = (
        f"gpu_name={gpu_class.replace(' ', '_')} "
        f"num_gpus={num_gpus} "
        f"geolocation=US"
    )
    # Use a dedicated client for status polling so --autoscaler-url can route
    # those calls to a local autoscaler shard while everything else (offer
    # search, endpoint/workergroup CRUD) stays on prod.
    status_client = _autoscaler_status_client(client, autoscaler_url)

    try:
        # Snapshot worker IDs already attached to the endpoint BEFORE we create
        # our workergroup. delete_workergroup removes the workergroup record
        # but the autoscaler doesn't immediately destroy the rented worker, so
        # the previous class's worker can linger as `idle` with its old
        # measured_perf value. Without this filter we'd report that lingering
        # worker's perf as the new class's result. See: a run where 5 classes
        # all returned the H100 SXM's 628.6 perf because worker 35713135 stuck
        # around between iterations.
        preexisting_worker_ids = {
            w["id"] for w in _normalize_workers(
                endpoints_api.get_endpoint_workers(status_client, endpoint_id))
            if isinstance(w.get("id"), int)
        }

        wg_kwargs = dict(
            endpoint_id=endpoint_id,
            endpoint_name=endpoint_name,
            search_params=search,
            test_workers=1,
            cold_workers=0,
            min_load=0.0,
        )
        # Caller is expected to have validated that at least one is set;
        # --template-id wins because --template-hash can resolve to a stale
        # template_id silently (serverless-bugs.md #6).
        if template_id is not None:
            wg_kwargs["template_id"] = template_id
        elif template_hash is not None:
            wg_kwargs["template_hash"] = template_hash
        if auto_instance is not None:
            wg_kwargs["auto_instance"] = auto_instance
        resp = endpoints_api.create_workergroup(client, **wg_kwargs)
        wg_id = _extract_id(resp, "result", "autojob_id", "id")
        if wg_id is None:
            return (gpu_class, "error", None,
                    f"create_workergroup returned no id: {resp!r}", None)
        active.add(wg_id)
        print(f"[{gpu_class}] workergroup {wg_id} created", file=sys.stderr)
        worker_states = {}

        while time.monotonic() - start < timeout:
            # Poll at endpoint level: get_workergroup_workers gates measured_perf
            # behind ready_ever_ which never flips for a benchmark-only worker.
            # The endpoint-level handler exposes measured_perf unconditionally.
            all_workers = _normalize_workers(
                endpoints_api.get_endpoint_workers(status_client, endpoint_id)
            )
            # Only consider workers whose id wasn't on the endpoint at the
            # start of this iteration — those are the ones our workergroup
            # rented. Leftover workers from prior classes have the wrong
            # measured_perf attached.
            workers = [w for w in all_workers
                       if w.get("id") not in preexisting_worker_ids]
            _emit_progress(worker_states, workers, gpu_class)
            # Require status=="idle" before accepting measured_perf. The
            # autoscaler pre-populates `pw->perf_` from dlperf (~12 for 3060)
            # as soon as the offer is scored, then replaces it with the real
            # throughput only after pyworker reports max_perf post-benchmark.
            # That pyworker report is also what triggers the transition to
            # idle (autoscaler log: "model_loading -> idle (received loadtime)").
            ready = [w for w in workers
                     if str(w.get("status", "")).lower() == "idle"
                     and (w.get("measured_perf") or 0) > 0]
            if ready:
                # Fetch the rented instance's actual dph_total. The
                # autoscaler's get_endpoint_workers payload doesn't include
                # price, so this is one extra GET /instances/<id>/ per
                # successful class. Failure is non-fatal: we still return
                # the measured_perf, just with price=None.
                worker_id = ready[0].get("id")
                dph = (_instance_dph_total(client, worker_id)
                       if worker_id else None)
                return (gpu_class, "ok", ready[0]["measured_perf"], None, dph)
            # Fail fast when every worker has been in a terminal state for at
            # least _TERMINAL_DEBOUNCE seconds without producing measured_perf.
            # Per-worker state duration (tracked by _emit_progress in
            # ``state_started``) reacts much faster than the absolute elapsed
            # time would: if a worker dies 30s after spawning, we exit ~60s
            # in instead of waiting out the original 120s gate.
            now_ts = time.monotonic()
            terminal_workers_long = workers and all(
                str(w.get("status", "")).lower() in _TERMINAL_STATES
                and isinstance(w.get("id"), int)
                and w["id"] in worker_states
                and now_ts - worker_states[w["id"]]["state_started"]
                    > _TERMINAL_DEBOUNCE
                for w in workers
            )
            if (terminal_workers_long
                    and not any((w.get("measured_perf") or 0) > 0
                                for w in workers)):
                states = sorted({str(w.get("status", "")).lower()
                                 for w in workers})
                return (gpu_class, "failed", None,
                        f"all workers terminal ({', '.join(states)}) for "
                        f">{_TERMINAL_DEBOUNCE}s without measured_perf — "
                        f"autoscaler not rotating (cold_workers=0)", None)
            # Fail fast if no worker has appeared after the no-worker window.
            # `worker_states` keys that are int are real worker ids (the
            # _WAITING_KEY sentinel is a string); if none ever materialized,
            # the autoscaler isn't going to find one in the remaining budget.
            if (not any(isinstance(k, int) for k in worker_states)
                    and time.monotonic() - start > _NO_WORKER_TIMEOUT):
                return (gpu_class, "no_worker", None,
                        f"autoscaler did not rent in {_NO_WORKER_TIMEOUT}s "
                        f"(scoring issue, all candidates failed silently, "
                        f"or template+GPU mismatch missed by pre-flight)", None)
            time.sleep(_POLL_INTERVAL)

        return (gpu_class, "timeout", None,
                f"no measured_perf in {timeout}s", None)
    finally:
        if wg_id is not None:
            try:
                endpoints_api.delete_workergroup(client, id=wg_id)
                active.discard(wg_id)
            except Exception as e:
                print(f"[cleanup] failed to delete workergroup {wg_id}: {e}",
                      file=sys.stderr)


@parser.command(
    argument("--gpus", type=str,
             help="Comma-separated GPU names. Same format as "
                  "`vastai search offers`: encode spaces as underscores, "
                  "or quote the whole arg with real spaces. "
                  "Examples: --gpus RTX_4080,RTX_3060   "
                  "--gpus \"RTX 4080,RTX 3060\". "
                  "If omitted, auto-discovers GPU classes with the most "
                  "offers matching this template's extra_filters; falls back "
                  "to a hardcoded default list if discovery returns nothing."),
    argument("--num-gpus", type=int, default=1,
             help="Number of GPUs per instance (default 1)"),
    argument("--timeout", type=int, default=_DEFAULT_TIMEOUT,
             help=f"Per-GPU safety ceiling in seconds (default "
                  f"{_DEFAULT_TIMEOUT}). Most runs finish well before this; "
                  f"the autoscaler's own adaptive loading timeout fires first "
                  f"for known templates (~13 min for TGI 1.0.3). This bound "
                  f"matters for fresh / uncommon templates where the "
                  f"autoscaler defaults to a 3-hour ceiling."),
    argument("--yes", "-y", action="store_true",
             help="Skip cost-disclosure prompt"),
    argument("--template-hash", type=str, default=None,
             help="Template hash to benchmark. One of --template-hash or "
                  "--template-id is required. Note: --template-hash can resolve "
                  "to the wrong template_id silently (serverless-bugs.md #6); "
                  "prefer --template-id when you have it."),
    argument("--template-id", type=int, default=None,
             help="Template id to benchmark. One of --template-hash or "
                  "--template-id is required. Wins over --template-hash if both "
                  "are passed."),
    # Hidden dev flag — pins the endpoint + workergroup to a local autoscaler
    # shard (e.g. "zuby") so dev can test against a docker-hosted autoscaler.
    # Real GPU rentals still happen unless the autoscaler is in sim mode.
    argument("--auto-instance", type=str, default=None, help=argparse.SUPPRESS),
    # Hidden dev flag — when working against a local autoscaler shard, the
    # default get_endpoint_workers URL (run.vast.ai) won't see the locally-
    # managed workers. Pointing at e.g. http://localhost:8080 routes status
    # polls to the local autoscaler. Customers should never need this.
    argument("--autoscaler-url", type=str, default=None, help=argparse.SUPPRESS),
    usage="vastai benchmark run (--template-id ID | --template-hash HASH) [OPTIONS]",
    help="Rent fresh instances, run pyworker benchmark, record measured perf/$",
    epilog=deindent("""
        Rents one instance per GPU class serially, measures perf, tears down.
        Uses an ephemeral endpoint named ``benchmark-<uuid8>`` that is
        created and deleted per run.

        REAL MONEY: each class rents a GPU for up to --timeout seconds.
        Cleanup runs on Ctrl-C, exceptions, timeouts, and sys.exit.

        Examples:
            vastai benchmark run --template-id 79663
            vastai benchmark run --template-hash 3f19d605a70f4896e8a717dfe6b517a2
            vastai benchmark run --template-id 79663 --gpus RTX_4080,RTX_3060
            vastai benchmark run --template-id 79663 --timeout 600 -y
    """),
)
def benchmark__run(args):
    if args.template_id is None and args.template_hash is None:
        print("error: one of --template-id or --template-hash is required",
              file=sys.stderr)
        return 2
    client = get_client(args)

    # Fail fast if the template can't be resolved at all.
    template = _fetch_template(client, template_id=args.template_id,
                               template_hash=args.template_hash)
    if template is None:
        ident = (f"id={args.template_id}" if args.template_id is not None
                 else f"hash={args.template_hash}")
        print(f"error: template not found ({ident})", file=sys.stderr)
        return 1
    extra_filters = _parse_extra_filters(template.get("extra_filters"))

    # Auto-discover GPU classes when --gpus isn't specified. Picks the classes
    # with the most offers matching the template's extra_filters, so the user
    # gets a sensible default without having to know the template's VRAM/CUDA
    # gates. Hardcoded _DEFAULT_GPUS is the last-resort fallback if discovery
    # comes up empty (rare; usually means no US offers right now).
    if args.gpus:
        gpu_classes = [g.strip().replace("_", " ") for g in args.gpus.split(",")]
    else:
        discovered = _suggest_compatible_gpus(
            client, num_gpus=args.num_gpus, extra_filters=extra_filters, top_k=5,
        )
        if discovered:
            gpu_classes = discovered
            print(f"Auto-detected GPU classes from template: "
                  f"{', '.join(gpu_classes)}", file=sys.stderr)
        else:
            gpu_classes = list(_DEFAULT_GPUS)
            print(f"warning: no GPU classes match this template's filters at "
                  f"num_gpus={args.num_gpus}; falling back to default list "
                  f"(all classes likely to skip)", file=sys.stderr)

    # Pre-run disclosure. No price estimate here; actual rental dph_total is
    # captured per instance after it comes up (via show_instance) and shown in
    # the result table.
    timeout_minutes = args.timeout / 60.0
    n = len(gpu_classes)
    print(f"Will rent {n} GPU{'s' if n != 1 else ''} (one at a time) for up "
          f"to {timeout_minutes:.0f} min each. Actual $/hr per GPU is shown "
          f"in the result table after the rental is live.")
    if not args.yes:
        if input("Continue? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Aborted.", file=sys.stderr)
            return 130

    # Provision ephemeral endpoint.
    endpoint_name = f"benchmark-{uuid.uuid4().hex[:8]}"
    ep_kwargs = dict(_ENDPOINT_CONFIG, endpoint_name=endpoint_name)
    if args.auto_instance is not None:
        ep_kwargs["auto_instance"] = args.auto_instance
    ep_resp = endpoints_api.create_endpoint(client, **ep_kwargs)
    endpoint_id = _extract_id(ep_resp, "result", "endpoint_id", "id")
    if endpoint_id is None:
        print(f"create_endpoint returned no id: {ep_resp!r}", file=sys.stderr)
        return 1
    print(f"endpoint {endpoint_id} created", file=sys.stderr)

    active = set()

    def _cleanup():
        for wg_id in list(active):
            try:
                endpoints_api.delete_workergroup(client, id=wg_id)
                active.discard(wg_id)
            except Exception:
                pass
        try:
            endpoints_api.delete_endpoint(client, id=endpoint_id)
        except Exception:
            pass
    atexit.register(_cleanup)

    results = []
    try:
        for g in gpu_classes:
            try:
                # Pre-flight: skip classes the template's extra_filters exclude.
                # Catches the common "wrong-VRAM template" failure without
                # spending the full --timeout in the autoscaler.
                offer_count = _count_matching_offers(
                    client, gpu_class=g, num_gpus=args.num_gpus,
                    extra_filters=extra_filters,
                )
                if offer_count == 0:
                    msg = _skip_message_for_zero_offers(
                        client, gpu_class=g, num_gpus=args.num_gpus,
                        extra_filters=extra_filters,
                    )
                    print(f"[{g}] skipping: {msg}", file=sys.stderr)
                    results.append((g, "no_offers", None, msg, None))
                    continue
                results.append(_benchmark_one(
                    client,
                    endpoint_id=endpoint_id,
                    endpoint_name=endpoint_name,
                    gpu_class=g,
                    num_gpus=args.num_gpus,
                    timeout=args.timeout,
                    active=active,
                    template_hash=args.template_hash,
                    template_id=args.template_id,
                    auto_instance=args.auto_instance,
                    autoscaler_url=args.autoscaler_url,
                ))
            except KeyboardInterrupt:
                raise
            except Exception as e:
                results.append((g, "error", None,
                                f"{type(e).__name__}: {e}", None))
    finally:
        _cleanup()

    # If the user passed --gpus and any class was skipped, suggest compatible
    # alternatives so they don't have to dig through the template themselves.
    # Skipped when --gpus was auto-discovered (the discovery already picked
    # the best classes for this template).
    if args.gpus and any(r[1] == "no_offers" for r in results):
        suggestions = _suggest_compatible_gpus(
            client, num_gpus=args.num_gpus, extra_filters=extra_filters,
        )
        new_suggestions = [s for s in suggestions if s not in gpu_classes]
        if new_suggestions:
            print(f"\nGPU classes compatible with this template "
                  f"(num_gpus={args.num_gpus}): "
                  f"{', '.join(new_suggestions[:8])}", file=sys.stderr)

    # Build + print table. ``price`` is the actual dph_total from
    # show_instance(worker_id) of the rented instance — populated only when
    # status == "ok". Other statuses leave it None and the row shows "-".
    rows = []
    for gpu, status, perf, err, price in results:
        pps = (perf / price) if (perf and price) else None
        rows.append({
            "gpu_name": gpu,
            "rental_dph": price,
            "measured_perf": perf,
            "status": status,
            "perf_per_dollar": pps,
        })
    rows.sort(key=lambda r: (r["perf_per_dollar"] or -1), reverse=True)

    for gpu, status, _perf, err, _price in results:
        # no_offers already printed an inline message during pre-flight; don't
        # duplicate it here.
        if status not in ("ok", "no_offers") and err:
            print(f"  [{gpu}] {status}: {err}", file=sys.stderr)

    if args.raw:
        return rows

    template_display = (
        f"id:{args.template_id}" if args.template_id is not None
        else f"hash:{args.template_hash[:8]}"
    )
    print()
    print(f"Template: {template_display}  num_gpus={args.num_gpus}  "
          f"gpus={len(results)}")
    print()
    display_table(rows, [
        ("gpu_name",        "GPU",             "{}",      None, True),
        ("rental_dph",      "Rental $/hr",     "${:.3f}", None, False),
        ("measured_perf",   "Perf (measured)", "{:.1f}",  None, False),
        ("status",          "Status",          "{}",      None, True),
        ("perf_per_dollar", "Perf / $/hr",     "{:.1f}",  None, False),
    ], replace_spaces=False)
