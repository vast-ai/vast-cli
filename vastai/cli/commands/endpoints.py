"""CLI commands for managing endpoints and workergroups."""

import json
import argparse

from vastai.cli.parser import argument
from vastai.cli.display import deindent
from vastai.api import endpoints as endpoints_api


from vastai.cli.utils import get_parser as _get_parser, get_client  # noqa: F401


parser = _get_parser()


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------

@parser.command(
    argument("--min_load", help="minimum floor load in perf units/s", type=float, default=0.0),
    argument("--min_cold_load", help="minimum floor load handled with cold workers", type=float, default=0.0),
    argument("--target_util", help="target capacity utilization (fraction, max 1.0, default 0.9)", type=float, default=0.9),
    argument("--cold_mult", help="cold/stopped instance capacity target as multiple of hot capacity target", type=float, default=2.5),
    argument("--cold_workers", help="min number of workers to keep 'cold' (default 5)", type=int, default=5),
    argument("--max_workers", help="max number of workers (default 20)", type=int, default=20),
    argument("--endpoint_name", help="deployment endpoint name", type=str),
    argument("--max_queue_time", help="maximum seconds requests may be queued on each worker (default 30.0)", type=float),
    argument("--target_queue_time", help="target seconds for the queue to be cleared (default 10.0)", type=float),
    argument("--auto_instance", help=argparse.SUPPRESS, type=str, default="prod"),
    usage="vastai create endpoint [OPTIONS]",
    help="Create a new endpoint group",
)
def create__endpoint(args):
    """Create a new endpoint group."""
    if args.explain:
        print("request json: ")
        print({
            "client_id": "me", "min_load": args.min_load, "min_cold_load": args.min_cold_load,
            "target_util": args.target_util, "cold_mult": args.cold_mult,
            "cold_workers": args.cold_workers, "max_workers": args.max_workers,
            "endpoint_name": args.endpoint_name, "autoscaler_instance": args.auto_instance,
        })

    client = get_client(args)
    try:
        result = endpoints_api.create_endpoint(
            client, min_load=args.min_load, min_cold_load=args.min_cold_load,
            target_util=args.target_util, cold_mult=args.cold_mult,
            cold_workers=args.cold_workers, max_workers=args.max_workers,
            endpoint_name=args.endpoint_name, auto_instance=args.auto_instance,
            max_queue_time=args.max_queue_time, target_queue_time=args.target_queue_time,
        )
        print("create endpoint {}".format(result))
    except Exception:
        print("The response is not valid JSON or an error occurred.")


@parser.command(
    usage="vastai show endpoints [--api-key API_KEY]",
    help="Display user's current endpoint groups",
)
def show__endpoints(args):
    """Display user's current endpoint groups."""
    if args.explain:
        print("request json: ")
        print({"client_id": "me", "api_key": args.api_key})

    client = get_client(args)
    result = endpoints_api.show_endpoints(client)

    if isinstance(result, dict) and "error" in result:
        print(result["error"])
        return

    if args.raw:
        return result
    else:
        print(json.dumps(result, indent=1, sort_keys=True))


@parser.command(
    argument("id", help="id of endpoint group to update", type=int),
    argument("--min_load", help="minimum floor load in perf units/s", type=float),
    argument("--min_cold_load", help="minimum floor load handled with cold workers", type=float),
    argument("--endpoint_state", help="active, suspended, or stopped", type=str),
    argument("--auto_instance", help=argparse.SUPPRESS, type=str, default="prod"),
    argument("--target_util", help="target capacity utilization (fraction, max 1.0, default 0.9)", type=float),
    argument("--cold_mult", help="cold/stopped instance capacity target as multiple of hot capacity target", type=float),
    argument("--cold_workers", help="min number of workers to keep 'cold' (default 5)", type=int),
    argument("--max_workers", help="max number of workers (default 20)", type=int),
    argument("--endpoint_name", help="deployment endpoint name", type=str),
    argument("--max_queue_time", help="maximum seconds requests may be queued on each worker (default 30.0)", type=float),
    argument("--target_queue_time", help="target seconds for the queue to be cleared (default 10.0)", type=float),
    usage="vastai update endpoint ID [OPTIONS]",
    help="Update an existing endpoint group",
)
def update__endpoint(args):
    """Update an existing endpoint group."""
    client = get_client(args)
    result = endpoints_api.update_endpoint(
        client, id=args.id,
        min_load=args.min_load, min_cold_load=args.min_cold_load,
        target_util=args.target_util, cold_mult=args.cold_mult,
        cold_workers=args.cold_workers, max_workers=args.max_workers,
        endpoint_name=args.endpoint_name, endpoint_state=args.endpoint_state,
        auto_instance=args.auto_instance,
        max_queue_time=args.max_queue_time, target_queue_time=args.target_queue_time,
    )
    if args.raw:
        return result
    print("update endpoint {}".format(result))


@parser.command(
    argument("id", help="id of endpoint group to delete", type=int),
    usage="vastai delete endpoint ID",
    help="Delete an endpoint group",
)
def delete__endpoint(args):
    """Delete an endpoint group."""
    id = args.id
    if args.explain:
        print("request json: ")
        print({"client_id": "me", "endptjob_id": args.id})

    client = get_client(args)
    result = endpoints_api.delete_endpoint(client, id=id)
    print("delete endpoint {}".format(result))


@parser.command(
    argument("id", help="id of endpoint group to fetch logs from", type=int),
    argument("--level", help="log detail level (0 to 3)", type=int, default=1),
    argument("--tail", help="", type=int, default=None),
    usage="vastai get endpt-logs ID [--api-key API_KEY]",
    help="Fetch logs for a specific serverless endpoint group",
)
def get__endpt_logs(args):
    """Fetch logs for a specific serverless endpoint group."""
    if args.explain:
        print(f"Fetching endpoint logs for id={args.id}")

    client = get_client(args)
    rj = endpoints_api.get_endpt_logs(client, id=args.id, level=args.level, tail=args.tail)

    levels = {0: "info0", 1: "info1", 2: "trace", 3: "debug"}

    if isinstance(rj, dict) and "error" in rj:
        print(rj["error"])
        return

    if args.raw:
        return rj
    else:
        dbg_lvl = levels[args.level]
        if rj and dbg_lvl:
            print(rj[dbg_lvl])


# ---------------------------------------------------------------------------
# workergroups
# ---------------------------------------------------------------------------

@parser.command(
    argument("--template_hash", help="template hash", type=str),
    argument("--template_id", help="template id (optional)", type=int),
    argument("-n", "--no-default", action="store_true", help="Disable default search param query args"),
    argument("--launch_args", help="launch args string for create instance", type=str),
    argument("--endpoint_name", help="deployment endpoint name", type=str),
    argument("--endpoint_id", help="deployment endpoint id", type=int),
    argument("--test_workers", help="number of workers to create for testing (default 3)", type=int, default=3),
    argument("--gpu_ram", help="estimated GPU RAM req", type=float),
    argument("--search_params", help="search param string for search offers", type=str),
    argument("--min_load", help="minimum floor load in perf units/s", type=float),
    argument("--target_util", help="target capacity utilization (fraction, max 1.0)", type=float),
    argument("--cold_mult", help="cold/stopped capacity target as multiple of hot capacity", type=float),
    argument("--cold_workers", help="min number of workers to keep 'cold'", type=int),
    argument("--auto_instance", help=argparse.SUPPRESS, type=str, default="prod"),
    usage="vastai create workergroup [OPTIONS]",
    help="Create a new autoscale group",
)
def create__workergroup(args):
    """Create a new workergroup."""
    if args.explain:
        print("request json: ")
        print({"template_hash": args.template_hash, "search_params": args.search_params})

    client = get_client(args)
    try:
        result = endpoints_api.create_workergroup(
            client, template_hash=args.template_hash, template_id=args.template_id,
            no_default=args.no_default, launch_args=args.launch_args,
            endpoint_name=args.endpoint_name, endpoint_id=args.endpoint_id,
            test_workers=args.test_workers, gpu_ram=args.gpu_ram,
            search_params=args.search_params, min_load=args.min_load,
            target_util=args.target_util, cold_mult=args.cold_mult,
            cold_workers=args.cold_workers, auto_instance=args.auto_instance,
        )
        print("workergroup create {}".format(result))
    except Exception as e:
        print(f"Error creating workergroup: {e}")


@parser.command(
    usage="vastai show workergroups [--api-key API_KEY]",
    help="Display user's current workergroups",
)
def show__workergroups(args):
    """Display user's current workergroups."""
    if args.explain:
        print("request json: ")
        print({"client_id": "me", "api_key": args.api_key})

    client = get_client(args)
    result = endpoints_api.show_workergroups(client)

    if isinstance(result, dict) and "error" in result:
        print(result["error"])
        return

    if args.raw:
        return result
    else:
        print(json.dumps(result, indent=1, sort_keys=True))


@parser.command(
    argument("id", help="id of autoscale group to update", type=int),
    argument("--min_load", help="minimum floor load in perf units/s", type=float),
    argument("--target_util", help="target capacity utilization (fraction, max 1.0)", type=float),
    argument("--cold_mult", help="cold/stopped capacity target as multiple of hot capacity", type=float),
    argument("--cold_workers", help="min number of workers to keep 'cold'", type=int),
    argument("--test_workers", help="number of test workers (default 3)", type=int),
    argument("--gpu_ram", help="estimated GPU RAM req", type=float),
    argument("--template_hash", help="template hash", type=str),
    argument("--template_id", help="template id", type=int),
    argument("--search_params", help="search param string for search offers", type=str),
    argument("-n", "--no-default", action="store_true", help="Disable default search param query args"),
    argument("--launch_args", help="launch args string for create instance", type=str),
    argument("--endpoint_name", help="deployment endpoint name", type=str),
    argument("--endpoint_id", help="deployment endpoint id", type=int),
    usage="vastai update workergroup WORKERGROUP_ID [OPTIONS]",
    help="Update an existing autoscale group",
)
def update__workergroup(args):
    """Update an existing workergroup."""
    client = get_client(args)
    result = endpoints_api.update_workergroup(
        client, id=args.id,
        min_load=args.min_load, target_util=args.target_util,
        cold_mult=args.cold_mult, cold_workers=args.cold_workers,
        test_workers=args.test_workers, gpu_ram=args.gpu_ram,
        template_hash=args.template_hash, template_id=args.template_id,
        search_params=args.search_params, no_default=args.no_default,
        launch_args=args.launch_args, endpoint_name=args.endpoint_name,
        endpoint_id=args.endpoint_id,
    )
    if args.raw:
        return result
    print("workergroup update {}".format(result))


@parser.command(
    argument("id", help="id of group to delete", type=int),
    usage="vastai delete workergroup ID",
    help="Delete a workergroup group",
)
def delete__workergroup(args):
    """Delete a workergroup."""
    id = args.id
    if args.explain:
        print("request json: ")
        print({"client_id": "me", "autojob_id": args.id})

    client = get_client(args)
    result = endpoints_api.delete_workergroup(client, id=id)
    print("workergroup delete {}".format(result))


@parser.command(
    argument("id", help="id of workergroup to fetch logs from", type=int),
    argument("--level", help="log detail level (0 to 3)", type=int, default=1),
    argument("--tail", help="", type=int, default=None),
    usage="vastai get wrkgrp-logs ID [--api-key API_KEY]",
    help="Fetch logs for a specific serverless worker group",
)
def get__wrkgrp_logs(args):
    """Fetch logs for a specific serverless worker group."""
    if args.explain:
        print(f"Fetching workergroup logs for id={args.id}")

    client = get_client(args)
    rj = endpoints_api.get_wrkgrp_logs(client, id=args.id, level=args.level, tail=args.tail)

    levels = {0: "info0", 1: "info1", 2: "trace", 3: "debug"}

    if isinstance(rj, dict) and "error" in rj:
        print(rj["error"])
        return

    if args.raw:
        return rj
    else:
        dbg_lvl = levels[args.level]
        if rj and dbg_lvl:
            print(rj[dbg_lvl])
