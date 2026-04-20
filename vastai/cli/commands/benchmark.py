"""CLI command: benchmark GPU classes for performance / cost."""

import json
from statistics import median

from vastai.cli.parser import argument
from vastai.cli.display import deindent
from vastai.cli.utils import get_parser as _get_parser, get_client
from vastai.api import offers as offers_api


parser = _get_parser()


DEFAULT_GPUS = [
    "RTX 3090",
    "RTX 4090",
    "RTX 5090",
    "RTX A4000",
    "RTX A5000",
    "H100 SXM",
    "H100 NVL",
    "H200",
]


def _canonicalize_gpu(name, known_names):
    """Map a user-supplied GPU token to the canonical API name.

    Accepts: `RTX_3090`, `RTX 3090`, `3090`, `h100_sxm`, `H200`. Returns None if unresolved.
    """
    raw = name.strip().replace("_", " ")
    lookup = {k.lower(): k for k in known_names}
    if raw.lower() in lookup:
        return lookup[raw.lower()]
    prefixed = f"rtx {raw.lower()}"
    if prefixed in lookup:
        return lookup[prefixed]
    return None


def _load_known_gpu_names():
    from vastai.data import query as dq
    return sorted({
        v for k, v in vars(dq).items()
        if isinstance(v, str) and not k.startswith("_") and k[0].isalpha() and k[0].isupper()
    })


def _aggregate(offers, requested_gpus):
    buckets = {g: [] for g in requested_gpus}
    for o in offers:
        g = o.get("gpu_name")
        if g in buckets:
            buckets[g].append(o)

    rows = []
    for g in requested_gpus:
        rs = buckets[g]
        if not rs:
            rows.append({"gpu": g, "n": 0})
            continue
        dph = [o["dph_total"] for o in rs if o.get("dph_total") is not None]
        stor = [o["storage_cost"] for o in rs if o.get("storage_cost") is not None]
        dlp = [o["dlperf"] for o in rs if o.get("dlperf") is not None]
        med_dph = median(dph) if dph else None
        med_stor = median(stor) if stor else None
        med_dlp = median(dlp) if dlp else None
        perf_per_cost = (med_dlp / med_dph) if (med_dlp and med_dph) else None
        rows.append({
            "gpu": g,
            "n": len(rs),
            "median_dph": med_dph,
            "median_storage_cost_per_gb_month": med_stor,
            "median_dlperf": med_dlp,
            "dlperf_per_dollar": perf_per_cost,
        })
    return rows


def _format_table(rows, min_samples):
    headers = ["GPU", "N", "Med $/hr", "Med $/GB/mo", "DLPerf", "DLPerf/$"]
    body = []
    thin = False
    for r in rows:
        if r["n"] == 0:
            body.append([r["gpu"], "0", "no offers", "", "", ""])
            continue
        mark = "*" if r["n"] < min_samples else " "
        body.append([
            r["gpu"] + mark,
            str(r["n"]),
            f"{r['median_dph']:.4f}" if r["median_dph"] is not None else "",
            f"{r['median_storage_cost_per_gb_month']:.4f}" if r["median_storage_cost_per_gb_month"] is not None else "",
            f"{r['median_dlperf']:.2f}" if r["median_dlperf"] is not None else "",
            f"{r['dlperf_per_dollar']:.1f}" if r["dlperf_per_dollar"] is not None else "",
        ])
        if r["n"] < min_samples:
            thin = True

    widths = [max(len(h), *(len(row[i]) for row in body)) for i, h in enumerate(headers)]
    sep = "  "
    lines = [sep.join(h.ljust(w) for h, w in zip(headers, widths))]
    lines.append(sep.join("-" * w for w in widths))
    for row in body:
        lines.append(sep.join(cell.ljust(w) for cell, w in zip(row, widths)))

    footer = [
        "",
        "DLPerf: Vast's generic DL-throughput benchmark (higher is better).",
        "DLPerf/$: DLPerf divided by median $/hr — higher means better perf/cost.",
        "Storage price is $/GB/month on the host.",
    ]
    if thin:
        footer.append(f"* sample size below --min-samples ({min_samples}); medians may be noisy.")
    return "\n".join(lines + footer)


@parser.command(
    argument("--gpus", type=str, default=None,
             help=f"Comma-separated GPU names. default: {','.join(DEFAULT_GPUS)}"),
    argument("--num-gpus", type=int, default=1,
             help="Bucket to benchmark (e.g. 1, 2, 4, 8). default: 1"),
    argument("--min-samples", type=int, default=3,
             help="Minimum offers per GPU before reporting without a warning. default: 3"),
    argument("--json", dest="emit_json", action="store_true",
             help="Emit JSON instead of a text table."),
    usage="vastai benchmark [--gpus 3090,4090,...] [--num-gpus N] [--json]",
    help="Compare GPU perf/cost using live marketplace data",
    epilog=deindent("""
        Fetches current on-demand offers and reports median price and median DLPerf
        score per GPU class, plus a perf/cost ratio. Uses the Vast marketplace
        as the data source — no instances are created and no cost is incurred.

        GPU names may be passed with or without the "RTX" prefix and with spaces
        or underscores (e.g. "3090", "RTX_3090", "RTX 3090" are all equivalent).
        Ambiguous tokens like "A100" or "H100" require the variant suffix
        ("A100_SXM", "H100_NVL", etc.).

        Examples:

            # default GPU set, single-GPU bucket
            vastai benchmark

            # custom set
            vastai benchmark --gpus 4090,5090,H100_SXM

            # compare 8-GPU bundles
            vastai benchmark --num-gpus 8 --gpus H100_SXM,H200

            # machine-readable output
            vastai benchmark --json
    """),
)
def benchmark(args):
    """Compare GPU classes by median price and median DLPerf."""
    known = _load_known_gpu_names()

    if args.gpus:
        raw_list = [t for t in args.gpus.split(",") if t.strip()]
    else:
        raw_list = DEFAULT_GPUS

    requested = []
    unresolved = []
    for token in raw_list:
        canonical = _canonicalize_gpu(token, known)
        if canonical is None:
            unresolved.append(token)
        elif canonical not in requested:
            requested.append(canonical)

    if unresolved:
        print(f"Error: unrecognized GPU name(s): {', '.join(unresolved)}")
        print("Hint: use the variant suffix for ambiguous families (e.g. H100_SXM, A100_PCIE).")
        return 1
    if not requested:
        print("Error: no GPU names to benchmark.")
        return 1

    query = {
        "num_gpus": {"eq": args.num_gpus},
        "gpu_name": {"in": requested},
    }
    client = get_client(args)
    try:
        offers = offers_api.search_offers(client, query=query, limit=10000)
    except Exception as e:
        print(f"Error fetching offers: {e}")
        return 1

    rows = _aggregate(offers, requested)

    if args.emit_json:
        print(json.dumps(rows, indent=2))
    else:
        print(_format_table(rows, args.min_samples))
    return 0
