"""CLI commands for the per-row price-increase contract extension flow.

Backend source of truth: ``vast/web/views/instance.py:257-312`` and
``vast/web/price_increase_pending.py``. All three endpoints are per-row
keyed on ``pending_price_increase_id``; the body is exactly
``{"pending_price_increase_id": int}`` with ``extra='forbid'``.

The CLI argument stays a positional **instance ID** to preserve UX
parity with ``show instances``; this module resolves it to the row
id with a single ``GET /pending-price-increases/`` per command
invocation, mirroring what the frontend modal does implicitly.

Stale signal is ``HTTP 404`` with body
``{"success": false, "error": "no_pending_price_increase"}`` (legacy
``HTTP 409`` is treated identically — the FE still recognises it).
"""

import sys
from datetime import datetime, timezone

from requests.exceptions import HTTPError

from vastai.api import price_increase as price_increase_api
from vastai.cli.display import (
    display_table,
    deindent,
    pending_price_increase_fields,
)
from vastai.cli.parser import argument
from vastai.cli.utils import get_parser as _get_parser, get_client

parser = _get_parser()


# Display rescale: backend writes per-second / fractional values; the human
# table renders the conventions the frontend uses on the in-app modal.
_SEC_PER_HOUR = 3600
_SEC_PER_MONTH = 3600 * 24 * 30


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _fmt_epoch(ts):
    """Render an epoch float as ``YYYY-MM-DD HH:MM UTC``; ``-`` if absent."""
    if ts is None:
        return "-"
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _fmt_delta(old, new, scale, precision):
    """Render ``old → new`` for a resource; ``-`` when the resource did not change.

    A ``null`` ``new`` means the backend did not change the resource on this
    row; the column collapses to ``-`` so the table does not invent a delta.
    """
    if new is None:
        return "-"
    old_part = f"{old * scale:.{precision}f}" if old is not None else "?"
    new_part = f"{new * scale:.{precision}f}"
    return f"{old_part} → {new_part}"


def _prepare_row(row):
    """Project a backend row into the table dict ``pending_price_increase_fields`` expects."""
    return {
        "pending_id": row.get("pending_price_increase_id"),
        "instance_id": row.get("contract_id"),
        "host_id": row.get("host_id"),
        "current_end": _fmt_epoch(row.get("contract_end_date")),
        "new_end": _fmt_epoch(row.get("ask_end_date")),
        "gpu": _fmt_delta(
            row.get("old_gpu_costpersec"), row.get("new_gpu_costpersec"),
            _SEC_PER_HOUR, 4,
        ),
        "storage": _fmt_delta(
            row.get("old_disk_ram_costpersec"), row.get("new_disk_ram_costpersec"),
            _SEC_PER_MONTH, 4,
        ),
        "bw_up": _fmt_delta(
            row.get("old_bwu_cost"), row.get("new_bwu_cost"), 1, 4,
        ),
        "bw_down": _fmt_delta(
            row.get("old_bwd_cost"), row.get("new_bwd_cost"), 1, 4,
        ),
        "fee": _fmt_delta(
            row.get("old_platform_fee"), row.get("new_platform_fee"), 100, 2,
        ),
    }


# ---------------------------------------------------------------------------
# Stale-row detection
# ---------------------------------------------------------------------------


def _is_stale_error(err):
    """Detect the backend's stale-row signal across the documented variants.

    Modern backend: ``HTTP 404`` with body
    ``{"error": "no_pending_price_increase"}``.
    Legacy: ``HTTP 409`` (the frontend still recognises it, so do we).
    """
    response = getattr(err, "response", None)
    if response is None:
        return False
    status = getattr(response, "status_code", None)
    if status == 409:
        return True
    if status != 404:
        return False
    try:
        body = response.json() or {}
    except Exception:
        return False
    return body.get("error") == price_increase_api.NO_PENDING_PRICE_INCREASE


# ---------------------------------------------------------------------------
# show pending-price-increases
# ---------------------------------------------------------------------------


@parser.command(
    argument("-q", "--quiet", action="store_true",
             help="print only pending_price_increase_id values, one per line"),
    usage="vastai show pending-price-increases [OPTIONS]",
    help="List pending price-increase challenges for the authenticated user",
    epilog=deindent("""
        Lists every pending price-increase challenge the backend has open for
        you. Each row shows the per-resource old → new prices and the cutover
        boundary: the new rate applies only after each contract's current
        end_date — your remaining time on the current term is billed at the
        original price.

        Pipe the pending IDs to `vastai accept price-increase` or
        `vastai reject price-increase` (use --quiet for one ID per line):

            vastai show pending-price-increases --quiet
    """),
)
def show__pending_price_increases(args):
    """List pending price-increase challenges in a human or raw form."""
    if args.explain:
        print("GET /instances/pending-price-increases/")
    client = get_client(args)
    envelope = price_increase_api.list_pending(client)
    if args.raw:
        return envelope
    rows = envelope.get("pending_price_increases", []) or []
    if args.quiet:
        for row in rows:
            print(row.get("pending_price_increase_id"))
        return
    if not rows:
        print("No pending price increases.")
        return
    display_table([_prepare_row(r) for r in rows], pending_price_increase_fields)
    if envelope.get("truncated"):
        print("\nResult truncated by the server; refine with `vastai show "
              "pending-price-increases --raw` to retrieve the full payload.")


# ---------------------------------------------------------------------------
# Shared accept/reject confirmation + fan-out
# ---------------------------------------------------------------------------


def _resolve_instance_ids_to_pending(rows, instance_ids):
    """Return ``[(instance_id, pending_id_or_None)]`` preserving CLI argument order."""
    by_contract = {r.get("contract_id"): r for r in rows}
    return [
        (iid, (by_contract.get(iid) or {}).get("pending_price_increase_id"))
        for iid in instance_ids
    ]


def _prompt_or_exit(present_imperative, instance_ids, rows, *, yes):
    """Confirm before mutating; honours the spec's TTY + --yes rules.

    Returns ``True`` to proceed, ``False`` to abort cleanly with exit 0.
    Non-TTY without ``--yes`` exits 1 with a clear message (matches the
    Two-Step Confirmation requirement).
    """
    if yes:
        return True
    if not sys.stdin.isatty():
        print(
            '--yes is required when stdin is not a TTY. Run "vastai show '
            'pending-price-increases" to review first.',
            file=sys.stderr,
        )
        sys.exit(1)
    matching = [r for r in rows if r.get("contract_id") in set(instance_ids)]
    if matching:
        display_table(
            [_prepare_row(r) for r in matching], pending_price_increase_fields,
        )
    answer = input(
        f"{present_imperative} these price increases? [y/N]: "
    ).strip().lower()
    return answer == "y"


def _run_per_row(args, *, route_verb, api_call, present_imperative, past_tense, cutover_note):
    """Shared accept/reject driver: resolve, confirm, fan-out, summarise."""
    instance_ids = [int(x) for x in args.ids]
    if args.explain:
        for iid in instance_ids:
            print(f"PUT /instances/{route_verb}-price-increase/  body for instance {iid}")
    client = get_client(args)
    envelope = price_increase_api.list_pending(client)
    rows = envelope.get("pending_price_increases", []) or []
    if not _prompt_or_exit(present_imperative, instance_ids, rows, yes=args.yes):
        print("Aborted.")
        return

    pairs = _resolve_instance_ids_to_pending(rows, instance_ids)
    accepted_ids, stale, failed = [], 0, 0
    for iid, pid in pairs:
        if pid is None:
            print(f"pending price increase no longer available for instance {iid}")
            stale += 1
            continue
        try:
            result = api_call(client, pid)
        except HTTPError as err:
            if _is_stale_error(err):
                print(
                    "pending price increase no longer available — re-run "
                    "vastai show pending-price-increases"
                )
                stale += 1
                continue
            print(f"failed for instance {iid}: {err}", file=sys.stderr)
            failed += 1
            continue
        print(
            f"{past_tense} pending_id={result.get('pending_price_increase_id')} "
            f"contract_id={result.get('contract_id')}"
        )
        accepted_ids.append(result.get("contract_id"))

    total = len(instance_ids)
    n_ok = len(accepted_ids)
    print(
        f"\n{past_tense} {n_ok} / Stale {stale} / Failed {failed} "
        f"of {total} requested."
    )
    if n_ok:
        ids_str = ", ".join(str(cid) for cid in accepted_ids)
        print(f"{past_tense} price increase for {n_ok} instance(s): {ids_str}")
        if cutover_note:
            print(cutover_note)

    # Spec: non-stale failures take precedence over stale (so a script can
    # distinguish "all stale" from "mixed failures").
    if failed:
        sys.exit(1)
    if stale:
        sys.exit(2)


# ---------------------------------------------------------------------------
# accept price-increase
# ---------------------------------------------------------------------------


@parser.command(
    argument("ids", help="instance IDs to accept (one or more).", type=int, nargs="+"),
    argument("--yes", "-y", action="store_true",
             help="skip the interactive prompt; required when stdin is not a TTY"),
    usage="vastai accept price-increase ID [ID ...] [--yes]",
    help="Accept one or more pending host price increases",
    epilog=deindent("""
        Review pending price increases with `vastai show pending-price-increases`
        before accepting. The CLI fans out one PUT per instance ID (no batch
        endpoint exists on the backend), and the new rate applies only after
        each contract's current end_date — your remaining time on the current
        term is billed at the original price.

        Examples:
            vastai accept price-increase 123 --yes
            vastai accept price-increase 1 2 3 --yes

        Exit codes:
            0 — every requested row was accepted
            1 — at least one row failed (non-stale)
            2 — at least one row was stale (re-run `show pending-price-increases`)
    """),
)
def accept__price_increase(args):
    """Per-row accept for pending price-increase challenges."""
    _run_per_row(
        args,
        route_verb="accept",
        api_call=price_increase_api.accept,
        present_imperative="Accept",
        past_tense="Accepted",
        cutover_note="New rate applies after each contract's current end_date.",
    )


# ---------------------------------------------------------------------------
# reject price-increase
# ---------------------------------------------------------------------------


@parser.command(
    argument("ids", help="instance IDs to reject (one or more).", type=int, nargs="+"),
    argument("--yes", "-y", action="store_true",
             help="skip the interactive prompt; required when stdin is not a TTY"),
    usage="vastai reject price-increase ID [ID ...] [--yes]",
    help="Reject one or more pending host price increases",
    epilog=deindent("""
        Tombstones the matching pending rows on the backend (no cutover follows).
        Use `vastai show pending-price-increases` to review the rows first; the
        CLI fans out one PUT per instance ID.

        Exit codes mirror `accept price-increase`:
            0 — every requested row was rejected
            1 — at least one row failed (non-stale)
            2 — at least one row was stale
    """),
)
def reject__price_increase(args):
    """Per-row reject for pending price-increase challenges."""
    _run_per_row(
        args,
        route_verb="reject",
        api_call=price_increase_api.reject,
        present_imperative="Reject",
        past_tense="Rejected",
        cutover_note=None,
    )
