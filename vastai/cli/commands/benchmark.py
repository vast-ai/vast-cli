"""vastai run benchmark: rent instances, measure perf/$, tear down.

Parallel execution. Each GPU class gets its own ephemeral endpoint
(``benchmark-<uuid8>``) and workergroup, all running concurrently in a
``ThreadPoolExecutor``. Per-class endpoints cap rentals at exactly one
GPU per class (cold_workers=1, max_workers=1) since ``max_workers`` is
endpoint-scoped and there's no per-workergroup cap; sharing an endpoint
would let the autoscaler over-allocate one class. Each thread tears
down its own resources in a ``finally`` block; an ``atexit`` hook is the
fallback if the process exits through ``sys.exit`` before the finally
runs.

Template is supplied by the caller via --template-id or --template-hash.
Note: not every template produces a usable perf score across GPU classes;
some saturate. TGI 1.0.3 (id 79663) has been verified not to saturate.
"""

import argparse
import atexit
import json
import math
import random
import re
import signal
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console
from rich.live import Live
from rich.table import Table

from vastai.cli.parser import argument
from vastai.cli.display import deindent, display_table
from vastai.cli.utils import get_parser as _get_parser, get_client

from vastai.api import endpoints as endpoints_api
from vastai.api import instances as instances_api
from vastai.api import offers as offers_api


parser = _get_parser()


# Default class list when --gpus is omitted. Five popular serverless GPUs
# spanning the price tiers: consumer (5090/4090/3090), workstation (A6000),
# and datacenter (H100 SXM). Each entry must also appear in
# _DEFAULT_GPU_RAM_MB so we can auto-size num_gpus from the template's
# gpu_total_ram filter without hitting the catalog. Caller's template
# extra_filters may still exclude individual classes (cuda version,
# compute_cap, inet, etc.) — those land in pre-flight as `skipped`.
_DEFAULT_GPUS = [
    "RTX 5090",
    "RTX 4090",
    "RTX 3090",
    "H100 SXM",
    "RTX A6000",
]

# Per-card VRAM (MB) for the default classes. Used by the auto-num_gpus path
# to compute the smallest count whose host-total satisfies a template's
# `gpu_total_ram` filter, e.g. a template requiring >48000 picks 2x for
# RTX 5090 (32 GB), 4x for RTX 4090 (24 GB), 1x for H100 SXM, etc. Values
# are the standard SKU per class verified against the live catalog
# (2026-04-30): RTX 4090 has rare 48 GB modded variants (~18% of US
# offers) but 80% are 24 GB; we size for the standard SKU and accept that
# customers who happen to land on a modded host will be over-provisioned.
#
# Do NOT add multi-VRAM-SKU classes here without switching to runtime
# catalog query (RTX 4060 Ti has 8/16 GB variants, A100 has 40/80 GB,
# both reported under the same gpu_name).
_DEFAULT_GPU_RAM_MB = {
    "RTX 5090":  32607,
    "RTX 4090":  24564,
    "RTX 3090":  24576,
    "H100 SXM":  81559,
    "RTX A6000": 49140,
}

# Per-class endpoint config:
# - cold_workers=1 drives min_to_create=1 in the autoscaler
#   (asm_ratio_manager.cpp:1055-1058) so it actually rents a worker.
# - max_workers=1 caps the rentals at exactly one. Without it, max_workers is
#   endpoint-scoped and a single endpoint hosting multiple workergroups would
#   let the autoscaler over-allocate to one class (e.g. 5x H200, 0x of others).
#   Per Lucas: per-workergroup max_workers doesn't exist, so per-class endpoint
#   is the only way to keep allocation balanced when running classes in parallel.
# - min_load=1.0 (NOT 0.0) tells the autoscaler "there is always at least 1
#   unit of demand on this endpoint." Without this, with load=0 and
#   min_load=0, the autoscaler computes "excess capacity" the moment a worker
#   reaches idle and stops it within ~1 second (verified live in autoscaler
#   logs). Our 10s poll then misses the idle window and we never capture
#   measured_perf. Per Lucas.
_ENDPOINT_CONFIG = {
    "cold_workers": 1,
    "max_workers": 1,
    "min_load": 1.0,
    "min_cold_load": 0.0,
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

# Seconds to wait between submitting each per-class thread. Prod's webserver
# rate-limits concurrent POSTs to /autojobs/ (returns 403/429 once a few
# threads burst), and the local autoscaler rate-limits /get_endpoint_workers/
# the same way. Spacing the submits out keeps every endpoint under its limit
# without serializing the actual benchmarks (each thread still runs to
# completion concurrently after its initial create_endpoint + create_wg).
_SUBMIT_STAGGER = 1.5


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


# Matches a "Nx GPU NAME" prefix on a --gpus token, with optional whitespace
# around the x. Only kicks in when the token starts with digits (so a normal
# name like "RTX_4090" doesn't accidentally match).
_GPU_COUNT_RE = re.compile(r"^(\d+)\s*x\s*(.+)$", re.IGNORECASE)


def _parse_gpu_spec(token, default_num_gpus):
    """Parse one --gpus token like ``RTX_4090`` or ``4x RTX_5090``.

    Returns ``(gpu_class, num_gpus)``. The ``Nx`` prefix wins; if absent,
    ``default_num_gpus`` (typically the value of ``--num-gpus``) is used.
    Underscores in the name are converted to spaces to match the rest of
    the codebase.
    """
    token = token.strip()
    m = _GPU_COUNT_RE.match(token)
    if m:
        return (m.group(2).strip().replace("_", " "), int(m.group(1)))
    return (token.replace("_", " "), default_num_gpus)


def _parse_gpus_arg(gpus_arg, default_num_gpus):
    """Split a ``--gpus`` value into a list of (gpu_class, num_gpus) tuples."""
    return [_parse_gpu_spec(t, default_num_gpus)
            for t in gpus_arg.split(",") if t.strip()]


def _fetch_template(client, *, template_id=None, template_hash=None):
    """Look up a template by id (preferred) or hash. Returns dict or None."""
    if template_id is not None:
        templates = _api_with_retry(offers_api.search_templates,
                                    client, query={"id": {"eq": template_id}})
    elif template_hash is not None:
        templates = _api_with_retry(
            offers_api.search_templates,
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
    offers = _api_with_retry(offers_api.search_offers,
                             client, query=query, limit=1)
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
        # Build a line per (key, op) where the GPU actually fails the
        # comparison. Operators where the GPU's value mathematically
        # satisfies the filter (but the search endpoint still returned 0
        # offers) are dropped silently; those are Vast search-engine quirks
        # we've seen on numeric comparisons like cuda_max_good>=12.4. Listing
        # them as "blockers" confuses users since the math contradicts the
        # claim.
        blocker_lines = []
        for key in blockers:
            ops = extra_filters.get(key)
            if not isinstance(ops, dict):
                blocker_lines.append(f"  {key}")
                continue
            actual = sample.get(key)
            for op, threshold in ops.items():
                if _filter_satisfied(actual, op, threshold) is True:
                    continue  # search-engine quirk, skip
                sym = _FILTER_OP_SYMBOL.get(op, op)
                if actual is None:
                    detail = "no sample available to check"
                else:
                    detail = f"{gpu_class} has {actual}"
                blocker_lines.append(f"  {key}{sym}{threshold}: {detail}")

        if blocker_lines:
            plural = "s" if len(blocker_lines) > 1 else ""
            lines = [f"blocked by template filter{plural}:"] + blocker_lines
            # Suggest a higher --num-gpus when gpu_total_ram is the ONLY
            # blocker. If there are other single-filter blockers (e.g.,
            # compute_cap on a too-new GPU), bumping num_gpus alone won't fix
            # the run, so we stay quiet rather than mislead.
            if blockers == ["gpu_total_ram"]:
                ops = extra_filters.get("gpu_total_ram") or {}
                if ops:
                    op, value = next(iter(ops.items()))
                    raw = _min_num_gpus_for_total_ram(
                        value, op, diag.get("per_card_gpu_ram"))
                    # Round our suggestion up to a count the marketplace
                    # actually has. Vast lists 1, 2, 4, 6, 8, 9, 10 commonly
                    # but rarely 3, 5, 7. Verifying via search_offers means
                    # we never suggest a count that pre-flight would skip.
                    if raw and raw > num_gpus:
                        viable = _suggest_viable_num_gpus(
                            client, gpu_class, raw, extra_filters)
                        if viable:
                            lines.append(
                                f"  hint: try {viable}x {gpu_class} "
                                f"(host total then satisfies {value})")
            return "\n".join(lines)
        # If every "blocker" turned out to be a search-engine quirk, fall
        # through to the combined-exclusion message below.

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
    offers = _api_with_retry(offers_api.search_offers,
                             client, query=query, limit=sample_limit)
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
    base_offers = _api_with_retry(offers_api.search_offers,
                                  client, query=base_query, limit=1)
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

    Note: Vast hosts list common chassis configurations (1, 2, 4, 6, 8, 9,
    10) but rarely 3, 5, or 7. If this returns 3 you should verify with
    a follow-up offer search before suggesting it to the user, otherwise
    the hint may point at a configuration the market doesn't have.
    """
    if not per_card_gpu_ram or not threshold:
        return None
    if op == "gt":
        return int(threshold // per_card_gpu_ram) + 1
    if op == "gte":
        return int(math.ceil(threshold / per_card_gpu_ram))
    return None


def _suggest_viable_num_gpus(client, gpu_class, raw_min, extra_filters,
                             max_search=12):
    """Return the smallest ``num_gpus >= raw_min`` that has at least one
    offer for ``gpu_class`` matching ``extra_filters``, or None if nothing
    up to ``max_search`` works. Used to round our num_gpus suggestion up
    to a configuration the marketplace actually rents.
    """
    if raw_min is None:
        return None
    for n in range(raw_min, max_search + 1):
        count = _count_matching_offers(
            client, gpu_class=gpu_class, num_gpus=n,
            extra_filters=extra_filters,
        )
        if count > 0:
            return n
    return None


def _auto_num_gpus_for_default(client, gpu_class, extra_filters):
    """Compute the per-class num_gpus for a default-list class based on the
    template's ``gpu_total_ram`` filter (if any) and the class's hardcoded
    per-card VRAM in ``_DEFAULT_GPU_RAM_MB``.

    Returns ``num_gpus`` (int >= 1). Falls back to 1 when:
    - The template has no ``gpu_total_ram`` filter (single card is enough).
    - The operator isn't a comparison we can solve (gt/gte).
    - One card already satisfies the threshold.

    Rounds up to a marketplace-viable count via ``_suggest_viable_num_gpus``
    so we never recommend e.g. ``3x RTX_4090`` when only 1/2/4-card hosts
    exist for that class.
    """
    per_card = _DEFAULT_GPU_RAM_MB.get(gpu_class)
    if per_card is None:
        return 1
    ops = (extra_filters or {}).get("gpu_total_ram") or {}
    if not ops:
        return 1
    op, threshold = next(iter(ops.items()))
    raw_min = _min_num_gpus_for_total_ram(threshold, op, per_card)
    if raw_min is None or raw_min <= 1:
        return 1
    viable = _suggest_viable_num_gpus(client, gpu_class, raw_min, extra_filters)
    return viable or raw_min


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

    Tracks each worker by id and only PRINTS on rotation events (a worker
    id disappears, meaning the autoscaler abandoned that host and is
    likely about to rent a different one). Per-state-transition lines and
    "still loading" heartbeats were dropped because the live rich Table
    already shows the current status, worker id, and elapsed time per
    class; printing every transition just duplicates table info.

    Mutates worker_states (still tracks state_started so the caller's
    terminal-debounce gate has timing info).
    """
    now = time.monotonic()

    if not current_workers:
        # Track the waiting window silently so other code paths can read
        # state_started, but don't print anything (the live table shows
        # status="waiting_for_worker" with a live elapsed counter).
        worker_states.setdefault(_WAITING_KEY,
                                 {"started": now, "last_heartbeat": now})
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
            worker_states[wid] = {
                "status": status,
                "state_started": now,
                "last_heartbeat": now,
            }
            continue
        if prev["status"] != status:
            prev["status"] = status
            prev["state_started"] = now
            prev["last_heartbeat"] = now

    for wid in list(worker_states):
        if not isinstance(wid, int):
            continue  # sentinel keys (e.g. _WAITING_KEY)
        if wid not in seen:
            # Worker abandoned by the autoscaler: print this because the
            # live table only shows the *current* worker, so a rotation
            # would otherwise be invisible.
            prev = worker_states[wid]
            elapsed = _format_elapsed(now - prev["state_started"])
            print(f"[{gpu_class}] worker {wid} abandoned "
                  f"(last state={prev['status']} for {elapsed})",
                  file=sys.stderr)
            del worker_states[wid]


# Statuses that mean "this class is finished and won't change anymore."
# Used by _render_class_table to freeze the elapsed column once a class
# is done (otherwise the displayed elapsed would keep climbing forever
# even though nothing is happening). Excludes ``error`` because the
# autoscaler recovers from error via rebooting -> model_loading; freezing
# elapsed at the first error would leave the table stale during recovery.
_TERMINAL_STATUSES = {"done", "skipped", "timeout", "failed", "no_worker"}


def _set_class_state(class_states, gpu_class, **fields):
    """Thread-safe (per-class) update of the live-table state dict.

    Each thread only writes to its own ``gpu_class`` key, and CPython makes
    individual dict assignments atomic, so no lock is needed.

    Tracks ``run_started`` (set on the first non-``queued`` status, used as
    the basis for the elapsed column) and ``run_ended`` (set when a terminal
    status is reached, so the elapsed in the table freezes instead of
    growing).
    """
    if class_states is None:
        return
    cur = class_states.setdefault(gpu_class, {})
    new_status = fields.get("status")
    now_ts = time.monotonic()
    if new_status and new_status != cur.get("status"):
        if "run_started" not in cur and new_status != "queued":
            cur["run_started"] = now_ts
        if new_status in _TERMINAL_STATUSES:
            cur["run_ended"] = now_ts
        else:
            # Coming back from a (mistakenly) frozen state; let elapsed
            # tick again. Without this, a worker that bounced through a
            # terminal status and recovered would show a frozen elapsed.
            cur.pop("run_ended", None)
    cur.update(fields)


def _render_class_table(class_states):
    """Render the per-class progress as a rich.Table for the live display."""
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
        # Hide skipped rows from the live table; they're noise during the
        # active run (the skip reason was printed at pre-flight, and the
        # final result table at the end still includes them for the record).
        if status == "skipped":
            continue
        run_started = s.get("run_started")
        run_ended = s.get("run_ended")
        # Skipped classes never really ran; queued ones haven't started.
        # Both deserve a blank elapsed so the column doesn't lie.
        # Terminal-but-meaningful statuses (done/failed/timeout/etc.) freeze
        # at the moment they finished. Active classes count up live.
        if status == "skipped" or run_started is None:
            elapsed_str = "-"
        elif run_ended is not None:
            elapsed_str = _format_elapsed(run_ended - run_started)
        else:
            elapsed_str = _format_elapsed(now - run_started)
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


def _instance_dph_total(client, instance_id):
    """Look up the actual ``dph_total`` for a rented instance.

    Returns the instance's billed price-per-hour (host base + storage; Vast's
    fee is already embedded in the host base). Falls back to None on lookup
    failure so a missing price doesn't kill the benchmark result.
    """
    try:
        inst = _api_with_retry(instances_api.show_instance,
                               client, id=instance_id)
        return inst.get("dph_total")
    except Exception:
        return None


def _api_with_retry(func, *args, max_retries=4, **kwargs):
    """Call ``func(*args, **kwargs)`` with retry on transient HTTP errors.

    Retries on:
      - 429 (Too Many Requests) — both prod webserver and local autoscaler
        rate-limit certain routes. The autoscaler's /get_endpoint_workers/
        threshold is ~1 call per 0.5s (rate_limiter.cpp:kDefaultThreshold);
        N parallel benchmark threads can bunch over that.
      - 503 (Service Unavailable) — transient backend issue.

    Does NOT retry on 403 because that usually means a real permission or
    credit problem (insufficient_credit, lacks api.X.write, etc.), and
    retrying just delays the eventual failure. If we ever start seeing
    rate-limit-induced 403s in practice we can revisit.

    Backoff: 0.6s, 1.2s, 2.4s, then give up. Adds 0.4s of jitter per attempt
    so multiple retrying threads don't synchronize.
    """
    delay = 0.6
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err = str(e)
            transient = ("429" in err) or ("503" in err)
            if attempt < max_retries - 1 and transient:
                time.sleep(delay + random.uniform(0, 0.4))
                delay *= 2
                continue
            raise


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


def _benchmark_one(client, *, gpu_class, num_gpus, timeout,
                   active_workergroups, active_endpoints,
                   template_hash=None, template_id=None,
                   auto_instance=None, autoscaler_url=None,
                   class_states=None):
    """Rent one instance for ``gpu_class``, poll for measured_perf, tear down.

    Each call creates and deletes its OWN endpoint and workergroup so it can
    safely run in parallel with other instances of itself. Lucas (autoscaler):
    ``max_workers`` is endpoint-scoped and there's no per-workergroup cap, so
    sharing an endpoint across classes lets the autoscaler over-allocate one
    class (e.g. 5x H200, 0x of others). One endpoint per class avoids that.

    Teardown runs in the ``finally`` regardless of exit path. The two
    ``active_*`` sets are the orchestrator's tracking for atexit cleanup;
    we add on create and remove on confirmed delete so the sweep catches
    anything we miss.

    Returns a 5-tuple ``(gpu_class, status, perf, err, dph_total)`` where
    ``dph_total`` is the rented instance's actual ``$/hr`` (None unless
    status == "ok" and the instance lookup succeeds).
    """
    endpoint_id = None
    wg_id = None
    endpoint_name = f"benchmark-{uuid.uuid4().hex[:8]}"
    start = time.monotonic()
    _set_class_state(class_states, gpu_class, status="provisioning")
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
        # Per-class endpoint with cold_workers=1 + max_workers=1 caps each
        # workergroup at exactly one rental. See _ENDPOINT_CONFIG comment.
        ep_kwargs = dict(_ENDPOINT_CONFIG, endpoint_name=endpoint_name)
        if auto_instance is not None:
            ep_kwargs["auto_instance"] = auto_instance
        ep_resp = _api_with_retry(endpoints_api.create_endpoint,
                                  client, **ep_kwargs)
        endpoint_id = _extract_id(ep_resp, "result", "endpoint_id", "id")
        if endpoint_id is None:
            return (gpu_class, "error", None,
                    f"create_endpoint returned no id: {ep_resp!r}", None)
        active_endpoints.add(endpoint_id)
        _set_class_state(class_states, gpu_class, endpoint_id=endpoint_id)

        wg_kwargs = dict(
            endpoint_id=endpoint_id,
            endpoint_name=endpoint_name,
            search_params=search,
            test_workers=1,
            # cold_workers=1 + min_load=1 here (not 0/0) so the autoscaler
            # keeps the worker alive after it reaches idle. Without min_load>0
            # the autoscaler's stop_score exceeds threshold the moment load
            # hits 0 (which is right after idle) and it stops the worker
            # within ~1 second (verified in autoscaler logs). cold_workers=1
            # alone protects against destroy but NOT stop; min_load=1 is what
            # actually keeps the stop decision from firing. Per Lucas.
            cold_workers=1,
            min_load=1.0,
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
        resp = _api_with_retry(endpoints_api.create_workergroup,
                               client, **wg_kwargs)
        wg_id = _extract_id(resp, "result", "autojob_id", "id")
        if wg_id is None:
            return (gpu_class, "error", None,
                    f"create_workergroup returned no id: {resp!r}", None)
        active_workergroups.add(wg_id)
        _set_class_state(class_states, gpu_class, status="waiting_for_worker")
        worker_states = {}

        while time.monotonic() - start < timeout:
            # Poll at endpoint level: get_workergroup_workers gates measured_perf
            # behind ready_ever_ which never flips for a benchmark-only worker.
            # The endpoint-level handler exposes measured_perf unconditionally.
            # Per-class endpoint means every worker in the response is ours;
            # no preexisting-id filter needed.
            workers = _normalize_workers(
                _api_with_retry(endpoints_api.get_endpoint_workers,
                                status_client, endpoint_id)
            )
            _emit_progress(worker_states, workers, gpu_class)
            # Mirror current worker state into class_states for the live table.
            # If no worker present we leave the prior state alone (might be
            # waiting_for_worker, or might be a brief gap during rotation).
            if workers:
                primary = workers[0]
                _set_class_state(
                    class_states, gpu_class,
                    status=str(primary.get("status") or "?").lower(),
                    worker_id=primary.get("id"),
                )
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
                _set_class_state(class_states, gpu_class, status="done",
                                 perf=ready[0]["measured_perf"], dph=dph)
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
            # We only reach this branch if `ready` above was empty (no
            # worker was status==idle AND measured_perf>0). So a real
            # measurement did NOT happen — no need to also check
            # measured_perf here. The autoscaler pre-fills measured_perf
            # with `dlperf` (a placeholder from offer specs) before
            # pyworker reports the real value, so checking for
            # measured_perf>0 alone misclassifies stuck workers as
            # "still in progress" and blocks the fail-fast.
            if terminal_workers_long:
                states = sorted({str(w.get("status", "")).lower()
                                 for w in workers})
                _set_class_state(class_states, gpu_class, status="failed")
                return (gpu_class, "failed", None,
                        f"all workers terminal ({', '.join(states)}) for "
                        f">{_TERMINAL_DEBOUNCE}s without reaching idle; "
                        f"autoscaler not rotating", None)
            # Fail fast if no worker has appeared after the no-worker window.
            # `worker_states` keys that are int are real worker ids (the
            # _WAITING_KEY sentinel is a string); if none ever materialized,
            # the autoscaler isn't going to find one in the remaining budget.
            if (not any(isinstance(k, int) for k in worker_states)
                    and time.monotonic() - start > _NO_WORKER_TIMEOUT):
                _set_class_state(class_states, gpu_class, status="no_worker")
                return (gpu_class, "no_worker", None,
                        f"autoscaler did not rent in {_NO_WORKER_TIMEOUT}s "
                        f"(scoring issue, all candidates failed silently, "
                        f"or template+GPU mismatch missed by pre-flight)", None)
            # Jitter the poll wait so N parallel threads don't all hit the
            # autoscaler's /get_endpoint_workers/ at the same instant every
            # 10s. Without jitter a 5-class run produces 5 simultaneous polls
            # per cycle and the autoscaler's rate limiter starts returning
            # 429s.
            time.sleep(_POLL_INTERVAL + random.uniform(0, 2.0))

        _set_class_state(class_states, gpu_class, status="timeout")
        return (gpu_class, "timeout", None,
                f"no measured_perf in {timeout}s", None)
    finally:
        # Tear down workergroup first (stops the autoscaler from spawning
        # new workers), then the endpoint (releases the cap, lets Vast GC
        # the rental). Both are best-effort; atexit sweeps any leftovers.
        if wg_id is not None:
            try:
                _api_with_retry(endpoints_api.delete_workergroup, client, id=wg_id)
                active_workergroups.discard(wg_id)
            except Exception as e:
                print(f"[cleanup] failed to delete workergroup {wg_id}: {e}",
                      file=sys.stderr)
        if endpoint_id is not None:
            try:
                _api_with_retry(endpoints_api.delete_endpoint, client, id=endpoint_id)
                active_endpoints.discard(endpoint_id)
            except Exception as e:
                print(f"[cleanup] failed to delete endpoint {endpoint_id}: {e}",
                      file=sys.stderr)


@parser.command(
    argument("--gpus", type=str,
             help="Comma-separated GPU names with optional Nx count prefix. "
                  "Same format as `vastai search offers`: encode spaces as "
                  "underscores, or quote the whole arg with real spaces. "
                  "Examples: --gpus RTX_4080,RTX_3060   "
                  "--gpus \"RTX 4080, 4x RTX 5090, 8x H100 SXM\". "
                  "Tokens without a Nx prefix use --num-gpus as their count. "
                  "If --gpus is omitted entirely, auto-discovers GPU classes "
                  "with the most offers matching this template's "
                  "extra_filters at --num-gpus."),
    argument("--num-gpus", type=int, default=None,
             help="Default number of GPUs per instance for tokens without an "
                  "Nx prefix. Also overrides the default-list auto-sizing "
                  "when --gpus is omitted. If not set, falls back to 1 "
                  "(or the per-class auto-size when --gpus is omitted and "
                  "the template has a gpu_total_ram filter)."),
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
    usage="vastai run benchmark (--template-id ID | --template-hash HASH) [OPTIONS]",
    help="Rent fresh instances, run pyworker benchmark, record measured perf/$",
    epilog=deindent("""
        Rents one instance per GPU class in parallel, measures perf, tears
        down. Each class gets its own ephemeral endpoint (``benchmark-<uuid8>``)
        and workergroup, capped at one rental each via cold_workers=1 +
        max_workers=1.

        REAL MONEY: each class rents a GPU for up to --timeout seconds, all
        running concurrently. Cleanup runs on Ctrl-C, exceptions, timeouts,
        and sys.exit.

        Examples:
            vastai run benchmark --template-id 79663
            vastai run benchmark --template-hash 3f19d605a70f4896e8a717dfe6b517a2
            vastai run benchmark --template-id 79663 --gpus RTX_4080,RTX_3060
            vastai run benchmark --template-id 79663 --timeout 600 -y
    """),
)
def run__benchmark(args):
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

    # Resolve gpu_specs (the (gpu_class, num_gpus) pairs we'll benchmark).
    # Three modes:
    #   - Explicit --gpus: parse the comma list, honoring inline Nx prefix
    #     per token; tokens without prefix fall back to --num-gpus or 1.
    #   - Default list, no --num-gpus: use _DEFAULT_GPUS and auto-size each
    #     class's count from the template's gpu_total_ram filter (e.g. a
    #     template requiring >48 GB picks 2x for RTX 5090, 4x for RTX 4090,
    #     1x for H100 SXM, etc.).
    #   - Default list, --num-gpus given: use _DEFAULT_GPUS, all at the
    #     specified count (user override).
    if args.gpus:
        gpu_specs = _parse_gpus_arg(args.gpus, args.num_gpus or 1)
    elif args.num_gpus is not None:
        gpu_specs = [(g, args.num_gpus) for g in _DEFAULT_GPUS]
    else:
        gpu_specs = [
            (g, _auto_num_gpus_for_default(client, g, extra_filters))
            for g in _DEFAULT_GPUS
        ]
    # gpu_classes used for downstream display & "did the user pass --gpus"
    # checks. The (gpu, n) pairs in gpu_specs are the source of truth for
    # what we actually rent.
    gpu_classes = [g for g, _ in gpu_specs]

    # Console used for live region + skip messages above it.
    console = Console(stderr=True)

    # Pre-flight all classes BEFORE the cost prompt so the disclosure shows
    # the actual count of GPUs that will be rented (not the optimistic count
    # of classes the user asked for). Skip messages with diagnoses print
    # here, and the alternatives-suggestion list also fires here when
    # --gpus was explicit.
    compatible_specs = []
    skipped_results = []
    for g, n in gpu_specs:
        offer_count = _count_matching_offers(
            client, gpu_class=g, num_gpus=n,
            extra_filters=extra_filters,
        )
        if offer_count == 0:
            msg = _skip_message_for_zero_offers(
                client, gpu_class=g, num_gpus=n,
                extra_filters=extra_filters,
            )
            console.print(f"[yellow][{g}] skipping:[/yellow] {msg}",
                          highlight=False)
            skipped_results.append((g, "skipped", None, msg, None))
        else:
            compatible_specs.append((g, n))

    # Suggest compatible alternatives if the user asked for specific classes
    # and any of them got filtered out. (Skipped when --gpus was auto-
    # discovered: discovery already picked the best classes for this
    # template, so any extras would be redundant noise.)
    if args.gpus and skipped_results:
        # The alternatives suggestion is for the explicit-gpus case only,
        # where args.num_gpus serves as the assumed count; default to 1.
        suggestion_n = args.num_gpus or 1
        suggestions = _suggest_compatible_gpus(
            client, num_gpus=suggestion_n, extra_filters=extra_filters,
        )
        new_suggestions = [s for s in suggestions if s not in gpu_classes]
        if new_suggestions:
            console.print(
                f"\nGPU classes compatible with this template "
                f"(num_gpus={suggestion_n}): "
                f"{', '.join(new_suggestions[:8])}", highlight=False)

    timeout_minutes = args.timeout / 60.0
    n = len(compatible_specs)
    if n == 0:
        # Everything got filtered out. Skip the prompt and the rental loop;
        # just print the result table with the skipped rows we collected.
        console.print(
            "\nNo compatible GPUs to benchmark for this template.",
            style="bold red")
        results = skipped_results
        return _print_results(args, results)

    # Disclose the per-class counts so the user sees what they're about to
    # rent. The leading count avoids the ambiguity of "Will rent 4x RTX
    # 4060 Ti, 4x RTX 4070S Ti..." reading as "four classes" instead of
    # "three configurations rented at 4 GPUs each."
    spec_strs = [f"{cnt}x {gpu}" for gpu, cnt in compatible_specs]
    spec_summary = ", ".join(spec_strs)
    if n == 1:
        print(f"Will rent 1 GPU configuration ({spec_summary}) for up to "
              f"{timeout_minutes:.0f} min.")
    else:
        print(f"Will rent {n} GPU configurations in parallel "
              f"({spec_summary}). Each runs for up to "
              f"{timeout_minutes:.0f} min.")
    if not args.yes:
        if input("Continue? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Aborted.", file=sys.stderr)
            return 130

    # Each class creates and destroys its own endpoint (per Lucas: only way
    # to cap rentals at one-per-class, since max_workers is endpoint-scoped).
    # These two sets back the atexit sweep for any leaks.
    active_workergroups = set()
    active_endpoints = set()

    def _cleanup():
        # Critical: this can run during Ctrl+C handling. We mask SIGINT for
        # the duration so a second Ctrl+C from an impatient user doesn't
        # interrupt mid-deletion and leave records leaked. We also catch
        # BaseException (not just Exception) on each delete because
        # KeyboardInterrupt is a BaseException and would otherwise bypass
        # `except Exception` and abort the loop. Each delete is independent;
        # one failure shouldn't abort the rest.
        prev_handler = None
        try:
            prev_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        except (ValueError, OSError):
            # Not in main thread, or signals unavailable; carry on.
            pass
        try:
            for wg_id in list(active_workergroups):
                try:
                    _api_with_retry(endpoints_api.delete_workergroup,
                                    client, id=wg_id)
                    active_workergroups.discard(wg_id)
                except BaseException:
                    pass
            for ep_id in list(active_endpoints):
                try:
                    _api_with_retry(endpoints_api.delete_endpoint,
                                    client, id=ep_id)
                    active_endpoints.discard(ep_id)
                except BaseException:
                    pass
        finally:
            if prev_handler is not None:
                try:
                    signal.signal(signal.SIGINT, prev_handler)
                except (ValueError, OSError):
                    pass
    atexit.register(_cleanup)

    # Live progress table state. Pre-populate with all classes (skipped ones
    # too, so the live table shows a complete picture).
    class_states = {}
    for g, _n in compatible_specs:
        _set_class_state(class_states, g, status="queued")
    for sr in skipped_results:
        _set_class_state(class_states, sr[0], status="skipped")

    def _run_one_class(g, n):
        try:
            return _benchmark_one(
                client,
                gpu_class=g,
                num_gpus=n,
                timeout=args.timeout,
                active_workergroups=active_workergroups,
                active_endpoints=active_endpoints,
                template_hash=args.template_hash,
                template_id=args.template_id,
                auto_instance=args.auto_instance,
                autoscaler_url=args.autoscaler_url,
                class_states=class_states,
            )
        except Exception as e:
            _set_class_state(class_states, g, status="error")
            return (g, "error", None, f"{type(e).__name__}: {e}", None)

    # Parallel: each compatible class runs its own endpoint+workergroup
    # concurrently. Per-class endpoints (with cold_workers=1, max_workers=1)
    # cap each at exactly one rental, so the autoscaler can't over-allocate.
    run_results = []
    executor = ThreadPoolExecutor(max_workers=len(compatible_specs))
    try:
        # Stagger submits by _SUBMIT_STAGGER seconds each. Without this, all N
        # threads fire create_endpoint+create_workergroup within milliseconds,
        # which trips prod's per-user rate limit on /autojobs/ (403/429) and
        # the local autoscaler's rate limit on /get_endpoint_workers/ (429).
        # The actual benchmarks still overlap heavily; only the cold-start
        # POSTs are spread out.
        future_map = {}
        for i, (g, n_for_class) in enumerate(compatible_specs):
            future_map[executor.submit(_run_one_class, g, n_for_class)] = g
            if i < len(compatible_specs) - 1:
                time.sleep(_SUBMIT_STAGGER)
        try:
            with Live(_render_class_table(class_states), console=console,
                      refresh_per_second=2, transient=False) as live:
                from concurrent.futures import wait, FIRST_COMPLETED
                pending = set(future_map)
                while pending:
                    done, pending = wait(pending, timeout=0.5,
                                         return_when=FIRST_COMPLETED)
                    for fut in done:
                        result = fut.result()
                        run_results.append(result)
                        # Surface failure reasons immediately so they scroll
                        # above the live table; the result-table section at
                        # the bottom doesn't repeat them.
                        g, status, _perf, err, _price = result
                        if status not in ("ok", "skipped") and err:
                            console.print(
                                f"[red][{g}] {status}:[/red] {err}",
                                highlight=False)
                    live.update(_render_class_table(class_states))
        except KeyboardInterrupt:
            # User aborted. Run cleanup IMMEDIATELY (don't wait for threads
            # via executor.shutdown(wait=True), which would block up to
            # --timeout). Deleting the workergroups makes the autoscaler
            # destroy the workers; the polling threads will then see zero
            # workers, exit their loops, and the executor will drain.
            # Without this, users hit Ctrl+C, stare at a stuck process for
            # 30 min, hit Ctrl+C again, kill the cleanup mid-flight, and
            # leak workergroups + endpoints.
            console.print("\n[yellow]Aborted, cleaning up...[/yellow]",
                          highlight=False)
            executor.shutdown(wait=False, cancel_futures=True)
            _cleanup()
            return 130
    finally:
        executor.shutdown(wait=True)
        _cleanup()

    results = skipped_results + run_results
    return _print_results(args, results)


def _print_results(args, results):
    """Print the final result table. Skip messages and suggestions are
    already printed during pre-flight, so this only prints per-class error
    details (for non-skipped failures) and the result rows themselves.
    """
    # Build + print table. ``price`` is the actual dph_total from
    # show_instance(worker_id) of the rented instance; populated only when
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

    # Note: failure messages are printed live as each future completes (above
    # the rich Live table) and skip messages are printed during pre-flight.
    # No need to repeat them here.

    if args.raw:
        return rows

    # The live rich table already shows everything; no need to re-render a
    # second static table here. Just print a one-line completion summary.
    n_ok = sum(1 for r in rows if r["status"] == "ok")
    n_total = len(rows)
    print(f"\nBenchmark complete: {n_ok}/{n_total} GPUs measured.")
