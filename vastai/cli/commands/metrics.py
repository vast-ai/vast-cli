"""CLI commands for platform-wide GPU market metrics (host/admin access)."""

import json
from datetime import datetime, timezone

from vastai.cli.parser import argument
from vastai.cli.display import display_table, deindent
from vastai.cli.utils import get_parser as _get_parser, get_client
from vastai.api import metrics as metrics_api


parser = _get_parser()


_VERIFIED_MAP = {"true": "yes", "false": "no", "all": "all"}
_HOSTING_MAP = {"true": "secure_cloud", "false": "community", "all": "all"}

_NEEDS_MACHINE_MSG = "No metrics available. This endpoint is for hosts with active machines."


_GPU_CURRENT_FIELDS = (
    ("gpu_name",          "GPU",      "{}",     None, True),
    ("total",             "Total",    "{}",     None, False),
    ("available",         "Avail",    "{}",     None, False),
    ("usage",             "Usage%",   "{:.1f}", None, False),
    ("rented_verified",   "Rnt/Ver",  "{}",     None, False),
    ("avail_verified",    "Avl/Ver",  "{}",     None, False),
    ("rented_unverified", "Rnt/Unv",  "{}",     None, False),
    ("avail_unverified",  "Avl/Unv",  "{}",     None, False),
    ("dlperf",            "DLPerf",   "{:.1f}", None, False),
    ("tflops",            "TFLOPS",   "{:.1f}", None, False),
    ("tflops_per_dollar", "TFLOPS/$", "{:.1f}", None, False),
    ("price_p10",         "P10 $/hr", "{:.4f}", None, False),
    ("price_median",      "Med $/hr", "{:.4f}", None, False),
    ("price_p90",         "P90 $/hr", "{:.4f}", None, False),
)


_GPU_TRENDS_FIELDS = (
    ("date",              "Date",     "{}",     None, True),
    ("rented_verified",   "Rnt/Ver",  "{}",     None, False),
    ("avail_verified",    "Avl/Ver",  "{}",     None, False),
    ("rented_unverified", "Rnt/Unv",  "{}",     None, False),
    ("avail_unverified",  "Avl/Unv",  "{}",     None, False),
    ("total",             "Total",    "{}",     None, False),
    ("rented_p10",        "R.p10",    "{:.4f}", None, False),
    ("rented_median",     "R.med",    "{:.4f}", None, False),
    ("rented_p90",        "R.p90",    "{:.4f}", None, False),
    ("avail_p10",         "A.p10",    "{:.4f}", None, False),
    ("avail_median",      "A.med",    "{:.4f}", None, False),
    ("avail_p90",         "A.p90",    "{:.4f}", None, False),
)


_GPU_LOCATION_FIELDS = (
    ("gpu_name",     "GPU",       "{}",     None, True),
    ("city",         "City",      "{}",     None, True),
    ("country_code", "CC",        "{}",     None, True),
    ("num_gpus",     "GPUs",      "{}",     None, False),
    ("rented",       "Rented",    "{}",     None, False),
    ("verified",     "Verified",  "{}",     None, False),
    ("latitude",     "Lat",       "{:.4f}", None, False),
    ("longitude",    "Lon",       "{:.4f}", None, False),
)


@parser.command(
    argument("--verified", type=str, choices=["true", "false", "all"], default="all",
             help="Filter GPUs by verification status"),
    argument("--datacenter", type=str, choices=["true", "false", "all"], default="all",
             help="Filter GPUs by datacenter hosting type"),
    usage="vastai metrics gpu [OPTIONS]",
    help="[Host] Get current GPU market metrics",
    epilog=deindent("""
        Get current GPU metrics with counts, usage, performance, and pricing.
        For historical metrics, see the `metrics gpu-trends` command.
        Requires host or admin access.

        Examples:
            vastai metrics gpu
            vastai metrics gpu --verified true --datacenter true
            vastai metrics gpu --raw
    """),
)
def metrics__gpu(args):
    """Get current GPU metrics."""
    client = get_client(args)
    resp = metrics_api.gpu_current(
        client,
        verified=_VERIFIED_MAP[args.verified],
        hosting_type=_HOSTING_MAP[args.datacenter],
    )
    if resp.get("needs_machine"):
        print(_NEEDS_MACHINE_MSG)
        return
    if args.raw:
        print(json.dumps(resp, indent=1))
        return
    display_table(resp.get("gpus", []), _GPU_CURRENT_FIELDS)


@parser.command(
    argument("name", type=str, nargs="?", default="RTX 5090,RTX 4090,RTX 3090",
             help="GPU name, comma-separated list, or 'all'. Underscores are accepted in place of spaces."),
    argument("--verified", type=str, choices=["true", "false", "all"], default="all",
             help="Filter by verified status"),
    argument("--datacenter", type=str, choices=["true", "false", "all"], default="all",
             help="Filter by datacenter hosting type"),
    argument("--start", type=int, default=None, help="Start unix timestamp"),
    argument("--end", type=int, default=None, help="End unix timestamp"),
    argument("--step", type=int, default=None,
             help="Time between data points in seconds (e.g. 3600 for hourly). Minimum 60s; step may be raised server-side to cap points returned."),
    argument("--full", action="store_true", default=False,
             help="Show all data points instead of sampling ~20"),
    usage="vastai metrics gpu-trends [NAME] [OPTIONS]",
    help="[Host] Get GPU market history",
    epilog=deindent("""
        Show GPU supply/demand and pricing trends over time. Defaults to RTX 5090, 4090, 3090
        for the last 24 hours. Requires host or admin access.

        Examples:
            vastai metrics gpu-trends
            vastai metrics gpu-trends "RTX 4090"
            vastai metrics gpu-trends "RTX 4090" --full
            vastai metrics gpu-trends "RTX 4090" --raw
            vastai metrics gpu-trends all --verified true --datacenter true
            vastai metrics gpu-trends "RTX 4090,H100_SXM" --start 1773298800 --end 1773817200 --step 3600
    """),
)
def metrics__gpu_trends(args):
    """Get GPU metrics history."""
    # Accept underscores as space aliases: "H100_SXM" -> "H100 SXM"
    args.name = args.name.replace("_", " ")
    client = get_client(args)
    resp = metrics_api.gpu_history(
        client,
        gpu_name=args.name,
        verified=_VERIFIED_MAP[args.verified],
        hosting_type=_HOSTING_MAP[args.datacenter],
        start=args.start,
        end=args.end,
        step=args.step,
    )
    if resp.get("needs_machine"):
        print(_NEEDS_MACHINE_MSG)
        return

    if "gpus" in resp:
        requested = [g.strip() for g in args.name.split(",")]
        gpu_items = [(name, resp["gpus"][name]) for name in requested if name in resp["gpus"]]
        seen = set(requested)
        for name, data in resp["gpus"].items():
            if name not in seen:
                gpu_items.append((name, data))
    else:
        gpu_items = [(args.name, resp)]

    sd_keys = ["rented_verified", "avail_verified", "rented_unverified", "avail_unverified", "total"]
    pr_keys = ["rented_p10", "rented_median", "rented_p90", "avail_p10", "avail_median", "avail_p90"]

    if args.raw:
        raw_out = {}
        for gpu_name, gpu_data in gpu_items:
            sd = gpu_data.get("supply_demand", {})
            pr = gpu_data.get("pricing", {})
            timestamps = sd.get("timestamps", [])
            rows = []
            for i, ts in enumerate(timestamps):
                row = {"date": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "timestamp": ts}
                for key in sd_keys:
                    arr = sd.get(key, [])
                    row[key] = arr[i] if i < len(arr) else None
                for key in pr_keys:
                    arr = pr.get(key, [])
                    row[key] = arr[i] if i < len(arr) else None
                rows.append(row)
            raw_out[gpu_name] = {"stats": gpu_data.get("stats", {}), "rows": rows}
        print(json.dumps(raw_out, indent=1))
        return

    for gpu_name, gpu_data in gpu_items:
        stats = gpu_data.get("stats", {})
        print(f"\n=== {gpu_name} ===")
        print(f"  tflops: {stats.get('tflops', '-')}  dlperf: {stats.get('dlperf', '-')}  tflops/$: {stats.get('tflops_per_dollar', '-')}")
        sd = gpu_data.get("supply_demand", {})
        pr = gpu_data.get("pricing", {})
        timestamps = sd.get("timestamps", [])
        if not timestamps:
            print("  (no data)")
            continue

        n = len(timestamps)
        sample_step = 1 if args.full else max(1, n // 20)
        rows = []
        for i in range(0, n, sample_step):
            row = {"date": datetime.fromtimestamp(timestamps[i], tz=timezone.utc).strftime("%Y-%m-%d %H:%M")}
            for key in sd_keys:
                arr = sd.get(key, [])
                row[key] = arr[i] if i < len(arr) else None
            for key in pr_keys:
                arr = pr.get(key, [])
                row[key] = arr[i] if i < len(arr) else None
            rows.append(row)

        display_table(rows, _GPU_TRENDS_FIELDS)
        if sample_step > 1:
            print(f"\n  ({n} data points, showing every {sample_step}th. Use --full for all.)")


@parser.command(
    argument("--verified", type=str, choices=["true", "false", "all"], default="all",
             help="Filter by verification status"),
    argument("--datacenter", type=str, choices=["true", "false", "all"], default="all",
             help="Filter by datacenter hosting type"),
    argument("--rented", type=str, choices=["true", "false", "all"], default="all",
             help="Filter by rented status"),
    argument("--gpu", type=str, default=None,
             help="Filter by GPU name (comma-separated list). Underscores are accepted in place of spaces."),
    usage="vastai metrics gpu-locations [OPTIONS]",
    help="[Host] Get GPU location metrics",
    epilog=deindent("""
        Show geographic locations of GPUs on the platform. Filtering is applied
        client-side — the endpoint returns one shared dataset and the CLI narrows
        the rows locally. Requires host or admin access.

        Examples:
            vastai metrics gpu-locations
            vastai metrics gpu-locations --verified true --datacenter true
            vastai metrics gpu-locations --gpu "RTX 4090,H100_SXM"
            vastai metrics gpu-locations --rented false --raw
    """),
)
def metrics__gpu_locations(args):
    """Get GPU location metrics."""
    client = get_client(args)
    resp = metrics_api.gpu_locations(client)
    if resp.get("needs_machine"):
        print(_NEEDS_MACHINE_MSG)
        return

    locations = resp.get("locations", [])

    for field in ("verified", "datacenter", "rented"):
        choice = getattr(args, field)
        if choice != "all":
            want = choice == "true"
            locations = [loc for loc in locations if bool(loc.get(field)) == want]
    if args.gpu:
        wanted_gpus = {g.strip().replace("_", " ") for g in args.gpu.split(",") if g.strip()}
        locations = [loc for loc in locations if loc.get("gpu_name") in wanted_gpus]

    if args.raw:
        print(json.dumps({"success": True, "locations": locations}, indent=1))
        return
    display_table(locations, _GPU_LOCATION_FIELDS)
