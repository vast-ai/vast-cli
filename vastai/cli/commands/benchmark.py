"""vastai run benchmark: benchmark a template against one or more GPUs.
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
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from rich.console import Console
from rich.live import Live
from rich.table import Table

from vastai.cli.parser import argument
from vastai.cli.display import deindent
from vastai.cli.utils import get_parser as _get_parser, get_client

from vastai.api import endpoints as endpoints_api
from vastai.api import instances as instances_api
from vastai.api import offers as offers_api


parser = _get_parser()


# Default GPUs (per-card VRAM in MB). Single-SKU only; VRAM variants under one gpu_name break the auto-sizer.
_DEFAULT_GPUS = {
    "RTX 5090":  32607,
    "RTX 4090":  24564,
    "RTX 3090":  24576,
    "H100 SXM":  81559,
    "RTX A6000": 49140,
}

_ENDPOINT_CONFIG = {"cold_workers": 1, "max_workers": 1, "min_load": 1.0}

_POLL_INTERVAL = 10.0
_DEFAULT_TIMEOUT = 30 * 60
_NO_WORKER_TIMEOUT = 120  # bail if autoscaler hasn't rented anything by here
_SUBMIT_STAGGER = 1.5  # spacing between parallel submits to avoid rate limits

_GPU_COUNT_RE = re.compile(r"^(\d+)\s*x\s*(.+)$", re.IGNORECASE)  # "Nx GPU NAME" prefix on a --gpus token

_FILTER_OP_SYMBOL = {
    "gt": ">", "gte": ">=", "lt": "<", "lte": "<=",
    "eq": "==", "neq": "!=", "in": "in", "notin": "notin",
}

# Workers stuck in these for >_TERMINAL_DEBOUNCE seconds trigger fail-fast.
# `error` excluded since the autoscaler recovers (error, rebooting, model_loading).
_TERMINAL_STATES = {"stopped", "destroying", "unavail"}
_TERMINAL_DEBOUNCE = 30

# Freezes the elapsed column in the live table; excludes `error` (autoscaler recovers).
_TERMINAL_STATUSES = {"done", "skipped", "timeout", "failed", "no_worker"}

_WAITING_KEY = "__waiting__"  # sentinel in worker_states; cannot collide with int worker ids


def _format_elapsed(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _parse_gpu_spec(token, default_num_gpus):
    """Parse one --gpus token like ``RTX_4090`` or ``4x RTX_5090``.

    Returns ``(gpu_name, num_gpus)``. The ``Nx`` prefix wins; if absent,
    ``default_num_gpus`` (typically the value of ``--num-gpus``) is used.
    Underscores in the name are converted to spaces to match the rest of
    the codebase.
    """
    token = token.strip()
    m = _GPU_COUNT_RE.match(token)
    if m:
        return (m.group(2).strip().replace("_", " "), int(m.group(1)))
    return (token.replace("_", " "), default_num_gpus)


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

    Returns an empty dict on missing/invalid input. Pre-flight just degrades
    to "GPU-name + num_gpus only" rather than failing loudly.
    """
    if not extra_filters_json:
        return {}
    try:
        return json.loads(extra_filters_json)
    except (ValueError, TypeError):
        return {}


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


def _count_matching_offers(client, *, gpu_name, num_gpus, extra_filters):
    """Return how many verified+rentable offers match the template's filters
    plus ``gpu_name`` and ``num_gpus``. ``limit=1`` because we only care
    whether any exist.
    """
    query = dict(extra_filters or {})
    query["gpu_name"] = {"eq": gpu_name}
    query["num_gpus"] = {"eq": num_gpus}
    offers = _api_with_retry(offers_api.search_offers,
                             client, query=query, limit=1)
    return len(offers)


def _skip_message_for_zero_offers(client, *, gpu_name, num_gpus, extra_filters):
    """Build a human-readable explanation for why a GPU has 0 matching offers.

    Skips the diagnostic API calls when there are no template filters (nothing
    to attribute the zero to). When there are filters, runs the diagnosis and
    surfaces the actual blocker (single filter, multi-filter, or no offers at
    all for the GPU).
    """
    if not extra_filters:
        return (f"no offers for {gpu_name} (num_gpus={num_gpus})")

    diag = _diagnose_offer_zero(
        client, gpu_name=gpu_name, num_gpus=num_gpus,
        extra_filters=extra_filters,
    )
    if diag["base_count"] == 0:
        return (f"no offers for {gpu_name} (num_gpus={num_gpus}), "
                f"independent of template filters")

    blockers = diag["single_blockers"]
    if blockers:
        sample = diag.get("sample_offer") or {}
        # Skip "blockers" the GPU actually satisfies (Vast search-engine quirk on numeric ops).
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
                    detail = f"{gpu_name} has {actual}"
                blocker_lines.append(f"  {key}{sym}{threshold}: {detail}")

        if blocker_lines:
            plural = "s" if len(blocker_lines) > 1 else ""
            lines = [f"blocked by template filter{plural}:"] + blocker_lines
            # Only hint num_gpus when gpu_total_ram is the sole blocker; otherwise bumping it won't fix the run.
            if blockers == ["gpu_total_ram"]:
                ops = extra_filters.get("gpu_total_ram") or {}
                if ops:
                    op, value = next(iter(ops.items()))
                    raw = _min_num_gpus_for_total_ram(
                        value, op, diag.get("per_card_gpu_ram"))
                    if raw and raw > num_gpus:
                        viable = _round_up_to_chassis(raw)
                        lines.append(
                            f"  hint: try {viable}x {gpu_name} "
                            f"(host total then satisfies {value})")
            return "\n".join(lines)
        # All "blockers" turned out to be quirks; fall through to combined-exclusion message.

    # No single filter is sufficient; combination of filters is the culprit.
    return ("0 offers match. No single filter is the culprit; the combination "
            f"of template filters excludes {gpu_name} "
            f"({_format_filter_query(extra_filters)})")


def _diagnose_offer_zero(client, *, gpu_name, num_gpus, extra_filters):
    """Identify why ``_count_matching_offers`` returned 0.

    Performs N+1 small offer searches (N = number of template filters) to find
    out:
      - whether the GPU has any offers at all (independent of template)
      - which individual filters alone exclude every offer for this GPU
      - the per-card ``gpu_ram`` for this GPU (read from the same base
        query, so callers can suggest a higher --num-gpus when
        ``gpu_total_ram`` is the blocker)

    Returns a dict {base_count, single_blockers, per_card_gpu_ram}.
    """
    base_query = {"gpu_name": {"eq": gpu_name},
                  "num_gpus": {"eq": num_gpus}}
    base_offers = _api_with_retry(offers_api.search_offers,
                                  client, query=base_query, limit=1)
    base = len(base_offers)
    sample = base_offers[0] if base_offers else None
    per_card = sample.get("gpu_ram") if sample else None
    blockers = []
    if base > 0:
        for key, op in (extra_filters or {}).items():
            single = _count_matching_offers(
                client, gpu_name=gpu_name, num_gpus=num_gpus,
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


def _round_up_to_chassis(n):
    """Round n up to the next common chassis size (1, 2, 4, 8). Returns n
    unchanged for >8 since that's rare enough we'd rather be honest than guess.
    """
    for c in (1, 2, 4, 8):
        if n <= c:
            return c
    return n


def _auto_num_gpus_for_default(gpu_name, extra_filters):
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
    raw_min = _min_num_gpus_for_total_ram(threshold, op, per_card)
    if raw_min is None or raw_min <= 1:
        return 1
    return _round_up_to_chassis(raw_min)


def _emit_progress(worker_states, current_workers, gpu_name):
    """Update worker_states with current poll, and print only on worker
    rotation (the live rich table already shows current status / elapsed).
    Tracks state_started per worker for the terminal-debounce gate.
    """
    now = time.monotonic()

    if not current_workers:
        worker_states.setdefault(_WAITING_KEY, {"started": now})
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
            elapsed = _format_elapsed(now - prev["state_started"])
            print(f"[{gpu_name}] worker {wid} abandoned "
                  f"(last state={prev['status']} for {elapsed})",
                  file=sys.stderr)
            del worker_states[wid]


def _set_class_state(class_states, gpu_name, **fields):
    """Update one GPU's row in the live-table state dict. Sets
    ``run_started`` on first non-``queued`` status and ``run_ended`` on
    terminal status (so elapsed freezes); each thread only writes its own
    key so no lock needed.
    """
    if class_states is None:
        return
    cur = class_states.setdefault(gpu_name, {})
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


def _render_class_table(class_states):
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
    """Look up the rented instance's actual ``$/hr``. None on lookup
    failure so a missing price doesn't kill the result.
    """
    try:
        inst = _api_with_retry(instances_api.show_instance,
                               client, id=instance_id)
        return inst.get("dph_total")
    except Exception:
        return None


def _api_with_retry(func, *args, max_retries=4, **kwargs):
    """Retry on 429 / 503 with jittered exponential backoff (0.6, 1.2, 2.4s).
    Other errors propagate immediately (403 usually means real auth/credit
    failure, not worth delaying with retries).
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
    """Optionally route status polls to a local autoscaler shard
    (``--autoscaler-url``) while keeping CRUD on prod.
    """
    if not autoscaler_url:
        return client
    from vastai.api.client import VastClient
    return VastClient(api_key=client.api_key, server_url=autoscaler_url)


def _benchmark_one(client, *, gpu_name, num_gpus, timeout,
                   active_workergroups, active_endpoints,
                   template_hash=None, template_id=None,
                   auto_instance=None, autoscaler_url=None,
                   class_states=None):
    """Rent one instance for ``gpu_name``, poll until idle + measured_perf,
    tear down. Each call owns its own endpoint + workergroup so it can run
    in parallel safely. Returns ``(gpu_name, status, perf, err, dph_total)``.
    """
    endpoint_id = None
    wg_id = None
    endpoint_name = f"benchmark-{uuid.uuid4().hex[:8]}"
    start = time.monotonic()
    _set_class_state(class_states, gpu_name, status="provisioning")
    search = f"gpu_name={gpu_name.replace(' ', '_')} num_gpus={num_gpus}"
    # status_client routes get_endpoint_workers through --autoscaler-url
    # for local-shard debugging, while CRUD stays on prod.
    status_client = _autoscaler_status_client(client, autoscaler_url)

    try:
        ep_kwargs = dict(_ENDPOINT_CONFIG, endpoint_name=endpoint_name)
        if auto_instance is not None:
            ep_kwargs["auto_instance"] = auto_instance
        ep_resp = _api_with_retry(endpoints_api.create_endpoint,
                                  client, **ep_kwargs)
        # Autoscaler returns the new id under either "result" or "id" depending on resource.
        endpoint_id = ep_resp.get("result", ep_resp.get("id")) if isinstance(ep_resp, dict) else None
        if not isinstance(endpoint_id, int):
            return (gpu_name, "error", None,
                    f"create_endpoint returned no id: {ep_resp!r}", None)
        active_endpoints.add(endpoint_id)
        _set_class_state(class_states, gpu_name, endpoint_id=endpoint_id)

        wg_kwargs = dict(
            endpoint_id=endpoint_id,
            endpoint_name=endpoint_name,
            search_params=search,
            test_workers=1,
            cold_workers=1,
            min_load=1.0,
        )
        # --template-id wins; --template-hash can silently resolve to a stale id (serverless-bugs.md #6).
        if template_id is not None:
            wg_kwargs["template_id"] = template_id
        elif template_hash is not None:
            wg_kwargs["template_hash"] = template_hash
        if auto_instance is not None:
            wg_kwargs["auto_instance"] = auto_instance
        resp = _api_with_retry(endpoints_api.create_workergroup,
                               client, **wg_kwargs)
        wg_id = resp.get("result", resp.get("id")) if isinstance(resp, dict) else None
        if not isinstance(wg_id, int):
            return (gpu_name, "error", None,
                    f"create_workergroup returned no id: {resp!r}", None)
        active_workergroups.add(wg_id)
        _set_class_state(class_states, gpu_name, status="waiting_for_worker")
        worker_states = {}

        while time.monotonic() - start < timeout:
            # Endpoint-level only: get_workergroup_workers gates measured_perf behind ready_ever_, which never flips for benchmark workers.
            resp = _api_with_retry(endpoints_api.get_endpoint_workers,
                                   status_client, endpoint_id)
            if isinstance(resp, list):
                workers = resp
            elif isinstance(resp, dict) and isinstance(resp.get("workers"), list):
                workers = resp["workers"]
            else:
                workers = []
            _emit_progress(worker_states, workers, gpu_name)
            if workers:
                primary = workers[0]
                _set_class_state(
                    class_states, gpu_name,
                    status=str(primary.get("status") or "?").lower(),
                    worker_id=primary.get("id"),
                )
            # measured_perf is only real once status==idle; before that it's a dlperf placeholder.
            ready = [w for w in workers
                     if str(w.get("status", "")).lower() == "idle"
                     and (w.get("measured_perf") or 0) > 0]
            if ready:
                # show_instance is the only place dph_total surfaces.
                worker_id = ready[0].get("id")
                dph = (_instance_dph_total(client, worker_id)
                       if worker_id else None)
                _set_class_state(class_states, gpu_name, status="done",
                                 perf=ready[0]["measured_perf"], dph=dph)
                return (gpu_name, "ok", ready[0]["measured_perf"], None, dph)
            # Fail fast: every worker stuck terminal past debounce, none reached idle.
            now_ts = time.monotonic()
            terminal_workers_long = workers and all(
                str(w.get("status", "")).lower() in _TERMINAL_STATES
                and isinstance(w.get("id"), int)
                and w["id"] in worker_states
                and now_ts - worker_states[w["id"]]["state_started"]
                    > _TERMINAL_DEBOUNCE
                for w in workers
            )
            if terminal_workers_long:
                states = sorted({str(w.get("status", "")).lower()
                                 for w in workers})
                _set_class_state(class_states, gpu_name, status="failed")
                return (gpu_name, "failed", None,
                        f"all workers terminal ({', '.join(states)}) for "
                        f">{_TERMINAL_DEBOUNCE}s without reaching idle; "
                        f"autoscaler not rotating", None)
            # Fail fast if no real worker (int id) has ever appeared.
            if (not any(isinstance(k, int) for k in worker_states)
                    and time.monotonic() - start > _NO_WORKER_TIMEOUT):
                _set_class_state(class_states, gpu_name, status="no_worker")
                return (gpu_name, "no_worker", None,
                        f"autoscaler did not rent in {_NO_WORKER_TIMEOUT}s "
                        f"(scoring issue, all candidates failed silently, "
                        f"or template+GPU mismatch missed by pre-flight)", None)
            # Jitter so N parallel threads don't all hit the autoscaler at the same instant.
            time.sleep(_POLL_INTERVAL + random.uniform(0, 2.0))

        _set_class_state(class_states, gpu_name, status="timeout")
        return (gpu_name, "timeout", None,
                f"no measured_perf in {timeout}s", None)
    finally:
        # Workergroup first (stops new workers), then endpoint. atexit sweeps anything we miss.
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
             help="comma-separated GPU names, same format as `vastai search offers` (e.g. RTX_4090,H100_SXM); optional Nx prefix per token (e.g. \"4x RTX_5090\")"),
    argument("--num-gpus", type=int, default=None,
             help="GPUs per instance for tokens without an Nx prefix (default 1)"),
    argument("--timeout", type=int, default=_DEFAULT_TIMEOUT,
             help=f"per-GPU safety ceiling in seconds (default {_DEFAULT_TIMEOUT})"),
    argument("--yes", "-y", action="store_true",
             help="skip cost-disclosure prompt"),
    argument("--template-hash", type=str, default=None,
             help="template hash to benchmark (one of --template-hash or --template-id required)"),
    argument("--template-id", type=int, default=None,
             help="template id to benchmark; wins over --template-hash if both are passed"),
    argument("--auto-instance", type=str, default=None, help=argparse.SUPPRESS),
    argument("--autoscaler-url", type=str, default=None, help=argparse.SUPPRESS),
    usage="vastai run benchmark (--template-id ID | --template-hash HASH) [OPTIONS]",
    help="Rent fresh instances per GPU, run the template's pyworker benchmark, record measured perf/$",
    epilog=deindent("""
        Rents one instance per GPU in parallel, measures perf, tears down.
        Each rental runs for up to --timeout seconds and costs real money.

        Example: vastai run benchmark --template-id 79663 --gpus RTX_4080,RTX_3060
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

    # Resolve gpu_specs: explicit --gpus parses inline Nx; otherwise auto-size from gpu_total_ram unless --num-gpus is given.
    if args.gpus:
        gpu_specs = [_parse_gpu_spec(t, args.num_gpus or 1)
                     for t in args.gpus.split(",") if t.strip()]
    elif args.num_gpus is not None:
        gpu_specs = [(g, args.num_gpus) for g in _DEFAULT_GPUS]
    else:
        gpu_specs = [
            (g, _auto_num_gpus_for_default(g, extra_filters))
            for g in _DEFAULT_GPUS
        ]

    console = Console(stderr=True)

    # Pre-flight before the prompt so the user sees skip reasons and accurate cost before approving.
    compatible_specs = []
    skipped_results = []
    for g, n in gpu_specs:
        offer_count = _count_matching_offers(
            client, gpu_name=g, num_gpus=n,
            extra_filters=extra_filters,
        )
        if offer_count == 0:
            msg = _skip_message_for_zero_offers(
                client, gpu_name=g, num_gpus=n,
                extra_filters=extra_filters,
            )
            console.print(f"[yellow][{g}] skipping:[/yellow] {msg}",
                          highlight=False)
            skipped_results.append((g, "skipped", None, msg, None))
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

    # Backing sets for the atexit sweep; per-GPU teardown discards on success.
    active_workergroups = set()
    active_endpoints = set()

    def _cleanup():
        # Mask SIGINT + catch BaseException so a second Ctrl+C can't leak records mid-iteration.
        prev_handler = None
        try:
            prev_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        except (ValueError, OSError):
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

    # Live-table state. Pre-populate every GPU so the table is complete.
    class_states = {}
    for g, _n in compatible_specs:
        _set_class_state(class_states, g, status="queued")
    for sr in skipped_results:
        _set_class_state(class_states, sr[0], status="skipped")

    def _run_one_class(g, n):
        try:
            return _benchmark_one(
                client,
                gpu_name=g,
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

    run_results = []
    executor = ThreadPoolExecutor(max_workers=len(compatible_specs))
    try:
        # Stagger submits to keep cold-start POSTs from tripping rate limits.
        futures = []
        for i, (g, n_for_class) in enumerate(compatible_specs):
            futures.append(executor.submit(_run_one_class, g, n_for_class))
            if i < len(compatible_specs) - 1:
                time.sleep(_SUBMIT_STAGGER)
        try:
            with Live(_render_class_table(class_states), console=console,
                      refresh_per_second=2, transient=False) as live:
                pending = set(futures)
                while pending:
                    done, pending = wait(pending, timeout=0.5,
                                         return_when=FIRST_COMPLETED)
                    for fut in done:
                        result = fut.result()
                        run_results.append(result)
                        # Surface failures live above the table.
                        g, status, _perf, err, _price = result
                        if status not in ("ok", "skipped") and err:
                            console.print(
                                f"[red][{g}] {status}:[/red] {err}",
                                highlight=False)
                    live.update(_render_class_table(class_states))
        except KeyboardInterrupt:
            # Cleanup synchronously; waiting on threads risks a leak if user hits Ctrl+C again.
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
    """Print the post-run summary. Failure / skip details have already
    scrolled above the live table; this just outputs the result rows
    (or raw JSON on --raw).
    """
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

    if args.raw:
        return rows

    n_ok = sum(1 for r in rows if r["status"] == "ok")
    print(f"\nBenchmark complete: {n_ok}/{len(rows)} GPUs measured.")
