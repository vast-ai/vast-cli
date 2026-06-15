"""CLI commands for managing host machines."""

import json
import os
import sys
import time
import textwrap
import warnings
import argparse
from contextlib import redirect_stdout, redirect_stderr

import requests
import urllib3

from vastai.cli.parser import argument
from vastai.cli.display import (
    display_table, machine_fields, maintenance_fields,
    network_disk_fields, network_disk_machine_fields, deindent,
)
from vastai.api import machines as machines_api
from vastai.api import instances as instances_api
from vastai.api import offers as offers_api
from vastai.api import storage as storage_api


from vastai.cli.utils import get_parser as _get_parser, get_client  # noqa: F401
from vastai.cli.self_test.machine_diagnostics import (
    base_result,
    compact_offer_metadata,
    failed_checks,
    no_offer_failure,
    preflight_requirement_checks,
    render_preflight_advisories,
    render_preflight_failure,
    requirement_failure,
)
from vastai.cli.self_test.runtime_diagnostics import (
    DAEMON_STARTUP_FAILED,
    INSTANCE_CREATE_FAILED,
    INSTANCE_CREATE_MISSING_CONTRACT,
    INSTANCE_OFFLINE_BEFORE_TEST,
    INSTANCE_START_TIMEOUT,
    INTERRUPTED,
    LegacyProgressParser,
    MISSING_PUBLIC_IP,
    PROGRESS_CONTAINER_PORT,
    PROGRESS_EMPTY_TIMEOUT,
    PROGRESS_ENDPOINT_LOST,
    PROGRESS_ENDPOINT_UNREACHABLE,
    PROGRESS_PORT_NOT_MAPPED,
    RUNTIME_TEST_TIMEOUT,
    classify_status_msg,
    make_progress_endpoint_diagnostic,
    make_failure,
    redact_secret_text,
    refine_startup_failure_with_daemon_log,
)
from vastai.cli.self_test.support_bundle import (
    create_support_bundle,
    format_bundle_summary,
    support_bundles_enabled,
)


parser = _get_parser()
SELF_TEST_INSTANCE_LABEL_PREFIX = "vast-self-test-machine"
INSTANCE_LOG_TAIL_LINES = 1000
SELF_TEST_LOG_LEVELS = ("critical", "error", "warning", "info", "debug")
SELF_TEST_LOG_LEVEL_PRIORITY = {
    "debug": 10,
    "info": 20,
    "warning": 30,
    "error": 40,
    "critical": 50,
}


# ---------------------------------------------------------------------------
# show machine / machines
# ---------------------------------------------------------------------------

@parser.command(
    argument("Machine", help="id of machine to display", type=int),
    argument("-q", "--quiet", action="store_true", help="only display numeric ids"),
    usage="vastai show machine ID [OPTIONS]",
    help="[Host] Show hosted machines",
)
def show__machine(args):
    """Show a machine the host is offering for rent."""
    client = get_client(args)
    rows = machines_api.show_machine(client, id=args.Machine)
    if args.raw:
        return rows
    else:
        if args.quiet:
            ids = [f"{row['id']}" for row in rows]
            print(" ".join(id for id in ids))
        else:
            display_table(rows, machine_fields)


@parser.command(
    argument("-q", "--quiet", action="store_true", help="only display numeric ids"),
    usage="vastai show machines [OPTIONS]",
    help="[Host] Show hosted machines",
)
def show__machines(args):
    """Show the machines user is offering for rent."""
    client = get_client(args)
    rows = machines_api.show_machines(client)
    if args.raw:
        return {"machines": rows}
    else:
        if args.quiet:
            ids = [f"{row['id']}" for row in rows]
            print(" ".join(id for id in ids))
        else:
            display_table(rows, machine_fields)


# ---------------------------------------------------------------------------
# show maints
# ---------------------------------------------------------------------------

@parser.command(
    argument("-i", "--ids", help="comma separated string of machine_ids for which to get maintenance information", type=str),
    argument("-q", "--quiet", action="store_true", help="only display numeric ids of the machines in maintenance"),
    usage="vastai show maints --ids 'machine_id_1[,machine_id_2,...]' [OPTIONS]",
    help="[Host] Show maintenance information for host machines",
)
def show__maints(args):
    """Show the maintenance information for the machines."""
    machine_ids = args.ids.split(',')
    machine_ids = list(map(int, machine_ids))

    client = get_client(args)
    rows = machines_api.show_maints(client, machine_ids=machine_ids)
    if args.raw:
        return rows
    else:
        if args.quiet:
            ids = [f"{row['machine_id']}" for row in rows]
            print(" ".join(id for id in ids))
        else:
            display_table(rows, maintenance_fields)


# ---------------------------------------------------------------------------
# show network-disks
# ---------------------------------------------------------------------------

@parser.command(
    usage="vastai show network-disks",
    help="[Host] Show network disks associated with your account.",
    epilog=deindent("""
        Show network disks associated with your account.
    """)
)
def show__network_disks(args):
    """Show network disks associated with your account."""
    client = get_client(args)
    response_data = storage_api.show_network_disks(client)

    if args.raw:
        return response_data

    for cluster_data in response_data['data']:
        print(f"Cluster ID: {cluster_data['cluster_id']}")
        display_table(cluster_data['network_disks'], network_disk_fields, replace_spaces=False)

        machine_rows = []
        for machine_id in cluster_data['machine_ids']:
            machine_rows.append({
                "machine_id": machine_id,
                "mount_point": cluster_data['mounts'].get(str(machine_id), "N/A"),
            })
        print()
        display_table(machine_rows, network_disk_machine_fields, replace_spaces=False)
        print("\n")


# ---------------------------------------------------------------------------
# list machine / machines
# ---------------------------------------------------------------------------

def list_machine_impl(args, id):
    """Shared logic for listing a single machine."""
    from vastai.cli.util import string_to_unix_epoch

    client = get_client(args)
    end_date = string_to_unix_epoch(args.end_date) if args.end_date else None

    json_blob = {
        'machine': id,
        'price_gpu': args.price_gpu,
        'price_disk': args.price_disk,
        'price_inetu': args.price_inetu,
        'price_inetd': args.price_inetd,
        'price_min_bid': args.price_min_bid,
        'min_chunk': args.min_chunk,
        'end_date': end_date,
        'credit_discount_max': args.discount_rate,
        'duration': args.duration,
        'vol_size': args.vol_size,
        'vol_price': args.vol_price,
    }
    if args.explain:
        print("request json: ")
        print(json_blob)

    rj = machines_api.list_machine(
        client, id=id, price_gpu=args.price_gpu, price_disk=args.price_disk,
        price_inetu=args.price_inetu, price_inetd=args.price_inetd,
        price_min_bid=args.price_min_bid, min_chunk=args.min_chunk,
        end_date=end_date, discount_rate=args.discount_rate,
        duration=args.duration, vol_size=args.vol_size, vol_price=args.vol_price,
    )

    if rj.get("success"):
        price_gpu_ = str(args.price_gpu) if args.price_gpu is not None else "def"
        price_inetu_ = str(args.price_inetu)
        price_inetd_ = str(args.price_inetd)
        min_chunk_ = str(args.min_chunk)
        discount_rate_ = str(args.discount_rate)
        duration_ = str(args.duration)
        if args.raw:
            return rj
        else:
            print(f"offers created/updated for machine {id},  @ ${price_gpu_}/gpu/hr, ${price_inetu_}/GB up, ${price_inetd_}/GB down, {min_chunk_}/min gpus, max discount_rate {discount_rate_}, duration {duration_}")
            num_extended = rj.get("extended", 0)
            if num_extended > 0:
                print(f"extended {num_extended} client contracts to {args.end_date}")
    else:
        if args.raw:
            return rj
        else:
            print(rj.get("msg", rj))


@parser.command(
    argument("id", help="id of machine to list", type=int),
    argument("-g", "--price_gpu", help="per gpu rental price in $/hour  (price for active instances)", type=float),
    argument("-s", "--price_disk",
             help="storage price in $/GB/month (price for inactive instances), default: $0.10/GB/month", type=float),
    argument("-u", "--price_inetu", help="price for internet upload bandwidth in $/GB", type=float),
    argument("-d", "--price_inetd", help="price for internet download bandwidth in $/GB", type=float),
    argument("-b", "--price_min_bid", help="per gpu minimum bid price floor in $/hour", type=float),
    argument("-r", "--discount_rate", help="Max long term prepay discount rate fraction, default: 0.4 ", type=float),
    argument("-m", "--min_chunk", help="minimum amount of gpus (default: 1)", type=int, default=1),
    argument("-e", "--end_date", help="contract offer expiration - the available until date (optional, in unix float timestamp or MM/DD/YYYY format)", type=str),
    argument("-l", "--duration", help="Updates end_date daily to be duration from current date. Cannot be combined with end_date. Format is: `n days`, `n weeks`, `n months`, `n years`, or total intended duration in seconds."),
    argument("-v", "--vol_size", help="Size for volume contract offer. Defaults to half of available disk. Set 0 to not create a volume contract offer.", type=int),
    argument("-z", "--vol_price", help="Price for disk on volume contract offer. Defaults to price_disk. Invalid if vol_size is 0.", type=float),
    usage="vastai list machine ID [options]",
    help="[Host] list a machine for rent",
    epilog=deindent("""
        Performs the same action as pressing the "LIST" button on the site https://cloud.vast.ai/host/machines.
        On the end date the listing will expire and your machine will unlist. However any existing client jobs will still remain until ended by their owners.
        Once you list your machine and it is rented, it is extremely important that you don't interfere with the machine in any way.
        If your machine has an active client job and then goes offline, crashes, or has performance problems, this could permanently lower your reliability rating.
        We strongly recommend you test the machine first and only list when ready.

        Raising any resource price above the current contract price writes a
        pending row to `pending_price_increases` for each affected client.
        Clients review and accept those rows via the console or
        `vastai show pending-price-increases`; auto-extend stops at the old
        price until they accept.
    """)
)
def list__machine(args):
    """List a machine for rent."""
    return list_machine_impl(args, args.id)


@parser.command(
    argument("ids", help="ids of machines to list", type=int, nargs='+'),
    argument("-g", "--price_gpu", help="per gpu on-demand rental price in $/hour (base price for active instances)", type=float),
    argument("-s", "--price_disk",
             help="storage price in $/GB/month (price for inactive instances), default: $0.10/GB/month", type=float),
    argument("-u", "--price_inetu", help="price for internet upload bandwidth in $/GB", type=float),
    argument("-d", "--price_inetd", help="price for internet download bandwidth in $/GB", type=float),
    argument("-b", "--price_min_bid", help="per gpu minimum bid price floor in $/hour", type=float),
    argument("-r", "--discount_rate", help="Max long term prepay discount rate fraction, default: 0.4 ", type=float),
    argument("-m", "--min_chunk", help="minimum amount of gpus (default: 1)", type=int, default=1),
    argument("-e", "--end_date", help="contract offer expiration - the available until date (optional, in unix float timestamp or MM/DD/YYYY format)", type=str),
    argument("-l", "--duration", help="Updates end_date daily to be duration from current date. Cannot be combined with end_date. Format is: `n days`, `n weeks`, `n months`, `n years`, or total intended duration in seconds."),
    argument("-v", "--vol_size", help="Size for volume contract offer. Defaults to half of available disk. Set 0 to not create a volume contract offer.", type=int),
    argument("-z", "--vol_price", help="Price for disk on volume contract offer. Defaults to price_disk. Invalid if vol_size is 0.", type=float),
    usage="vastai list machines IDs [options]",
    help="[Host] list machines for rent",
    epilog=deindent("""
        This variant can be used to list or update the listings for multiple machines at once with the same args.
        You could extend the end dates of all your machines using a command combo like this:
        ./vast.py list machines $(./vast.py show machines -q) -e 12/31/2024 --retry 6
    """)
)
def list__machines(args):
    """List multiple machines for rent."""
    return [list_machine_impl(args, id) for id in args.ids]


# ---------------------------------------------------------------------------
# unlist machine
# ---------------------------------------------------------------------------

@parser.command(
    argument("id", help="id of machine to unlist", type=int),
    usage="vastai unlist machine <id>",
    help="[Host] Unlist a listed machine",
)
def unlist__machine(args):
    """Remove machine from list of machines for rent."""
    client = get_client(args)
    rj = machines_api.unlist_machine(client, id=args.id)
    if rj.get("success"):
        print("all offers for machine {machine_id} removed, machine delisted.".format(machine_id=args.id))
    else:
        print(rj.get("msg", rj))


# ---------------------------------------------------------------------------
# delete machine
# ---------------------------------------------------------------------------

@parser.command(
    argument("id", help="id of machine to delete", type=int),
    usage="vastai delete machine <id>",
    help="[Host] Delete machine if the machine is not being used by clients. host jobs on their own machines are disregarded and machine is force deleted.",
)
def delete__machine(args):
    """Delete machine if the machine is not being used by clients."""
    client = get_client(args)
    rj = machines_api.delete_machine(client, id=args.id)
    if rj.get("success"):
        print("deleted machine_id ({machine_id}) and all related contracts.".format(machine_id=args.id))
    else:
        print(rj.get("msg", rj))


# ---------------------------------------------------------------------------
# cleanup machine
# ---------------------------------------------------------------------------

@parser.command(
    argument("id", help="id of machine to cleanup", type=int),
    usage="vastai cleanup machine ID [options]",
    help="[Host] Remove all expired storage instances from the machine, freeing up space",
    epilog=deindent("""
        Instances expire on their end date. Expired instances still pay storage fees, but can not start.
        Since hosts are still paid storage fees for expired instances, we do not auto delete them.
        Instead you can use this CLI/API function to delete all expired storage instances for a machine.
        This is useful if you are running low on storage, want to do maintenance, or are subsidizing storage, etc.
    """)
)
def cleanup__machine(args):
    """Remove expired storage instances from a machine."""
    client = get_client(args)
    rj = machines_api.cleanup_machine(client, id=args.id)

    if args.raw:
        return rj
    if rj.get("success"):
        print(json.dumps(rj, indent=1))
    else:
        print(rj.get("msg", rj))


# ---------------------------------------------------------------------------
# defrag machines
# ---------------------------------------------------------------------------

@parser.command(
    argument("IDs", help="ids of machines", type=int, nargs='+'),
    usage="vastai defragment machines IDs ",
    help="[Host] Defragment machines",
    epilog=deindent("""
        Defragment some of your machines. This will rearrange GPU assignments to try and make more multi-gpu offers available.
    """),
)
def defrag__machines(args):
    """Defragment machines to make more multi-gpu offers available."""
    if args.explain:
        print("request json: ")
        print({"machine_ids": args.IDs})

    client = get_client(args)
    try:
        result = machines_api.defrag_machines(client, machine_ids=args.IDs)
        print(f"defragment result: {result}")
    except Exception as e:
        print(f"Error: {e}")


# ---------------------------------------------------------------------------
# set min_bid
# ---------------------------------------------------------------------------

@parser.command(
    argument("id", help="id of machine to set min bid price for", type=int),
    argument("--price", help="per gpu min bid price in $/hour", type=float),
    usage="vastai set min_bid id [--price PRICE]",
    help="[Host] Set the minimum bid/rental price for a machine",
    epilog=deindent("""
        Change the current min bid price of machine id to PRICE.
    """),
)
def set__min_bid(args):
    """Set the minimum bid/rental price for a machine."""
    if args.explain:
        print("request json: ")
        print({"client_id": "me", "price": args.price})

    client = get_client(args)
    machines_api.set_min_bid(client, id=args.id, price=args.price)
    print("Per gpu min bid price changed")


# ---------------------------------------------------------------------------
# set defjob
# ---------------------------------------------------------------------------

@parser.command(
    argument("id", help="id of machine to launch default instance on", type=int),
    argument("--price_gpu", help="per gpu rental price in $/hour", type=float),
    argument("--price_inetu", help="price for internet upload bandwidth in $/GB", type=float),
    argument("--price_inetd", help="price for internet download bandwidth in $/GB", type=float),
    argument("--image", help="docker container image to launch", type=str),
    argument("--args", nargs=argparse.REMAINDER, help="list of arguments passed to container launch"),
    usage="vastai set defjob id [--api-key API_KEY] [--price_gpu PRICE_GPU] [--price_inetu PRICE_INETU] [--price_inetd PRICE_INETD] [--image IMAGE] [--args ...]",
    help="[Host] Create default jobs for a machine",
    epilog=deindent("""
        Performs the same action as creating a background job at https://cloud.vast.ai/host/create.
    """)
)
def set__defjob(args):
    """Create default jobs for a machine."""
    if args.explain:
        print("request json: ")
        print({'machine': args.id, 'price_gpu': args.price_gpu, 'price_inetu': args.price_inetu,
               'price_inetd': args.price_inetd, 'image': args.image, 'args': args.args})

    client = get_client(args)
    rj = machines_api.set_defjob(client, id=args.id, price_gpu=args.price_gpu,
                                  price_inetu=args.price_inetu, price_inetd=args.price_inetd,
                                  image=args.image, args=args.args)
    if rj.get("success"):
        print("bids created for machine {args.id},  @ ${args.price_gpu}/gpu/day, ${args.price_inetu}/GB up, ${args.price_inetd}/GB down".format(**locals()))
    else:
        print(rj.get("msg", rj))


# ---------------------------------------------------------------------------
# remove defjob
# ---------------------------------------------------------------------------

@parser.command(
    argument("id", help="id of machine to remove default instance from", type=int),
    usage="vastai remove defjob id",
    help="[Host] Delete default jobs",
)
def remove__defjob(args):
    """Delete default jobs for a machine."""
    client = get_client(args)
    rj = machines_api.remove_defjob(client, id=args.id)

    if rj.get("success"):
        print("default instance for machine {machine_id} removed.".format(machine_id=args.id))
    else:
        print(rj.get("msg", rj))


# ---------------------------------------------------------------------------
# schedule / cancel maint
# ---------------------------------------------------------------------------

@parser.command(
    argument("id", help="id of machine to schedule maintenance for", type=int),
    argument("--sdate", help="maintenance start date in unix epoch time (UTC seconds)", type=float),
    argument("--duration", help="maintenance duration in hours", type=float),
    argument("--maintenance_category", help="(optional) can be one of [power, internet, disk, gpu, software, other]", type=str, default="not provided"),
    usage="vastai schedule maintenance id [--sdate START_DATE --duration DURATION --maintenance_category MAINTENANCE_CATEGORY]",
    help="[Host] Schedule upcoming maint window",
    epilog=deindent("""
        The proper way to perform maintenance on your machine is to wait until all active contracts have expired or the machine is vacant.
        For unplanned or unscheduled maintenance, use this schedule maint command. That will notify the client that you have to take the machine down and that they should save their work.
        You can specify a date, duration, reason and category for the maintenance.

        Example: vastai schedule maint 8207 --sdate 1677562671 --duration 0.5 --maintenance_category "power"
    """),
    )
def schedule__maint(args):
    """Schedule upcoming maintenance window."""
    from datetime import datetime, timezone
    from vastai.cli.util import string_to_unix_epoch

    dt = datetime.fromtimestamp(args.sdate, tz=timezone.utc)
    print(f"Scheduling maintenance window starting {dt} lasting {args.duration} hours")
    print(f"This will notify all clients of this machine.")
    ok = input("Continue? [y/n] ")
    if ok.strip().lower() != "y":
        return

    if args.explain:
        print("request json: ")
        print({"client_id": "me", "sdate": args.sdate, "duration": args.duration,
               "maintenance_category": args.maintenance_category})

    client = get_client(args)
    machines_api.schedule_maint(client, id=args.id, sdate=string_to_unix_epoch(args.sdate),
                                duration=args.duration, maintenance_category=args.maintenance_category)
    print(f"Maintenance window scheduled for {dt} success")


@parser.command(
    argument("id", help="id of machine to cancel maintenance(s) for", type=int),
    usage="vastai cancel maint id",
    help="[Host] Cancel maint window",
    epilog=deindent("""
        For deleting a machine's scheduled maintenance window(s), use this cancel maint command.
        Example: vastai cancel maint 8207
    """),
    )
def cancel__maint(args):
    """Cancel scheduled maintenance window(s)."""
    print(f"Cancelling scheduled maintenance window(s) for machine {args.id}.")
    ok = input("Continue? [y/n] ")
    if ok.strip().lower() != "y":
        return

    if args.explain:
        print("request json: ")
        print({"client_id": "me", "machine_id": args.id})

    client = get_client(args)
    machines_api.cancel_maint(client, id=args.id)
    print(f"Cancel maintenance window(s) scheduled for machine {args.id} success")


# ---------------------------------------------------------------------------
# add network-disk
# ---------------------------------------------------------------------------

@parser.command(
    argument("machines", help="ids of machines to add disk to, that is networked to be on the same LAN as machine", type=int, nargs='+'),
    argument("mount_point", help="mount path of disk to add", type=str),
    argument("-d", "--disk_id", help="id of network disk to attach to machines in the cluster", type=int, nargs='?'),
    usage="vastai add network-disk MACHINES MOUNT_PATH [options]",
    help="[Host] Add Network Disk to Physical Cluster.",
    epilog=deindent("""
        This variant can be used to add a network disk to a physical cluster.
        When you add a network disk for the first time, you just need to specify the machine(s) and mount_path.
        When you add a network disk for the second time, you need to specify the disk_id.
        Example:
        vastai add network-disk 1 /mnt/disk1
        vastai add network-disk 1 /mnt/disk1 -d 12345
    """)
)
def add__network_disk(args):
    """Add network disk to a physical cluster."""
    if args.explain:
        print("request json: ")
        print({"machines": [int(id) for id in args.machines], "mount_point": args.mount_point, "disk_id": args.disk_id})

    client = get_client(args)
    result = storage_api.add_network_disk(client, machines=args.machines, mount_point=args.mount_point,
                                           disk_id=args.disk_id)

    if args.raw:
        return result

    print("Attached network disk to machines. Disk id: " + str(result["disk_id"]))


# ---------------------------------------------------------------------------
# dump-logs
# ---------------------------------------------------------------------------

def _diagnostic_error(error):
    return redact_secret_text(error) or ""


def _artifact_text(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def collect_instance_log_artifacts(client, instance_id):
    files = {}
    errors = []

    try:
        instance_info = instances_api.show_instance(client, id=instance_id)
        files["instance/show-instance.json"] = _artifact_text(instance_info)
    except Exception as e:
        errors.append({
            "artifact": "instance/show-instance.json",
            "error": _diagnostic_error(e),
        })

    for archive_name, daemon_logs in (
        ("instance/container.log", False),
        ("instance/daemon.log", True),
    ):
        try:
            logs = instances_api.logs(
                client,
                instance_id=instance_id,
                tail=INSTANCE_LOG_TAIL_LINES,
                daemon_logs=daemon_logs,
            )
            files[archive_name] = _artifact_text(logs)
        except Exception as e:
            errors.append({
                "artifact": archive_name,
                "error": _diagnostic_error(e),
            })

    return files, errors


def resolve_self_test_log_level(args):
    """Resolve self-test log level from CLI args, legacy flag, and env."""
    arg_level = getattr(args, "log_level", None)
    if arg_level:
        return arg_level.lower(), "argument"
    if getattr(args, "debugging", False):
        return "debug", "debugging"
    env_level = os.environ.get("VAST_LOG_LEVEL")
    if env_level:
        normalized = env_level.strip().lower()
        if normalized in SELF_TEST_LOG_LEVELS:
            return normalized, "VAST_LOG_LEVEL"
        return "info", "default_invalid_VAST_LOG_LEVEL"
    return "info", "default"


@parser.command(
    argument("machine_id", help="Machine ID", type=str),
    argument("--instance-id", help="Instance ID to pull Vast instance logs from", type=int),
    argument("--output-dir", help="Directory for the diagnostic bundle (default: /tmp)", type=str),
    argument(
        "--include-local-host-artifacts",
        action="store_true",
        help="Include local OS/kaalia artifacts; only use when running on the actual Vast host",
    ),
    usage=(
        "vastai dump-logs <machine_id> [--instance-id INSTANCE_ID] "
        "[--output-dir DIR] [--include-local-host-artifacts]"
    ),
    help="[Host] Bundle self-test diagnostics for support",
    epilog=deindent("""
        Creates a redacted diagnostic tarball containing CLI-visible self-test
        evidence. If --instance-id is provided, the command also pulls container
        and daemon logs from the Vast instance logs API.

        Local OS/kaalia artifacts are only collected with
        --include-local-host-artifacts. Use that option only when running this
        command on the actual host machine; from a laptop, it would collect the
        laptop's logs instead.

        Example:
         vastai dump-logs 12345 --instance-id 67890
    """),
)
def dump_logs(args):
    run_started_at = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    cli_output = [f"Manual diagnostic bundle requested for machine {args.machine_id}."]
    extra_files = {}
    extra_errors = []
    if args.instance_id:
        client = get_client(args)
        cli_output.append(f"Requested Vast instance logs for instance {args.instance_id}.")
        instance_files, instance_errors = collect_instance_log_artifacts(client, args.instance_id)
        extra_files.update(instance_files)
        extra_errors.extend(instance_errors)
    else:
        cli_output.append("No --instance-id provided; Vast instance logs were not requested.")

    if not args.include_local_host_artifacts:
        cli_output.append(
            "Local host OS/kaalia artifacts were not collected. Use "
            "--include-local-host-artifacts only when running on the actual host."
        )

    try:
        bundle = create_support_bundle(
            machine_id=args.machine_id,
            output_dir=args.output_dir,
            result={
                "machine_id": args.machine_id,
                "stage": "manual_dump_logs",
                "reason": "Manual diagnostic bundle requested with vastai dump-logs.",
                "instance_id": args.instance_id,
                "includes_local_host_artifacts": args.include_local_host_artifacts,
            },
            cli_output=cli_output,
            extra_files=extra_files,
            extra_errors=extra_errors,
            run_started_at=run_started_at,
            command=sys.argv,
            secrets=[getattr(args, "api_key", None), os.environ.get("VAST_API_KEY")],
            include_local_host_artifacts=args.include_local_host_artifacts,
        )
    except Exception as e:
        error = _diagnostic_error(e)
        if getattr(args, "raw", False):
            return {
                "success": False,
                "machine_id": args.machine_id,
                "error": f"Failed to create diagnostic bundle: {error}",
            }
        print(f"WARNING: failed to create diagnostic bundle: {error}")
        sys.exit(1)
    if getattr(args, "raw", False):
        return bundle
    for line in format_bundle_summary(bundle):
        print(line)


# ---------------------------------------------------------------------------
# self-test machine
# ---------------------------------------------------------------------------

@parser.command(
    argument("machine_id", help="Machine ID", type=str),
    argument("--debugging", action="store_true", help="Enable debugging output"),
    argument(
        "--log-level",
        choices=SELF_TEST_LOG_LEVELS,
        help="Set self-test log level (default: VAST_LOG_LEVEL or info; info is compact, debug shows live diagnostics)",
    ),
    argument("--ignore-requirements", action="store_true", help="Ignore the minimum system requirements and run the self test regardless"),
    argument("--test-image", help="Use a custom self-test image for testing custom self-test images. Overrides VAST_SELF_TEST_IMAGE and CUDA mapping.", type=str),
    argument("--support-bundle-dir", help="Directory for failure diagnostic bundles (default: /tmp)", type=str),
    argument("--no-support-bundle", action="store_true", help="Do not create a diagnostic tarball when the self-test fails"),
    usage="vastai self-test machine <machine_id> [--debugging] [--log-level LEVEL] [--ignore-requirements] [--test-image IMAGE]",
    help="[Host] Perform a self-test on the specified machine",
    epilog=deindent("""
        This command tests if a machine meets specific requirements and
        runs a series of tests to ensure it's functioning correctly.

        Examples:
         vast self-test machine 12345
         vast self-test machine 12345 --debugging
    """),
)
def self_test__machine(args):
    """
    Performs a self-test on the specified machine to verify its compliance with
    required specifications and functionality.
    """
    instance_id = None
    result = base_result(args.machine_id)
    run_started_at = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    cli_output = []
    instance_log_files = {}
    instance_log_errors = []
    instance_log_collected = set()
    ignore_requirements_warning = (
        "WARNING: --ignore-requirements is set. Requirement checks are skipped as a "
        "pass/fail gate, and passing this self-test does not qualify this machine for verification."
    )

    if not hasattr(args, 'debugging'):
        args.debugging = False
    if not hasattr(args, 'log_level'):
        args.log_level = None
    if not hasattr(args, 'test_image'):
        args.test_image = None
    if not hasattr(args, 'support_bundle_dir'):
        args.support_bundle_dir = None
    if not hasattr(args, 'no_support_bundle'):
        args.no_support_bundle = False

    log_level, log_level_source = resolve_self_test_log_level(args)
    args.debugging = args.debugging or log_level == "debug"
    result["diagnostics"]["log_level"] = {
        "level": log_level,
        "source": log_level_source,
    }
    if getattr(args, "ignore_requirements", False):
        result["warning"] = ignore_requirements_warning
        result["diagnostics"]["requirements_ignored"] = True

    def output_line(*args_to_print):
        return " ".join(str(item) for item in args_to_print)

    def should_print(level):
        return (
            not args.raw
            and SELF_TEST_LOG_LEVEL_PRIORITY[level] >= SELF_TEST_LOG_LEVEL_PRIORITY[log_level]
        )

    def emit(level, *args_to_print):
        cli_output.append(output_line(*args_to_print))
        if should_print(level):
            print(*args_to_print)

    def progress_print(*args_to_print):
        emit("debug", *args_to_print)

    def info_print(*args_to_print):
        emit("info", *args_to_print)

    def warning_print(*args_to_print):
        emit("warning", *args_to_print)

    def error_print(*args_to_print):
        emit("error", *args_to_print)

    def summary_print(*args_to_print):
        cli_output.append(output_line(*args_to_print))
        if not args.raw:
            print(*args_to_print)

    def debug_print(*args_to_print):
        if args.debugging:
            cli_output.append(f"DEBUG: {output_line(*args_to_print)}")
        if args.debugging and not args.raw:
            print(*args_to_print)

    def collect_instance_logs(inst_id):
        if args.no_support_bundle or not support_bundles_enabled():
            return
        if not inst_id or inst_id in instance_log_collected:
            return
        instance_log_collected.add(inst_id)
        files, errors = collect_instance_log_artifacts(client, inst_id)
        instance_log_files.update(files)
        instance_log_errors.extend(errors)
        result["diagnostics"]["instance_log_collection"] = {
            "instance_id": inst_id,
            "files": sorted(instance_log_files.keys()),
            "collection_errors": instance_log_errors,
        }
        runtime_failure = result.get("diagnostics", {}).get("runtime_failure")
        refined_failure = refine_startup_failure_with_daemon_log(
            runtime_failure,
            instance_log_files.get("instance/daemon.log"),
        )
        if refined_failure != runtime_failure:
            set_runtime_failure(refined_failure, result.get("reason"))

    def ensure_support_bundle():
        if result.get("success"):
            return None
        if result.get("diagnostics", {}).get("support_bundle"):
            return result["diagnostics"]["support_bundle"]
        if args.no_support_bundle or not support_bundles_enabled():
            return None
        if instance_id:
            collect_instance_logs(instance_id)
        try:
            bundle = create_support_bundle(
                machine_id=args.machine_id,
                output_dir=args.support_bundle_dir,
                result=result,
                cli_output=cli_output,
                extra_files=instance_log_files,
                extra_errors=instance_log_errors,
                run_started_at=run_started_at,
                command=sys.argv,
                secrets=[getattr(args, "api_key", None), os.environ.get("VAST_API_KEY")],
                include_local_host_artifacts=False,
            )
        except Exception as e:
            error = redact_secret_text(e) or ""
            result["diagnostics"]["support_bundle_error"] = error
            warning_print(f"WARNING: failed to create self-test diagnostic bundle: {error}")
            return None
        result["diagnostics"]["support_bundle"] = bundle
        return bundle

    def finish_failure():
        if args.raw:
            ensure_support_bundle()
            return result
        if result.get("warning"):
            warning_print(result["warning"])
        render_runtime_failure()
        bundle = ensure_support_bundle()
        render_final_summary(bundle=bundle)
        sys.exit(1)

    def set_runtime_failure(diagnostic, fallback_reason=None):
        diagnostic = refine_startup_failure_with_daemon_log(
            diagnostic,
            instance_log_files.get("instance/daemon.log"),
        )
        result["failure"] = diagnostic
        result["failure_code"] = diagnostic["code"]
        result["stage"] = diagnostic.get("stage") or result.get("stage")
        result["reason"] = fallback_reason or diagnostic.get("summary") or ""
        result["diagnostics"]["runtime_failure"] = diagnostic

    def safe_error(error):
        return redact_secret_text(error) or ""

    def failure_display_reason():
        diagnostic = result.get("diagnostics", {}).get("runtime_failure")
        if diagnostic and diagnostic.get("summary"):
            return diagnostic["summary"]
        return result["reason"]

    def render_bundle_summary(bundle):
        if not bundle:
            return
        if log_level == "debug":
            for line in format_bundle_summary(bundle):
                summary_print(line)
            return
        summary_print(f"Support bundle: {bundle.get('path')}")
        errors = bundle.get("collection_errors") or []
        if errors:
            summary_print(f"Bundle collection warnings: {len(errors)} artifact(s) could not be collected.")

    def render_final_summary(bundle=None):
        success = bool(result.get("success"))
        summary_print("")
        summary_print("Self-test summary")
        summary_print(f"Status: {'passed' if success else 'failed'}")
        summary_print(f"Machine: {args.machine_id}")
        if result.get("stage") and not success:
            summary_print(f"Failed stage: {result['stage']}")
        if result.get("warning"):
            summary_print(f"Warning: {result['warning']}")
        failed = failed_checks(result.get("checks") or [])
        if failed:
            summary_print("Failed checks: " + ", ".join(check["title"] for check in failed))
        if success:
            if result.get("diagnostics", {}).get("preflight_failure"):
                summary_print("Result: runtime checks passed, but requirement checks were ignored.")
                summary_print("Next: resolve the failed requirement checks before relying on this for verification.")
            else:
                summary_print("Result: self-test completed successfully.")
            return
        summary_print(f"Reason: {failure_display_reason()}")
        render_bundle_summary(bundle)
        if bundle:
            summary_print("Next: inspect the support bundle or rerun with --log-level debug for live details.")
        else:
            summary_print("Next: rerun with --log-level debug for detailed diagnostics.")

    def render_runtime_failure():
        diagnostic = result.get("diagnostics", {}).get("runtime_failure")
        if not diagnostic:
            return

        def print_wrapped_lines(text, indent=4, width=100):
            prefix = " " * indent
            for raw_line in str(text).splitlines() or [""]:
                if not raw_line:
                    progress_print("")
                    continue
                wrapped = textwrap.wrap(
                    raw_line,
                    width=width,
                    initial_indent=prefix,
                    subsequent_indent=prefix,
                    break_long_words=True,
                    break_on_hyphens=False,
                )
                for line in wrapped or [prefix + raw_line]:
                    progress_print(line)

        progress_print("")
        progress_print("Runtime failure diagnostics")
        progress_print("")
        progress_print("  Result:")
        progress_print(f"    code: {diagnostic.get('code')}")
        if diagnostic.get("summary"):
            progress_print(f"    summary: {diagnostic['summary']}")

        evidence = diagnostic.get("startup_evidence") or {}
        findings = evidence.get("findings") if isinstance(evidence, dict) else []
        if findings:
            progress_print("")
            progress_print("  What happened:")
            for finding in findings:
                progress_print(f"    - {finding}")

        if diagnostic.get("underlying_error"):
            progress_print("")
            progress_print("  Underlying error:")
            print_wrapped_lines(diagnostic["underlying_error"], indent=4)

        endpoint = diagnostic.get("progress_endpoint") or result.get("diagnostics", {}).get("progress_endpoint")
        if endpoint:
            progress_print("")
            progress_print("  Connection attempt:")
            if endpoint.get("url"):
                progress_print(f"    tried: {endpoint['url']}")
            external_port = endpoint.get("external_port") or endpoint.get("host_port")
            if external_port:
                progress_print(f"    external port tested: {external_port}")
            last_bits = []
            if endpoint.get("last_status_code") is not None:
                last_bits.append(f"HTTP {endpoint['last_status_code']}")
            if endpoint.get("last_error_type"):
                last_bits.append(str(endpoint["last_error_type"]))
            if endpoint.get("last_error"):
                last_bits.append(str(endpoint["last_error"]))
            if last_bits:
                progress_print(f"    last result: {' - '.join(last_bits)}")
            if endpoint.get("mapped_ports"):
                progress_print(f"    mapped container ports: {', '.join(endpoint['mapped_ports'])}")

        if diagnostic.get("remediation"):
            progress_print("")
            progress_print("  Remediation:")
            progress_print(f"    {diagnostic['remediation']}")

        steps = diagnostic.get("suggested_steps") or []
        if steps:
            progress_print("")
            progress_print("  Suggested steps:")
            for step in steps:
                progress_print(f"    - {step}")

        if findings:
            progress_print("")
            progress_print("  Where to read next:")
            progress_print("    - instance/daemon.log in the diagnostic bundle for startup/build details.")
            progress_print("    - instance/show-instance.json in the diagnostic bundle for the raw instance status.")

    info_print(f"Starting self-test for machine {args.machine_id}.")
    client = get_client(args)

    try:
        def http_status_code(error):
            response = getattr(error, "response", None)
            return getattr(response, "status_code", None)

        def offer_search_error_summary(error):
            return {
                "status_code": http_status_code(error),
                "error": safe_error(error),
            }

        def lookup_machine_for_offer_failure(machine_id):
            try:
                rows = machines_api.show_machine(client, id=machine_id)
                if isinstance(rows, dict):
                    rows_for_status = [rows] if rows else []
                else:
                    rows_for_status = rows or []
                return {
                    "status": "visible" if rows_for_status else "empty",
                    "rows": rows_for_status,
                    "row_count": len(rows_for_status),
                }
            except requests.exceptions.HTTPError as e:
                status_code = http_status_code(e)
                status = "permission_denied" if status_code in (401, 403) else "not_found" if status_code == 404 else "error"
                return {
                    "status": status,
                    "status_code": status_code,
                    "error": safe_error(e),
                    "rows": [],
                    "row_count": 0,
                }
            except requests.exceptions.RequestException as e:
                return {
                    "status": "lookup_error",
                    "status_code": http_status_code(e),
                    "error": safe_error(e),
                    "rows": [],
                    "row_count": 0,
                }

        def compact_machine_lookup(machine_lookup):
            if not machine_lookup:
                return None
            return {
                "status": machine_lookup.get("status"),
                "status_code": machine_lookup.get("status_code"),
                "row_count": machine_lookup.get("row_count", len(machine_lookup.get("rows") or [])),
                "error": machine_lookup.get("error"),
            }

        def selected_offer_for_self_test(machine_id):
            strict_query = {
                "machine_id": {"eq": machine_id},
                "verified": {"eq": "any"},
                "rentable": {"eq": True},
                "rented": {"eq": "any"},
            }
            diagnostics = {
                "strict_offer_count": None,
                "broader_offer_count": None,
                "broader_offers": [],
                "search_error": None,
                "machine_lookup": None,
            }
            try:
                strict_offers = offers_api.search_offers(
                    client, query=strict_query, offer_type="on-demand",
                    order=[["score", "desc"]], storage=5.0, no_default=True,
                )
            except requests.exceptions.HTTPError as e:
                if http_status_code(e) in (401, 403):
                    diagnostics["search_error"] = offer_search_error_summary(e)
                    check, failure = no_offer_failure(machine_id, [], search_error=e)
                    return None, (check, failure), diagnostics
                raise
            debug_print("Captured strict offers from search_offers:", strict_offers)
            diagnostics["strict_offer_count"] = len(strict_offers or [])
            if strict_offers:
                sorted_offers = sorted(strict_offers, key=lambda x: x.get("dlperf", 0), reverse=True)
                selected = dict(sorted_offers[0])
                selected["machine_id"] = selected.get("machine_id") or machine_id
                debug_print("Selected offer found:", selected)
                return selected, None, diagnostics

            broader_query = {
                "machine_id": {"eq": machine_id},
                "verified": {"eq": "any"},
                "rentable": {"eq": "any"},
                "rented": {"eq": "any"},
            }
            try:
                broader_offers = offers_api.search_offers(
                    client, query=broader_query, offer_type="on-demand",
                    order=[["score", "desc"]], storage=5.0, no_default=True,
                )
            except requests.exceptions.HTTPError as e:
                if http_status_code(e) in (401, 403):
                    diagnostics["search_error"] = offer_search_error_summary(e)
                    check, failure = no_offer_failure(machine_id, [], search_error=e)
                    return None, (check, failure), diagnostics
                raise
            diagnostics["broader_offer_count"] = len(broader_offers or [])
            diagnostics["broader_offers"] = [
                compact_offer_metadata(dict(offer, machine_id=offer.get("machine_id", machine_id)))
                for offer in (broader_offers or [])[:5]
            ]
            machine_lookup = None
            if not broader_offers:
                machine_lookup = lookup_machine_for_offer_failure(machine_id)
                diagnostics["machine_lookup"] = compact_machine_lookup(machine_lookup)
            check, failure = no_offer_failure(machine_id, broader_offers, machine_lookup=machine_lookup)
            return None, (check, failure), diagnostics

        selected_offer, offer_failure, offer_diagnostics = selected_offer_for_self_test(args.machine_id)
        result["diagnostics"]["offer_search"] = offer_diagnostics
        if offer_failure:
            check, failure = offer_failure
            result["checks"] = [check]
            result["failure"] = failure
            result["failure_code"] = failure["code"]
            result["stage"] = "select_offer"
            result["reason"] = failure["summary"]
            info_print("Preflight failed.")
            render_preflight_failure(args.machine_id, result["checks"], failure, progress_print)
            return finish_failure()

        result["offer"] = compact_offer_metadata(selected_offer)
        checks = preflight_requirement_checks(selected_offer)
        result["checks"] = checks
        unmet_checks = failed_checks(checks)
        if unmet_checks:
            failure = requirement_failure(checks)
            result["diagnostics"]["preflight_failure"] = failure
            info_print("Preflight failed.")
            render_preflight_failure(args.machine_id, checks, failure, progress_print)
            render_preflight_advisories(args.machine_id, checks, progress_print)
            if not args.ignore_requirements:
                result["failure"] = failure
                result["failure_code"] = failure["code"]
                result["stage"] = "preflight_requirements"
                result["reason"] = failure["summary"]
                return finish_failure()
            warning_print("Continuing despite unmet requirements because --ignore-requirements is set.")
        else:
            info_print("Preflight passed.")
            progress_print(f"Machine ID {args.machine_id} meets all the requirements.")
            render_preflight_advisories(args.machine_id, checks, progress_print)
        if args.ignore_requirements:
            warning_print(ignore_requirements_warning)

        # ----- CUDA version to docker image mapping -----
        def cuda_map_to_image(cuda_version, compute_cap=None):
            """Return (image, reason). Reason explains why this image was picked."""
            docker_repo = "vastai/test"
            image_tag_prefix = "self-test-v2-cuda"

            def image_for(version):
                return f"{docker_repo}:{image_tag_prefix}-{version}"

            if isinstance(cuda_version, float):
                cuda_version = str(cuda_version)
            original_cuda = cuda_version

            # cuda-12.8 (torch 2.10) still ships sm_70 (Volta); cuda-13.0
            # (torch 2.11) never did. Neither builds sm_50/sm_60 kernels.
            # Anything pre-Volta (compute_cap < 700) must use the cuda-11.8
            # legacy image.
            if compute_cap is not None and compute_cap < 700:
                return (
                    image_for("11.8"),
                    f"compute_cap={compute_cap} below sm_70 -> forced {image_tag_prefix}-11.8",
                )

            # Volta sm_70/sm_72 hosts: cuda-12.8 wheels include sm_70 but
            # cuda-13.0 wheels never did. Cap the driver-reported CUDA version
            # at 12.8 so the map below resolves to cuda-12.8 even if the
            # operator has installed a CUDA 13 driver on a V100.
            clamped_for_volta = False
            if compute_cap is not None and compute_cap < 750:
                if float(cuda_version) > 12.8:
                    cuda_version = "12.8"
                    clamped_for_volta = True

            docker_tag_map = {
                "11.8": image_for("11.8"),
                "12.8": image_for("12.8"),
                "13.0": image_for("13.0"),
                "13.3": image_for("13.3"),
            }

            cap_hint = f"compute_cap={compute_cap}" if compute_cap is not None else "compute_cap=unknown"

            cuda_float = float(cuda_version)
            compatible_versions = sorted(float(version) for version in docker_tag_map)
            selected_version = max(
                (version for version in compatible_versions if version <= cuda_float),
                default=None,
            )

            if selected_version is not None:
                selected_version_str = f"{selected_version:.1f}"
                image = docker_tag_map[selected_version_str]
                if clamped_for_volta:
                    reason = f"{cap_hint} (Volta) + cuda_max_good={original_cuda} -> clamped to {cuda_version} -> {image}"
                elif selected_version_str == cuda_version:
                    reason = f"{cap_hint}, cuda_max_good={cuda_version} -> exact match -> {image}"
                else:
                    reason = (
                        f"{cap_hint}, cuda_max_good={original_cuda} -> "
                        f"selected newest image <= host CUDA ({selected_version_str}) -> {image}"
                    )
                return image, reason

            raise KeyError(f"No CUDA version found for {cuda_version} or any lower version")

        top_offer = selected_offer
        if not top_offer:
            progress_print(f"No valid offers found for Machine ID {args.machine_id}")
            result["reason"] = "No valid offers found."
        else:
            ask_contract_id = top_offer["id"]
            cuda_version = top_offer["cuda_max_good"]
            compute_cap = top_offer.get("compute_cap")
            image_override = args.test_image or os.environ.get("VAST_SELF_TEST_IMAGE")
            if image_override:
                docker_image = image_override
                image_reason = "custom self-test image override"
            else:
                docker_image, image_reason = cuda_map_to_image(cuda_version, compute_cap)
            result["diagnostics"]["image"] = {
                "image": docker_image,
                "reason": image_reason,
                "override": bool(image_override),
            }

            # ----- create the test instance -----
            try:
                result["phase"] = "rental"
                result["stage"] = "create_instance"
                from vastai.cli.util import parse_env
                env = parse_env("-e TZ=PDT -e XNAME=XX4 -p 5000:5000 -p 1234:1234")
                runtype = "ssh_direc ssh_proxy"
                self_test_label = f"{SELF_TEST_INSTANCE_LABEL_PREFIX}-{args.machine_id}"
                result["diagnostics"]["launch"] = {
                    "runtype": runtype,
                    "jupyter_lab": False,
                    "ports": ["5000/tcp", "1234/tcp"],
                    "label": self_test_label,
                }

                info_print("Creating temporary test instance...")
                progress_print(f"Starting test with {docker_image} ({image_reason})")
                rj = instances_api.create_instance(
                    client,
                    id=ask_contract_id,
                    image=docker_image,
                    disk=40,
                    env=env,
                    price=None,
                    label=self_test_label,
                    extra=None,
                    onstart_cmd="/verification/remote.sh",
                    login=None,
                    python_utf8=False,
                    lang_utf8=False,
                    jupyter_lab=False,
                    jupyter_dir=None,
                    force=False,
                    cancel_unavail=False,
                    template_hash=None,
                    user=None,
                    runtype=runtype,
                    args=None,
                )
                debug_print("Captured instance_info from create_instance:", rj)
            except Exception as e:
                error = safe_error(e)
                error_print(f"Error creating instance: {error}")
                set_runtime_failure(
                    make_failure(
                        INSTANCE_CREATE_FAILED,
                        stage="create_instance",
                        summary="Failed to create instance. Check the docker configuration.",
                        error=error,
                        underlying_error=error,
                    )
                )
                result["error"] = error
                return finish_failure()

            instance_id = rj.get("new_contract")
            if not instance_id:
                progress_print("Instance creation response did not contain 'new_contract'.")
                set_runtime_failure(
                    make_failure(
                        INSTANCE_CREATE_MISSING_CONTRACT,
                        stage="create_instance",
                        details=f"Create-instance response: {rj}",
                    ),
                    "Instance creation failed.",
                )
            else:
                # ----- helper: check if instance exists -----
                def instance_exist(inst_id):
                    try:
                        info = instances_api.show_instance(client, id=inst_id)
                        if not info:
                            return False
                        status = info.get('intended_status') or info.get('actual_status')
                        if status in ['destroyed', 'terminated', 'offline']:
                            return False
                        return True
                    except requests.exceptions.HTTPError as e:
                        if e.response.status_code == 404:
                            return False
                        debug_print(f"HTTPError when checking instance existence: {safe_error(e)}")
                        return False
                    except Exception as e:
                        debug_print(f"No instance found or Unexpected error checking instance existence: {safe_error(e)}")
                        return False

                # ----- helper: destroy instance silently with retries -----
                def destroy_instance_silent(inst_id, collect_logs=False):
                    if collect_logs:
                        collect_instance_logs(inst_id)
                    max_retries = 10
                    for attempt in range(1, max_retries + 1):
                        try:
                            if args.raw:
                                with open(os.devnull, 'w') as devnull, redirect_stdout(devnull), redirect_stderr(devnull):
                                    instances_api.destroy_instance(client, id=inst_id)
                            else:
                                instances_api.destroy_instance(client, id=inst_id)
                            info_print(f"Temporary test instance {inst_id} destroyed.")
                            return {"success": True}
                        except Exception as e:
                            warning_print(f"WARNING: error destroying test instance {inst_id}: {safe_error(e)}")
                        if attempt < max_retries:
                            progress_print(f"Retrying destroy in 10 seconds... (Attempt {attempt}/{max_retries})")
                            time.sleep(10)
                        else:
                            warning_print(f"WARNING: failed to destroy test instance {inst_id} after {max_retries} attempts.")
                            return {"success": False, "error": "Max retries exceeded"}

                # ----- wait for instance to start -----
                def wait_for_instance(inst_id, timeout=900, interval=10):
                    start_time = time.time()
                    debug_print("Starting wait_for_instance with ID:", inst_id)

                    while time.time() - start_time < timeout:
                        try:
                            instance_info = instances_api.show_instance(client, id=inst_id)
                            if not instance_info:
                                progress_print(f"No information returned for instance {inst_id}. Retrying...")
                                time.sleep(interval)
                                continue

                            status_msg = instance_info.get('status_msg', '')
                            status_msg_clean = status_msg.strip() if isinstance(status_msg, str) else ""
                            status_msg_lower = status_msg_clean.lower()
                            status_msg_is_error = any(
                                token in status_msg_lower
                                for token in (
                                    "error",
                                    "failed",
                                    "failure",
                                    "exception",
                                    "traceback",
                                    "oci runtime",
                                    "permission denied",
                                )
                            )
                            if status_msg_clean and status_msg_is_error:
                                diagnostic = classify_status_msg(status_msg_clean) or make_failure(
                                    DAEMON_STARTUP_FAILED,
                                    stage="startup",
                                    error=status_msg_clean,
                                    underlying_error=status_msg_clean,
                                )
                                reason = f"Instance {inst_id} encountered an error: {status_msg_clean}"
                                progress_print(reason)
                                if instance_exist(inst_id):
                                    destroy_instance_silent(inst_id, collect_logs=True)
                                    progress_print(f"Instance {inst_id} has been destroyed due to error.")
                                else:
                                    progress_print(f"Instance {inst_id} could not be destroyed or does not exist.")
                                return False, reason, diagnostic

                            actual_status = instance_info.get('actual_status', 'unknown')
                            intended_status = instance_info.get('intended_status', 'unknown')
                            if actual_status == 'offline':
                                reason = "Instance offline during testing"
                                diagnostic = make_failure(INSTANCE_OFFLINE_BEFORE_TEST, stage="startup")
                                progress_print(reason)
                                if instance_exist(inst_id):
                                    destroy_instance_silent(inst_id, collect_logs=True)
                                    progress_print(f"Instance {inst_id} has been destroyed due to being offline.")
                                else:
                                    progress_print(f"Instance {inst_id} could not be destroyed or does not exist.")
                                return False, reason, diagnostic

                            if intended_status in ('stopped', 'exited') or actual_status in ('stopped', 'exited'):
                                reason = f"Instance {inst_id} stopped before reaching running status"
                                if status_msg_clean:
                                    reason = f"{reason}: {status_msg_clean}"
                                diagnostic = classify_status_msg(status_msg_clean) if status_msg_clean else None
                                if diagnostic is None:
                                    diagnostic = make_failure(
                                        DAEMON_STARTUP_FAILED,
                                        stage="startup",
                                        summary="Instance stopped before the self-test runtime started.",
                                        details=reason,
                                        error=status_msg_clean or None,
                                        underlying_error=status_msg_clean or None,
                                    )
                                progress_print(reason)
                                if instance_exist(inst_id):
                                    destroy_instance_silent(inst_id, collect_logs=True)
                                    progress_print(f"Instance {inst_id} has been destroyed due to startup failure.")
                                else:
                                    progress_print(f"Instance {inst_id} could not be destroyed or does not exist.")
                                return False, reason, diagnostic

                            if intended_status == 'running' and actual_status == 'running':
                                debug_print(f"Instance {inst_id} is now running.")
                                return instance_info, None, None

                            progress_print(f"Instance {inst_id} status: {actual_status}... waiting for 'running' status.")
                            time.sleep(interval)

                        except Exception as e:
                            error = safe_error(e)
                            progress_print(f"Error retrieving instance info for {inst_id}: {error}. Retrying...")
                            debug_print(f"Exception details: {error}")
                            time.sleep(interval)

                    reason = f"Instance did not become running within {timeout} seconds. Verify network configuration. Use the self-test machine function in vast cli"
                    progress_print(reason)
                    return False, reason, make_failure(
                        INSTANCE_START_TIMEOUT,
                        stage="startup",
                        details=reason,
                    )

                # ----- run machine tester -----
                def run_machinetester(ip_address, port, inst_id, machine_id, delay, mapped_ports=None):
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    delay = int(delay)
                    message = ''
                    legacy_parser = LegacyProgressParser()
                    progress_url = f"https://{ip_address}:{port}/progress"
                    request_timeout = 10
                    attempt_count = 0
                    last_error_type = None
                    last_error = None
                    last_status_code = None
                    first_connection_established = False

                    def update_progress_endpoint():
                        endpoint = make_progress_endpoint_diagnostic(
                            url=progress_url,
                            public_ip=ip_address,
                            container_port=PROGRESS_CONTAINER_PORT,
                            host_port=port,
                            timeout_seconds=request_timeout,
                            attempt_count=attempt_count,
                            first_connection_established=first_connection_established,
                            last_error_type=last_error_type,
                            last_error=last_error,
                            last_status_code=last_status_code,
                            mapped_ports=mapped_ports,
                        )
                        result["diagnostics"]["progress_endpoint"] = endpoint
                        return endpoint

                    update_progress_endpoint()

                    def is_instance(iid):
                        try:
                            info = instances_api.show_instance(client, id=iid)
                            debug_print(f"is_instance(): Output from show instance: {info}")
                            if not info or not isinstance(info, dict):
                                debug_print("is_instance(): No valid instance information received.")
                                return 'unknown'
                            actual_status = info.get('actual_status', 'unknown')
                            return actual_status if actual_status in ['running', 'offline', 'exited', 'created'] else 'unknown'
                        except Exception as e:
                            debug_print(f"is_instance(): Error: {safe_error(e)}")
                            return 'unknown'

                    if delay > 0:
                        debug_print(f"Sleeping for {delay} seconds before starting tests.")
                        time.sleep(delay)

                    start_time = time.time()
                    no_response_seconds = 0
                    printed_lines = set()
                    instance_destroyed = False
                    try:
                        while time.time() - start_time < 600:
                            status = is_instance(inst_id)
                            debug_print(f"Instance {inst_id} status: {status}")

                            if status == 'offline':
                                reason = "Instance offline during testing"
                                progress_print(f"Instance {inst_id} went offline. {reason}")
                                destroy_instance_silent(inst_id, collect_logs=True)
                                instance_destroyed = True
                                return False, reason, make_failure(INSTANCE_OFFLINE_BEFORE_TEST, stage="runtime")

                            try:
                                debug_print(f"Sending GET request to {progress_url}")
                                attempt_count += 1
                                response = requests.get(progress_url, verify=False, timeout=request_timeout)
                                last_status_code = response.status_code
                                last_error_type = None
                                last_error = None

                                if response.status_code == 200 and not first_connection_established:
                                    progress_print("Successfully established HTTPS connection to the server.")
                                    first_connection_established = True

                                if response.status_code == 200:
                                    message = response.text.strip()
                                else:
                                    last_error_type = "HTTPStatus"
                                    last_error = f"HTTP {response.status_code} from progress endpoint"
                                    message = ''
                                debug_print(f"Received message: '{message}'")
                            except requests.exceptions.RequestException as e:
                                last_status_code = None
                                last_error_type = e.__class__.__name__
                                last_error = safe_error(e)
                                debug_print(f"Error making HTTPS request: {last_error}")
                                message = ''
                            update_progress_endpoint()

                            if message:
                                lines = message.split('\n')
                                new_lines = [line for line in lines if line not in printed_lines]
                                for line in new_lines:
                                    diagnostic = legacy_parser.process_line(line)
                                    if line == 'DONE':
                                        progress_print("Test completed successfully.")
                                        progress_print("Test passed.")
                                        destroy_instance_silent(inst_id)
                                        instance_destroyed = True
                                        return True, "", None
                                    elif line.startswith('ERROR'):
                                        progress_print(line)
                                        progress_print(f"Test failed with error: {line}.")
                                        destroy_instance_silent(inst_id, collect_logs=True)
                                        instance_destroyed = True
                                        return False, line, diagnostic
                                    else:
                                        progress_print(line)
                                    printed_lines.add(line)
                                no_response_seconds = 0
                            else:
                                no_response_seconds += 20
                                debug_print(f"No message received. Incremented no_response_seconds to {no_response_seconds}.")

                            if status == 'running' and no_response_seconds >= 120:
                                endpoint = update_progress_endpoint()
                                if not first_connection_established:
                                    progress_print("No response for 120s — port was never reachable.")
                                    progress_print(f"Tried: {endpoint.get('url')}")
                                    if endpoint.get("external_port"):
                                        progress_print(f"External port tested: {endpoint.get('external_port')}")
                                    if endpoint.get("last_error_type") or endpoint.get("last_status_code") is not None:
                                        last_result = endpoint.get("last_error_type") or f"HTTP {endpoint.get('last_status_code')}"
                                        if endpoint.get("last_error"):
                                            last_result = f"{last_result}: {endpoint.get('last_error')}"
                                        progress_print(f"Last result: {last_result}")
                                    progress_print("Possible causes:")
                                    progress_print("  1. TCP firewall/NAT forwarding is blocking the mapped public port")
                                    progress_print("  2. Container did not start or did not bind the progress server")
                                    progress_print("  3. NAT loopback/hairpinning may fail when testing from the same LAN as the host")
                                    progress_print(f"  4. direct_port_count below the 3 ports/GPU minimum - check with: vastai search offers 'machine_id={machine_id} rentable=any rented=any'")
                                    return_reason = "Port never reachable within 120 seconds"
                                    diagnostic = make_failure(
                                        PROGRESS_ENDPOINT_UNREACHABLE,
                                        stage="runtime_connect",
                                        details=return_reason,
                                        progress_endpoint=endpoint,
                                    )
                                elif endpoint.get("last_status_code") == 200 and not endpoint.get("last_error_type"):
                                    progress_print("Progress endpoint was reachable but returned no output for 120s.")
                                    progress_print(f"Tried: {endpoint.get('url')}")
                                    if endpoint.get("external_port"):
                                        progress_print(f"External port tested: {endpoint.get('external_port')}")
                                    progress_print("Possible causes:")
                                    progress_print("  1. Runtime script stalled before writing progress")
                                    progress_print("  2. Container process is alive but the test worker is hung")
                                    progress_print("  3. Host stall, GPU hang, or slow I/O prevented progress updates")
                                    return_reason = "Progress endpoint returned no output for 120 seconds"
                                    diagnostic = make_failure(
                                        PROGRESS_EMPTY_TIMEOUT,
                                        stage="runtime_progress",
                                        details=return_reason,
                                        progress_endpoint=endpoint,
                                    )
                                else:
                                    progress_print("Connection lost after initial success — instance may have crashed.")
                                    progress_print(f"Tried: {endpoint.get('url')}")
                                    if endpoint.get("external_port"):
                                        progress_print(f"External port tested: {endpoint.get('external_port')}")
                                    if endpoint.get("last_error_type") or endpoint.get("last_status_code") is not None:
                                        last_result = endpoint.get("last_error_type") or f"HTTP {endpoint.get('last_status_code')}"
                                        if endpoint.get("last_error"):
                                            last_result = f"{last_result}: {endpoint.get('last_error')}"
                                        progress_print(f"Last result: {last_result}")
                                    progress_print("Possible causes:")
                                    progress_print("  1. Container crash, OOM, or runtime process exit — check docker logs")
                                    progress_print("  2. GPU errors or reset — check dmesg for Xid errors")
                                    progress_print("  3. Host stall or network loss after the progress server started")
                                    return_reason = "Connection lost after 120 seconds — possible crash during stress test"
                                    diagnostic = make_failure(
                                        PROGRESS_ENDPOINT_LOST,
                                        stage="runtime_connect",
                                        details=return_reason,
                                        progress_endpoint=endpoint,
                                    )
                                destroy_instance_silent(inst_id, collect_logs=True)
                                instance_destroyed = True
                                return False, return_reason, diagnostic

                            debug_print("Waiting for 20 seconds before the next check.")
                            time.sleep(20)

                        debug_print(f"Time limit reached. Destroying instance {inst_id}.")
                        return False, "Test did not complete within the time limit", make_failure(
                            RUNTIME_TEST_TIMEOUT,
                            stage="runtime",
                        )
                    finally:
                        if not instance_destroyed and inst_id and instance_exist(inst_id):
                            destroy_instance_silent(inst_id, collect_logs=True)
                        progress_print(f"Machine: {machine_id} Done with testing remote.py results {message}")
                        warnings.simplefilter('default')

                # ----- main orchestration: wait then test -----
                result["phase"] = "wait"
                result["stage"] = "wait_for_instance"
                instance_info, wait_reason, wait_diagnostic = wait_for_instance(instance_id)
                if not instance_info:
                    set_runtime_failure(wait_diagnostic, wait_reason)
                else:
                    ip_address = instance_info.get("public_ipaddr")
                    if not ip_address:
                        set_runtime_failure(
                            make_failure(MISSING_PUBLIC_IP, stage="instance_network"),
                            "Failed to retrieve public IP address.",
                        )
                    else:
                        all_ports = instance_info.get("ports", {})
                        port_mappings = all_ports.get("5000/tcp", [])
                        port = port_mappings[0].get("HostPort") if port_mappings else None
                        if not port:
                            endpoint = make_progress_endpoint_diagnostic(
                                public_ip=ip_address,
                                container_port=PROGRESS_CONTAINER_PORT,
                                host_port=None,
                                timeout_seconds=10,
                                mapped_ports=all_ports,
                            )
                            result["diagnostics"]["progress_endpoint"] = endpoint
                            progress_print(f"Port 5000/tcp not found in mapped ports. Available ports: {list(all_ports.keys())}")
                            progress_print("Possible causes:")
                            progress_print("  1. The instance launch did not map the self-test progress port")
                            progress_print(f"  2. direct_port_count below the 3 ports/GPU minimum - check with: vastai search offers 'machine_id={args.machine_id} rentable=any rented=any'")
                            progress_print("  3. Container is not exposing port 5000/tcp")
                            set_runtime_failure(
                                make_failure(
                                    PROGRESS_PORT_NOT_MAPPED,
                                    stage="instance_network",
                                    details=f"Available ports: {list(all_ports.keys())}",
                                    progress_endpoint=endpoint,
                                ),
                                "Failed to retrieve mapped port.",
                            )
                        else:
                            delay = "15"
                            result["phase"] = "test"
                            result["stage"] = "run_machinetester"
                            info_print("Running self-test...")
                            success, reason, runtime_diagnostic = run_machinetester(
                                ip_address, port, instance_id, args.machine_id, delay, mapped_ports=all_ports,
                            )
                            result["success"] = success
                            result["reason"] = reason
                            if success:
                                result["phase"] = "complete"
                                result["stage"] = "complete"
                            else:
                                set_runtime_failure(runtime_diagnostic, reason)

    except KeyboardInterrupt:
        result["success"] = False
        set_runtime_failure(
            make_failure(INTERRUPTED, stage=result.get("stage")),
            "Interrupted by user (Ctrl+C)",
        )
        result["error"] = result["reason"]
        warning_print("\nInterrupted - cleaning up test instance...")
    except Exception as e:
        error = safe_error(e)
        result["success"] = False
        result["reason"] = error
        result["failure_code"] = "unexpected_error"
        result["failure"] = {
            "code": "unexpected_error",
            "summary": error,
            "remediation": "Retry with --debugging and inspect the error details.",
        }
        result["error"] = error

    finally:
        # Always attempt to destroy the test instance, including on Ctrl+C.
        # KeyboardInterrupt is BaseException (not Exception) so it skips the
        # typed except above and lands here. Surface failures loudly: a
        # silently-leaked instance keeps billing the host.
        if instance_id:
            try:
                info = instances_api.show_instance(client, id=instance_id)
                if not info:
                    debug_print(f"Test instance {instance_id} already gone during cleanup.")
                    info = {}
                status = (info or {}).get('intended_status') or (info or {}).get('actual_status')
                if info and status not in ('destroyed', 'terminated', 'offline'):
                    if not result.get("success"):
                        collect_instance_logs(instance_id)
                    info_print(f"Cleaning up temporary test instance {instance_id} (status: {status})...")
                    instances_api.destroy_instance(client, id=instance_id)
                    info_print(f"Temporary test instance {instance_id} destroyed.")
            except KeyboardInterrupt:
                warning_print(
                    f"\nSecond interrupt during cleanup - instance {instance_id} may still be running.\n"
                    f"  Destroy it manually: vastai destroy instance {instance_id}"
                )
                raise
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
                    debug_print(f"Test instance {instance_id} already gone during cleanup.")
                else:
                    warning_print(
                        f"WARNING: failed to destroy test instance {instance_id}: {safe_error(e)}\n"
                        f"  Destroy it manually: vastai destroy instance {instance_id}"
                    )
            except Exception as e:
                warning_print(
                    f"WARNING: failed to destroy test instance {instance_id}: {safe_error(e)}\n"
                    f"  Destroy it manually: vastai destroy instance {instance_id}"
                )

    if args.raw:
        if not result.get("success"):
            ensure_support_bundle()
        return result
    else:
        if result.get("warning"):
            warning_print(result["warning"])
        if result["success"]:
            render_final_summary()
            sys.exit(0)
        render_runtime_failure()
        bundle = ensure_support_bundle()
        render_final_summary(bundle=bundle)
        sys.exit(1)
