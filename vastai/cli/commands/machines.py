"""CLI commands for managing host machines."""

import json
import os
import re
import sys
import time
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
    PROGRESS_ENDPOINT_LOST,
    PROGRESS_ENDPOINT_UNREACHABLE,
    PROGRESS_PORT_NOT_MAPPED,
    RUNTIME_TEST_TIMEOUT,
    classify_status_msg,
    make_failure,
)


parser = _get_parser()


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
# self-test machine
# ---------------------------------------------------------------------------

@parser.command(
    argument("machine_id", help="Machine ID", type=str),
    argument("--debugging", action="store_true", help="Enable debugging output"),
    argument("--ignore-requirements", action="store_true", help="Ignore the minimum system requirements and run the self test regardless"),
    argument("--test-image", help="Use a custom self-test image for testing custom self-test images. Overrides VAST_SELF_TEST_IMAGE and CUDA mapping.", type=str),
    usage="vastai self-test machine <machine_id> [--debugging] [--ignore-requirements] [--test-image IMAGE]",
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
    ignore_requirements_warning = (
        "WARNING: --ignore-requirements is set. Requirement checks are skipped as a "
        "pass/fail gate, and passing this self-test does not qualify this machine for verification."
    )

    if not hasattr(args, 'debugging'):
        args.debugging = False
    if not hasattr(args, 'test_image'):
        args.test_image = None
    if getattr(args, "ignore_requirements", False):
        result["warning"] = ignore_requirements_warning

    def progress_print(*args_to_print):
        if not args.raw:
            print(*args_to_print)

    def debug_print(*args_to_print):
        if args.debugging and not args.raw:
            print(*args_to_print)

    def finish_failure():
        if args.raw:
            return result
        if result.get("warning"):
            print(result["warning"])
        render_runtime_failure()
        print(f"Test failed: {result['reason']}")
        sys.exit(1)

    def set_runtime_failure(diagnostic, fallback_reason=None):
        result["failure"] = diagnostic
        result["failure_code"] = diagnostic["code"]
        result["stage"] = diagnostic.get("stage") or result.get("stage")
        result["reason"] = fallback_reason or diagnostic.get("summary") or ""
        result["diagnostics"]["runtime_failure"] = diagnostic

    def safe_error(error):
        return re.sub(r"([?&]api_key=)[^&\s]+", r"\1REDACTED", str(error))

    def render_runtime_failure():
        diagnostic = result.get("diagnostics", {}).get("runtime_failure")
        if not diagnostic:
            return
        print("Runtime failure diagnostics:")
        print(f"- code: {diagnostic.get('code')}")
        if diagnostic.get("summary"):
            print(f"- summary: {diagnostic['summary']}")
        if diagnostic.get("underlying_error"):
            print(f"- underlying error: {diagnostic['underlying_error']}")
        if diagnostic.get("remediation"):
            print(f"- remediation: {diagnostic['remediation']}")
        steps = diagnostic.get("suggested_steps") or []
        if steps:
            print("- suggested steps:")
            for step in steps:
                print(f"  - {step}")

    client = get_client(args)

    try:
        def selected_offer_for_self_test(machine_id):
            strict_query = {
                "machine_id": {"eq": machine_id},
                "verified": {"eq": "any"},
                "rentable": {"eq": True},
                "rented": {"eq": "any"},
            }
            strict_offers = offers_api.search_offers(
                client, query=strict_query, offer_type="on-demand",
                order=[["score", "desc"]], storage=5.0, no_default=True,
            )
            debug_print("Captured strict offers from search_offers:", strict_offers)
            diagnostics = {
                "strict_offer_count": len(strict_offers or []),
                "broader_offer_count": None,
                "broader_offers": [],
            }
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
            broader_offers = offers_api.search_offers(
                client, query=broader_query, offer_type="on-demand",
                order=[["score", "desc"]], storage=5.0, no_default=True,
            )
            diagnostics["broader_offer_count"] = len(broader_offers or [])
            diagnostics["broader_offers"] = [
                compact_offer_metadata(dict(offer, machine_id=offer.get("machine_id", machine_id)))
                for offer in (broader_offers or [])[:5]
            ]
            check, failure = no_offer_failure(machine_id, broader_offers)
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
            render_preflight_failure(args.machine_id, result["checks"], failure, progress_print)
            return finish_failure()

        result["offer"] = compact_offer_metadata(selected_offer)
        checks = preflight_requirement_checks(selected_offer)
        result["checks"] = checks
        unmet_checks = failed_checks(checks)
        if unmet_checks:
            failure = requirement_failure(checks)
            result["failure"] = failure
            result["failure_code"] = failure["code"]
            result["stage"] = "preflight_requirements"
            result["reason"] = failure["summary"]
            render_preflight_failure(args.machine_id, checks, failure, progress_print)
            if not args.ignore_requirements:
                return finish_failure()
            progress_print("Continuing despite unmet requirements because --ignore-requirements is set.")
        else:
            progress_print(f"Machine ID {args.machine_id} meets all the requirements.")
        if args.ignore_requirements:
            progress_print(ignore_requirements_warning)

        # ----- CUDA version to docker image mapping -----
        def cuda_map_to_image(cuda_version, compute_cap=None):
            """Return (image, reason). Reason explains why this image was picked."""
            docker_repo = "vastai/test"
            if isinstance(cuda_version, float):
                cuda_version = str(cuda_version)
            original_cuda = cuda_version

            # cuda-12.8 (torch 2.10) still ships sm_70 (Volta); cuda-13.0
            # (torch 2.11) never did. Neither builds sm_50/sm_60 kernels.
            # Anything pre-Volta (compute_cap < 700) must use the cuda-11.8
            # legacy image.
            if compute_cap is not None and compute_cap < 700:
                return (
                    f"{docker_repo}:self-test-cuda-11.8",
                    f"compute_cap={compute_cap} below sm_70 → forced cuda-11.8",
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
                "11.8": "cuda-11.8",
                "12.8": "cuda-12.8",
                "13.0": "cuda-13.0",
            }

            cap_hint = f"compute_cap={compute_cap}" if compute_cap is not None else "compute_cap=unknown"

            if cuda_version in docker_tag_map:
                tag = docker_tag_map[cuda_version]
                if clamped_for_volta:
                    reason = f"{cap_hint} (Volta) + cuda_max_good={original_cuda} → clamped to {cuda_version} → {tag}"
                else:
                    reason = f"{cap_hint}, cuda_max_good={cuda_version} → exact match → {tag}"
                return f"{docker_repo}:self-test-{tag}", reason

            cuda_float = float(cuda_version)
            next_version = round(cuda_float - 0.1, 1)
            while next_version >= min(float(v) for v in docker_tag_map.keys()):
                next_version_str = str(next_version)
                if next_version_str in docker_tag_map:
                    tag = docker_tag_map[next_version_str]
                    reason = (
                        f"{cap_hint}, cuda_max_good={original_cuda} → "
                        f"stepped down to {next_version_str} → {tag}"
                    )
                    return f"{docker_repo}:self-test-{tag}", reason
                next_version = round(next_version - 0.1, 1)

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

                progress_print(f"Starting test with {docker_image} ({image_reason})")
                rj = instances_api.create_instance(
                    client,
                    id=ask_contract_id,
                    image=docker_image,
                    disk=40,
                    env=env,
                    price=None,
                    label=None,
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
                    runtype="jupyter_direc ssh_direc ssh_proxy",
                    args=None,
                )
                debug_print("Captured instance_info from create_instance:", rj)
            except Exception as e:
                error = safe_error(e)
                progress_print(f"Error creating instance: {error}")
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
                def destroy_instance_silent(inst_id):
                    max_retries = 10
                    for attempt in range(1, max_retries + 1):
                        try:
                            if args.raw:
                                with open(os.devnull, 'w') as devnull, redirect_stdout(devnull), redirect_stderr(devnull):
                                    instances_api.destroy_instance(client, id=inst_id)
                            else:
                                instances_api.destroy_instance(client, id=inst_id)
                            if not args.raw:
                                print(f"Instance {inst_id} destroyed successfully on attempt {attempt}.")
                            return {"success": True}
                        except Exception as e:
                            if not args.raw:
                                print(f"Error destroying instance {inst_id}: {safe_error(e)}")
                        if attempt < max_retries:
                            if not args.raw:
                                print(f"Retrying in 10 seconds... (Attempt {attempt}/{max_retries})")
                            time.sleep(10)
                        else:
                            if not args.raw:
                                print(f"Failed to destroy instance {inst_id} after {max_retries} attempts.")
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
                            if status_msg and 'Error' in status_msg:
                                diagnostic = classify_status_msg(status_msg) or make_failure(
                                    DAEMON_STARTUP_FAILED,
                                    stage="startup",
                                    error=status_msg.strip(),
                                    underlying_error=status_msg.strip(),
                                )
                                reason = f"Instance {inst_id} encountered an error: {status_msg.strip()}"
                                progress_print(reason)
                                if instance_exist(inst_id):
                                    destroy_instance_silent(inst_id)
                                    progress_print(f"Instance {inst_id} has been destroyed due to error.")
                                else:
                                    progress_print(f"Instance {inst_id} could not be destroyed or does not exist.")
                                return False, reason, diagnostic

                            actual_status = instance_info.get('actual_status', 'unknown')
                            if actual_status == 'offline':
                                reason = "Instance offline during testing"
                                diagnostic = make_failure(INSTANCE_OFFLINE_BEFORE_TEST, stage="startup")
                                progress_print(reason)
                                if instance_exist(inst_id):
                                    destroy_instance_silent(inst_id)
                                    progress_print(f"Instance {inst_id} has been destroyed due to being offline.")
                                else:
                                    progress_print(f"Instance {inst_id} could not be destroyed or does not exist.")
                                return False, reason, diagnostic

                            if instance_info.get('intended_status') == 'running' and actual_status == 'running':
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
                def run_machinetester(ip_address, port, inst_id, machine_id, delay):
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    delay = int(delay)
                    message = ''
                    legacy_parser = LegacyProgressParser()

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
                    first_connection_established = False
                    instance_destroyed = False
                    try:
                        while time.time() - start_time < 600:
                            status = is_instance(inst_id)
                            debug_print(f"Instance {inst_id} status: {status}")

                            if status == 'offline':
                                reason = "Instance offline during testing"
                                progress_print(f"Instance {inst_id} went offline. {reason}")
                                destroy_instance_silent(inst_id)
                                instance_destroyed = True
                                return False, reason, make_failure(INSTANCE_OFFLINE_BEFORE_TEST, stage="runtime")

                            try:
                                debug_print(f"Sending GET request to https://{ip_address}:{port}/progress")
                                response = requests.get(f'https://{ip_address}:{port}/progress', verify=False, timeout=10)

                                if response.status_code == 200 and not first_connection_established:
                                    progress_print("Successfully established HTTPS connection to the server.")
                                    first_connection_established = True

                                message = response.text.strip()
                                debug_print(f"Received message: '{message}'")
                            except requests.exceptions.RequestException as e:
                                debug_print(f"Error making HTTPS request: {safe_error(e)}")
                                message = ''

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
                                        destroy_instance_silent(inst_id)
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
                                if not first_connection_established:
                                    progress_print("No response for 120s — port was never reachable.")
                                    progress_print("Possible causes:")
                                    progress_print("  1. Port not accessible from outside — check firewall and direct_port_count")
                                    progress_print("  2. Container crashed on startup — check docker logs")
                                    progress_print(f"  3. direct_port_count too low - check with: vastai search offers 'machine_id={machine_id} rentable=any rented=any'")
                                    return_reason = "Port never reachable within 120 seconds"
                                    diagnostic = make_failure(
                                        PROGRESS_ENDPOINT_UNREACHABLE,
                                        stage="runtime_connect",
                                        details=return_reason,
                                    )
                                else:
                                    progress_print("Connection lost after initial success — instance may have crashed.")
                                    progress_print("Possible causes:")
                                    progress_print("  1. Out of RAM/VRAM — check docker logs")
                                    progress_print("  2. GPU errors — check dmesg for Xid errors")
                                    progress_print("  3. Try running individual tests to isolate the failure")
                                    return_reason = "Connection lost after 120 seconds — possible crash during stress test"
                                    diagnostic = make_failure(
                                        PROGRESS_ENDPOINT_LOST,
                                        stage="runtime_connect",
                                        details=return_reason,
                                    )
                                destroy_instance_silent(inst_id)
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
                            destroy_instance_silent(inst_id)
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
                            progress_print(f"Port 5000/tcp not found in mapped ports. Available ports: {list(all_ports.keys())}")
                            progress_print("Possible causes:")
                            progress_print("  1. Firewall blocking the port")
                            progress_print(f"  2. direct_port_count too low - check with: vastai search offers 'machine_id={args.machine_id} rentable=any rented=any'")
                            progress_print("  3. Container is not exposing port 5000")
                            set_runtime_failure(
                                make_failure(
                                    PROGRESS_PORT_NOT_MAPPED,
                                    stage="instance_network",
                                    details=f"Available ports: {list(all_ports.keys())}",
                                ),
                                "Failed to retrieve mapped port.",
                            )
                        else:
                            delay = "15"
                            result["phase"] = "test"
                            result["stage"] = "run_machinetester"
                            success, reason, runtime_diagnostic = run_machinetester(
                                ip_address, port, instance_id, args.machine_id, delay,
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
        progress_print("\nInterrupted — cleaning up test instance...")
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
                    progress_print(f"Destroying test instance {instance_id} (status: {status})...")
                    instances_api.destroy_instance(client, id=instance_id)
                    progress_print(f"Test instance {instance_id} destroyed.")
            except KeyboardInterrupt:
                progress_print(
                    f"\nSecond interrupt during cleanup — instance {instance_id} may still be running.\n"
                    f"  Destroy it manually: vastai destroy instance {instance_id}"
                )
                raise
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
                    debug_print(f"Test instance {instance_id} already gone during cleanup.")
                else:
                    progress_print(
                        f"WARNING: failed to destroy test instance {instance_id}: {safe_error(e)}\n"
                        f"  Destroy it manually: vastai destroy instance {instance_id}"
                    )
            except Exception as e:
                progress_print(
                    f"WARNING: failed to destroy test instance {instance_id}: {safe_error(e)}\n"
                    f"  Destroy it manually: vastai destroy instance {instance_id}"
                )

    if args.raw:
        return result
    else:
        if result.get("warning"):
            print(result["warning"])
        if result["success"]:
            print("Test completed successfully.")
            sys.exit(0)
        else:
            render_runtime_failure()
            print(f"Test failed: {result['reason']}")
            sys.exit(1)
