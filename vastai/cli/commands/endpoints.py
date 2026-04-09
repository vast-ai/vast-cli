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
    argument("--min_load", help="minimum floor load in perf units/s  (token/s for LLms)", type=float, default=0.0),
    argument("--min_cold_load", help="minimum floor load in perf units/s (token/s for LLms), but allow handling with cold workers", type=float, default=0.0),
    argument("--target_util", help="target capacity utilization (fraction, max 1.0, default 0.9)", type=float, default=0.9),
    argument("--cold_mult",   help="cold/stopped instance capacity target as multiple of hot capacity target (default 2.5)", type=float, default=2.5),
    argument("--cold_workers", help="min number of workers to keep 'cold' when you have no load (default 5)", type=int, default=5),
    argument("--max_workers", help="max number of workers your endpoint group can have (default 20)", type=int, default=20),
    argument("--endpoint_name", help="deployment endpoint name (allows multiple autoscale groups to share same deployment endpoint)", type=str),
    argument("--max_queue_time", help="maximum seconds requests may be queued on each worker (default 30.0)", type=float),
    argument("--target_queue_time", help="target seconds for the queue to be cleared (default 10.0)", type=float),
    argument("--inactivity_timeout", help="seconds of no traffic before the endpoint can scale to zero active workers", type=int),
    argument("--auto_instance", help=argparse.SUPPRESS, type=str, default="prod"),
    usage="vastai create endpoint [OPTIONS]",
    help="Create a new endpoint group",
    epilog=deindent("""
        Create a new endpoint group to manage many autoscaling groups

        Example: vastai create endpoint --target_util 0.9 --cold_mult 2.0 --endpoint_name "LLama"
    """),
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
    result = endpoints_api.create_endpoint(
        client, min_load=args.min_load, min_cold_load=args.min_cold_load,
        target_util=args.target_util, cold_mult=args.cold_mult,
        cold_workers=args.cold_workers, max_workers=args.max_workers,
        endpoint_name=args.endpoint_name, auto_instance=args.auto_instance,
        max_queue_time=args.max_queue_time, target_queue_time=args.target_queue_time,
        inactivity_timeout=args.inactivity_timeout,
    )
    if args.raw:
        return result
    print("create endpoint {}".format(result))


@parser.command(
    usage="vastai show endpoints [--api-key API_KEY]",
    help="Display user's current endpoint groups",
    epilog=deindent("""
        Example: vastai show endpoints
    """),
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
    argument("--min_load", help="minimum floor load in perf units/s  (token/s for LLms)", type=float),
    argument("--min_cold_load", help="minimum floor load in perf units/s  (token/s for LLms), but allow handling with cold workers", type=float),
    argument("--endpoint_state", help="active, suspended, or stopped", type=str),
    argument("--auto_instance", help=argparse.SUPPRESS, type=str, default="prod"),
    argument("--target_util",      help="target capacity utilization (fraction, max 1.0, default 0.9)", type=float),
    argument("--cold_mult",   help="cold/stopped instance capacity target as multiple of hot capacity target (default 2.5)", type=float),
    argument("--cold_workers", help="min number of workers to keep 'cold' when you have no load (default 5)", type=int),
    argument("--max_workers", help="max number of workers your endpoint group can have (default 20)", type=int),
    argument("--endpoint_name",   help="deployment endpoint name (allows multiple workergroups to share same deployment endpoint)", type=str),
    argument("--max_queue_time", help="maximum seconds requests may be queued on each worker (default 30.0)", type=float),
    argument("--target_queue_time", help="target seconds for the queue to be cleared (default 10.0)", type=float),
    argument("--inactivity_timeout", help="seconds of no traffic before the endpoint can scale to zero active workers", type=int),
    usage="vastai update endpoint ID [OPTIONS]",
    help="Update an existing endpoint group",
    epilog=deindent("""
        Example: vastai update endpoint 4242 --min_load 100 --target_util 0.9 --cold_mult 2.0 --endpoint_name "LLama"
    """),
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
        inactivity_timeout=args.inactivity_timeout,
    )
    if args.raw:
        return result
    print("update endpoint {}".format(result))


@parser.command(
    argument("id", help="id of endpoint group to delete", type=int),
    usage="vastai delete endpoint ID ",
    help="Delete an endpoint group",
    epilog=deindent("""
        Example: vastai delete endpoint 4242
    """),
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
    epilog=deindent("""
        Example: vastai get endpt-logs 382
    """),
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
    argument("--template_hash", help="template hash (required, but **Note**: if you use this field, you can skip search_params, as they are automatically inferred from the template)", type=str),
    argument("--template_id",   help="template id (optional)", type=int),
    argument("-n", "--no-default", action="store_true", help="Disable default search param query args"),
    argument("--launch_args",   help="launch args  string for create instance  ex: \"--onstart onstart_wget.sh  --env '-e ONSTART_PATH=https://s3.amazonaws.com/vast.ai/onstart_OOBA.sh' --image atinoda/text-generation-webui:default-nightly --disk 64\"", type=str),
    argument("--endpoint_name", help="deployment endpoint name (allows multiple workergroups to share same deployment endpoint)", type=str),
    argument("--endpoint_id",   help="deployment endpoint id (allows multiple workergroups to share same deployment endpoint)", type=int),
    argument("--test_workers",help="number of workers to create to get an performance estimate for while initializing workergroup (default 3)", type=int, default=3),
    argument("--gpu_ram",     help="estimated GPU RAM req  (independent of search string)", type=float),
    argument("--search_params", help="search param string for search offers    ex: \"gpu_ram>=23 num_gpus=2 gpu_name=RTX_4090 inet_down>200 direct_port_count>2 disk_space>=64\"", type=str),
    argument("--min_load", help="[NOTE: this field isn't currently used at the workergroup level] minimum floor load in perf units/s  (token/s for LLms)", type=float),
    argument("--target_util", help="[NOTE: this field isn't currently used at the workergroup level] target capacity utilization (fraction, max 1.0, default 0.9)", type=float),
    argument("--cold_mult",   help="[NOTE: this field isn't currently used at the workergroup level]cold/stopped instance capacity target as multiple of hot capacity target (default 2.0)", type=float),
    argument("--cold_workers",   help="min number of workers to keep 'cold' for this workergroup", type=int),
    argument("--auto_instance", help=argparse.SUPPRESS, type=str, default="prod"),
    usage="vastai create workergroup [OPTIONS]",
    help="Create a new autoscale group",
    epilog=deindent("""
        Create a new autoscaling group to manage a pool of worker instances.

        Example: vastai create workergroup --template_hash HASH  --endpoint_name "LLama" --test_workers 5
    """),
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
    epilog=deindent("""
        Example: vastai show workergroups
    """),
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
    argument("--min_load", help="minimum floor load in perf units/s  (token/s for LLms)", type=float),
    argument("--target_util",      help="target capacity utilization (fraction, max 1.0, default 0.9)", type=float),
    argument("--cold_mult",   help="cold/stopped instance capacity target as multiple of hot capacity target (default 2.5)", type=float),
    argument("--cold_workers",   help="min number of workers to keep 'cold' for this workergroup", type=int),
    argument("--test_workers",help="number of workers to create to get an performance estimate for while initializing workergroup (default 3)", type=int),
    argument("--gpu_ram",   help="estimated GPU RAM req  (independent of search string)", type=float),
    argument("--template_hash",   help="template hash (**Note**: if you use this field, you can skip search_params, as they are automatically inferred from the template)", type=str),
    argument("--template_id",   help="template id", type=int),
    argument("--search_params",   help="search param string for search offers    ex: \"gpu_ram>=23 num_gpus=2 gpu_name=RTX_4090 inet_down>200 direct_port_count>2 disk_space>=64\"", type=str),
    argument("-n", "--no-default", action="store_true", help="Disable default search param query args"),
    argument("--launch_args",   help="launch args  string for create instance  ex: \"--onstart onstart_wget.sh  --env '-e ONSTART_PATH=https://s3.amazonaws.com/public.vast.ai/onstart_OOBA.sh' --image atinoda/text-generation-webui:default-nightly --disk 64\"", type=str),
    argument("--endpoint_name",   help="deployment endpoint name (allows multiple workergroups to share same deployment endpoint)", type=str),
    argument("--endpoint_id",   help="deployment endpoint id (allows multiple workergroups to share same deployment endpoint)", type=int),
    usage="vastai update workergroup WORKERGROUP_ID --endpoint_id ENDPOINT_ID [options]",
    help="Update an existing autoscale group",
    epilog=deindent("""
        Example: vastai update workergroup 4242 --min_load 100 --target_util 0.9 --cold_mult 2.0 --search_params \"gpu_ram>=23 num_gpus=2 gpu_name=RTX_4090 inet_down>200 direct_port_count>2 disk_space>=64\" --launch_args \"--onstart onstart_wget.sh  --env '-e ONSTART_PATH=https://s3.amazonaws.com/public.vast.ai/onstart_OOBA.sh' --image atinoda/text-generation-webui:default-nightly --disk 64\" --gpu_ram 32.0 --endpoint_name "LLama" --endpoint_id 2
    """),
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
    argument("id", help="id of workergroup to update workers for", type=int),
    argument("--cancel", action="store_true", help="cancel an in-progress update for the workergroup"),
    usage="vastai update workers WORKERGROUP_ID [--cancel]",
    help="Trigger a rolling update of all workers in a workergroup, or cancel an in-progress update",
    epilog=deindent("""
        Starts a rolling update of all workers in the specified workergroup. The autoscaler
        will cycle through workers, updating them while maintaining capacity.

        Use --cancel to cancel an update that is currently in progress.

        Examples:
            vastai update workers 4242
            vastai update workers 4242 --cancel
    """),
)
def update__workers(args):
    """Trigger a rolling update of workers in a workergroup."""
    client = get_client(args)
    result = endpoints_api.update_workers(client, id=args.id, cancel=args.cancel)
    if args.raw:
        return result
    if result.get("success"):
        if result.get("cancelled"):
            print(f"Update cancelled for workergroup {args.id}")
        else:
            print(f"Update started for workergroup {args.id} ({result.get('workers_to_update', 0)} workers)")
    else:
        print(f"Error: {result.get('error_msg', 'unknown error')}")


@parser.command(
    argument("id", help="id of group to delete", type=int),
    usage="vastai delete workergroup ID ",
    help="Delete a workergroup group",
    epilog=deindent("""
        Note that deleting a workergroup doesn't automatically destroy all the instances that are associated with your workergroup.
        Example: vastai delete workergroup 4242
    """),
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
    epilog=deindent("""
        Example: vastai get endpt-logs 382
    """),
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
