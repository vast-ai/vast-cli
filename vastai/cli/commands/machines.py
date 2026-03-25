"""CLI commands for managing host machines."""

import json
import os
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
    argument("-ids", help="comma separated string of machine_ids for which to get maintenance information", type=str),
    argument("-q", "--quiet", action="store_true", help="only display numeric ids of the machines in maintenance"),
    usage="\nvastai show maints -ids 'machine_id_1' [OPTIONS]\nvastai show maints -ids 'machine_id_1, machine_id_2' [OPTIONS]",
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
    argument("-g", "--price_gpu", help="per gpu rental price in $/hour", type=float),
    argument("-s", "--price_disk", help="storage price in $/GB/month", type=float),
    argument("-u", "--price_inetu", help="price for internet upload bandwidth in $/GB", type=float),
    argument("-d", "--price_inetd", help="price for internet download bandwidth in $/GB", type=float),
    argument("-b", "--price_min_bid", help="per gpu minimum bid price floor in $/hour", type=float),
    argument("-r", "--discount_rate", help="Max long term prepay discount rate fraction, default: 0.4", type=float),
    argument("-m", "--min_chunk", help="minimum amount of gpus", type=int),
    argument("-e", "--end_date", help="contract offer expiration date", type=str),
    argument("-l", "--duration", help="Updates end_date daily to be duration from current date"),
    argument("-v", "--vol_size", help="Size for volume contract offer", type=int),
    argument("-z", "--vol_price", help="Price for disk on volume contract offer", type=float),
    usage="vastai list machine ID [options]",
    help="[Host] list a machine for rent",
)
def list__machine(args):
    """List a machine for rent."""
    return list_machine_impl(args, args.id)


@parser.command(
    argument("ids", help="ids of machines to list", type=int, nargs='+'),
    argument("-g", "--price_gpu", help="per gpu on-demand rental price in $/hour", type=float),
    argument("-s", "--price_disk", help="storage price in $/GB/month", type=float),
    argument("-u", "--price_inetu", help="price for internet upload bandwidth in $/GB", type=float),
    argument("-d", "--price_inetd", help="price for internet download bandwidth in $/GB", type=float),
    argument("-b", "--price_min_bid", help="per gpu minimum bid price floor in $/hour", type=float),
    argument("-r", "--discount_rate", help="Max long term prepay discount rate fraction, default: 0.4", type=float),
    argument("-m", "--min_chunk", help="minimum amount of gpus", type=int),
    argument("-e", "--end_date", help="contract offer expiration date", type=str),
    argument("-l", "--duration", help="Updates end_date daily to be duration from current date"),
    argument("-v", "--vol_size", help="Size for volume contract offer", type=int),
    argument("-z", "--vol_price", help="Price for disk on volume contract offer", type=float),
    usage="vastai list machines IDs [options]",
    help="[Host] list machines for rent",
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
    help="[Host] Delete machine if not in use by clients",
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
)
def cleanup__machine(args):
    """Remove expired storage instances from a machine."""
    client = get_client(args)
    rj = machines_api.cleanup_machine(client, id=args.id)

    if rj.get("success"):
        print(json.dumps(rj, indent=1))
    else:
        if args.raw:
            return rj
        else:
            print(rj.get("msg", rj))


# ---------------------------------------------------------------------------
# defrag machines
# ---------------------------------------------------------------------------

@parser.command(
    argument("IDs", help="ids of machines", type=int, nargs='+'),
    usage="vastai defragment machines IDs",
    help="[Host] Defragment machines",
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
    usage="vastai set defjob id [OPTIONS]",
    help="[Host] Create default jobs for a machine",
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
    usage="vastai schedule maintenance id [--sdate START_DATE --duration DURATION]",
    help="[Host] Schedule upcoming maint window",
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
    argument("machines", help="ids of machines to add disk to", type=int, nargs='+'),
    argument("mount_point", help="mount path of disk to add", type=str),
    argument("-d", "--disk_id", help="id of network disk to attach", type=int, nargs='?'),
    usage="vastai add network-disk MACHINES MOUNT_PATH [options]",
    help="[Host] Add Network Disk to Physical Cluster.",
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
    argument("--ignore-requirements", action="store_true", help="Ignore minimum system requirements"),
    usage="vastai self-test machine <machine_id> [--debugging] [--ignore-requirements]",
    help="[Host] Perform a self-test on the specified machine",
    epilog=deindent("""
        This command tests if a machine meets specific requirements and
        runs a series of tests to ensure it's functioning correctly.

        Examples:
         vastai self-test machine 12345
         vastai self-test machine 12345 --debugging
         vastai self-test machine 12345 --ignore-requirements
    """),
)
def self_test__machine(args):
    """
    Performs a self-test on the specified machine to verify its compliance with
    required specifications and functionality.
    """
    instance_id = None
    result = {"success": False, "reason": ""}

    if not hasattr(args, 'debugging'):
        args.debugging = False

    def progress_print(*args_to_print):
        if not args.raw:
            print(*args_to_print)

    def debug_print(*args_to_print):
        if args.debugging and not args.raw:
            print(*args_to_print)

    def safe_float(value):
        if value is None:
            return 0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0

    client = get_client(args)

    try:
        # ----- check requirements -----
        def check_requirements(machine_id):
            unmet_reasons = []
            query = {
                "machine_id": {"eq": machine_id},
                "verified": {"eq": "any"},
                "rentable": {"eq": True},
                "rented": {"eq": "any"},
            }
            try:
                offers = offers_api.search_offers(
                    client, query=query, offer_type="on-demand",
                    order=[["score", "desc"]], storage=5.0, no_default=True,
                )
                debug_print("Captured offers from search_offers:", offers)

                if not offers:
                    unmet_reasons.append(f"Machine ID {machine_id} not found or not rentable.")
                    progress_print(f"Machine ID {machine_id} not found or not rentable.")
                    return False, unmet_reasons

                sorted_offers = sorted(offers, key=lambda x: x.get('dlperf', 0), reverse=True)
                top_offer = sorted_offers[0]
                debug_print("Top offer found:", top_offer)

                if safe_float(top_offer.get('cuda_max_good')) < 11.8:
                    unmet_reasons.append("CUDA version < 11.8")
                if safe_float(top_offer.get('reliability')) <= 0.90:
                    unmet_reasons.append("Reliability <= 0.90")
                if safe_float(top_offer.get('direct_port_count')) <= 3:
                    unmet_reasons.append("Direct port count <= 3")
                if safe_float(top_offer.get('pcie_bw')) <= 2.85:
                    unmet_reasons.append("PCIe bandwidth <= 2.85")
                if safe_float(top_offer.get('inet_down')) < 500:
                    unmet_reasons.append("Download speed < 500 Mb/s")
                if safe_float(top_offer.get('inet_up')) < 500:
                    unmet_reasons.append("Upload speed < 500 Mb/s")
                if safe_float(top_offer.get('gpu_ram')) <= 7:
                    unmet_reasons.append("GPU RAM <= 7 GB")

                gpu_total_ram = safe_float(top_offer.get('gpu_total_ram'))
                cpu_ram = safe_float(top_offer.get('cpu_ram'))
                if cpu_ram < 0.95 * gpu_total_ram:
                    unmet_reasons.append("System RAM is less than total VRAM.")
                debug_print(f"CPU RAM: {cpu_ram} MB")
                debug_print(f"Total GPU RAM: {gpu_total_ram} MB")

                cpu_cores = int(safe_float(top_offer.get('cpu_cores')))
                num_gpus = int(safe_float(top_offer.get('num_gpus')))
                if cpu_cores < 2 * num_gpus:
                    unmet_reasons.append("Number of CPU cores is less than twice the number of GPUs.")
                debug_print(f"CPU Cores: {cpu_cores}")
                debug_print(f"Number of GPUs: {num_gpus}")

                if unmet_reasons:
                    progress_print(f"Machine ID {machine_id} does not meet the requirements:")
                    for reason in unmet_reasons:
                        progress_print(f"- {reason}")
                    return False, unmet_reasons
                else:
                    progress_print(f"Machine ID {machine_id} meets all the requirements.")
                    return True, []

            except Exception as e:
                progress_print(f"An unexpected error occurred: {str(e)}")
                debug_print(f"Exception details: {e}")
                return False, [f"Unexpected error: {str(e)}"]

        meets_requirements, unmet_reasons = check_requirements(args.machine_id)
        if not meets_requirements and not args.ignore_requirements:
            progress_print(f"Machine ID {args.machine_id} does not meet the following requirements:")
            for reason in unmet_reasons:
                progress_print(f"- {reason}")
            result["reason"] = "; ".join(unmet_reasons)
            return result
        if not meets_requirements and args.ignore_requirements:
            progress_print(f"Machine ID {args.machine_id} does not meet the following requirements:")
            for reason in unmet_reasons:
                progress_print(f"- {reason}")
            progress_print("Continuing despite unmet requirements because --ignore-requirements is set.")

        # ----- CUDA version to docker image mapping -----
        def cuda_map_to_image(cuda_version):
            docker_repo = "vastai/test"
            if isinstance(cuda_version, float):
                cuda_version = str(cuda_version)

            docker_tag_map = {
                "11.8": "cu118",
                "12.1": "cu121",
                "12.4": "cu124",
                "12.6": "cu126",
                "12.8": "cu128",
            }

            if cuda_version in docker_tag_map:
                return f"{docker_repo}:self-test-{docker_tag_map[cuda_version]}"

            cuda_float = float(cuda_version)
            next_version = round(cuda_float - 0.1, 1)
            while next_version >= min(float(v) for v in docker_tag_map.keys()):
                next_version_str = str(next_version)
                if next_version_str in docker_tag_map:
                    return f"{docker_repo}:self-test-{docker_tag_map[next_version_str]}"
                next_version = round(next_version - 0.1, 1)

            raise KeyError(f"No CUDA version found for {cuda_version} or any lower version")

        # ----- search offers and get top -----
        def search_offers_and_get_top(machine_id):
            query = {
                "machine_id": {"eq": machine_id},
                "verified": {"eq": "any"},
                "rentable": {"eq": True},
                "rented": {"eq": "any"},
            }
            offers = offers_api.search_offers(
                client, query=query, offer_type="on-demand",
                order=[["score", "desc"]], storage=5.0, no_default=True,
            )
            if not offers:
                progress_print(f"Machine ID {machine_id} not found or not rentable.")
                return None
            sorted_offers = sorted(offers, key=lambda x: x.get("dlperf", 0), reverse=True)
            return sorted_offers[0] if sorted_offers else None

        top_offer = search_offers_and_get_top(args.machine_id)
        if not top_offer:
            progress_print(f"No valid offers found for Machine ID {args.machine_id}")
            result["reason"] = "No valid offers found."
        else:
            ask_contract_id = top_offer["id"]
            cuda_version = top_offer["cuda_max_good"]
            docker_image = cuda_map_to_image(cuda_version)

            # ----- create the test instance -----
            try:
                from vastai.cli.util import parse_env
                env = parse_env("-e TZ=PDT -e XNAME=XX4 -p 5000:5000 -p 1234:1234")

                progress_print(f"Starting test with {docker_image}")
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
                progress_print(f"Error creating instance: {e}")
                result["reason"] = "Failed to create instance. Check the docker configuration. Use the self-test machine function in vast cli"
                return result

            instance_id = rj.get("new_contract")
            if not instance_id:
                progress_print("Instance creation response did not contain 'new_contract'.")
                result["reason"] = "Instance creation failed."
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
                        debug_print(f"HTTPError when checking instance existence: {e}")
                        return False
                    except Exception as e:
                        debug_print(f"No instance found or Unexpected error checking instance existence: {e}")
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
                                print(f"Error destroying instance {inst_id}: {e}")
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
                                reason = f"Instance {inst_id} encountered an error: {status_msg.strip()}"
                                progress_print(reason)
                                if instance_exist(inst_id):
                                    destroy_instance_silent(inst_id)
                                    progress_print(f"Instance {inst_id} has been destroyed due to error.")
                                else:
                                    progress_print(f"Instance {inst_id} could not be destroyed or does not exist.")
                                return False, reason

                            actual_status = instance_info.get('actual_status', 'unknown')
                            if actual_status == 'offline':
                                reason = "Instance offline during testing"
                                progress_print(reason)
                                if instance_exist(inst_id):
                                    destroy_instance_silent(inst_id)
                                    progress_print(f"Instance {inst_id} has been destroyed due to being offline.")
                                else:
                                    progress_print(f"Instance {inst_id} could not be destroyed or does not exist.")
                                return False, reason

                            if instance_info.get('intended_status') == 'running' and actual_status == 'running':
                                debug_print(f"Instance {inst_id} is now running.")
                                return instance_info, None

                            progress_print(f"Instance {inst_id} status: {actual_status}... waiting for 'running' status.")
                            time.sleep(interval)

                        except Exception as e:
                            progress_print(f"Error retrieving instance info for {inst_id}: {e}. Retrying...")
                            debug_print(f"Exception details: {str(e)}")
                            time.sleep(interval)

                    reason = f"Instance did not become running within {timeout} seconds. Verify network configuration. Use the self-test machine function in vast cli"
                    progress_print(reason)
                    return False, reason

                # ----- run machine tester -----
                def run_machinetester(ip_address, port, inst_id, machine_id, delay):
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    delay = int(delay)
                    message = ''

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
                            debug_print(f"is_instance(): Error: {e}")
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
                                return False, reason

                            try:
                                debug_print(f"Sending GET request to https://{ip_address}:{port}/progress")
                                response = requests.get(f'https://{ip_address}:{port}/progress', verify=False, timeout=10)

                                if response.status_code == 200 and not first_connection_established:
                                    progress_print("Successfully established HTTPS connection to the server.")
                                    first_connection_established = True

                                message = response.text.strip()
                                debug_print(f"Received message: '{message}'")
                            except requests.exceptions.RequestException as e:
                                debug_print(f"Error making HTTPS request: {e}")
                                message = ''

                            if message:
                                lines = message.split('\n')
                                new_lines = [line for line in lines if line not in printed_lines]
                                for line in new_lines:
                                    if line == 'DONE':
                                        progress_print("Test completed successfully.")
                                        progress_print("Test passed.")
                                        destroy_instance_silent(inst_id)
                                        instance_destroyed = True
                                        return True, ""
                                    elif line.startswith('ERROR'):
                                        progress_print(line)
                                        progress_print(f"Test failed with error: {line}.")
                                        destroy_instance_silent(inst_id)
                                        instance_destroyed = True
                                        return False, line
                                    else:
                                        progress_print(line)
                                    printed_lines.add(line)
                                no_response_seconds = 0
                            else:
                                no_response_seconds += 20
                                debug_print(f"No message received. Incremented no_response_seconds to {no_response_seconds}.")

                            if status == 'running' and no_response_seconds >= 120:
                                progress_print(f"No response for 120s with running instance. This may indicate a misconfiguration of ports on the machine. Network error or system stall or crashed.")
                                destroy_instance_silent(inst_id)
                                instance_destroyed = True
                                return False, "No response for 120 seconds with running instance. The system might have crashed or stalled during stress test. Use the self-test machine function in vast cli"

                            debug_print("Waiting for 20 seconds before the next check.")
                            time.sleep(20)

                        debug_print(f"Time limit reached. Destroying instance {inst_id}.")
                        return False, "Test did not complete within the time limit"
                    finally:
                        if not instance_destroyed and inst_id and instance_exist(inst_id):
                            destroy_instance_silent(inst_id)
                        progress_print(f"Machine: {machine_id} Done with testing remote.py results {message}")
                        warnings.simplefilter('default')

                # ----- main orchestration: wait then test -----
                instance_info, wait_reason = wait_for_instance(instance_id)
                if not instance_info:
                    result["reason"] = wait_reason
                else:
                    ip_address = instance_info.get("public_ipaddr")
                    if not ip_address:
                        result["reason"] = "Failed to retrieve public IP address."
                    else:
                        port_mappings = instance_info.get("ports", {}).get("5000/tcp", [])
                        port = port_mappings[0].get("HostPort") if port_mappings else None
                        if not port:
                            result["reason"] = "Failed to retrieve mapped port."
                        else:
                            delay = "15"
                            success, reason = run_machinetester(
                                ip_address, port, instance_id, args.machine_id, delay,
                            )
                            result["success"] = success
                            result["reason"] = reason

    except Exception as e:
        result["success"] = False
        result["reason"] = str(e)

    finally:
        try:
            if instance_id:
                # Helper might not be defined if we failed early, so use API directly
                try:
                    info = instances_api.show_instance(client, id=instance_id)
                    if info:
                        status = info.get('intended_status') or info.get('actual_status')
                        if status not in ['destroyed', 'terminated', 'offline']:
                            instances_api.destroy_instance(client, id=instance_id)
                except Exception:
                    pass
        except Exception as e:
            if args.debugging:
                print(f"Error during cleanup: {e}")

    if args.raw:
        print(json.dumps(result))
        sys.exit(0)
    else:
        if result["success"]:
            print("Test completed successfully.")
            sys.exit(0)
        else:
            print(f"Test failed: {result['reason']}")
            sys.exit(1)
