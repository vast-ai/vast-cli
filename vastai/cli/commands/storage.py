"""CLI commands for managing volumes, storage, copies, and cloud sync."""

import json
import time
import subprocess

from vastai.cli.parser import argument
from vastai.cli.display import (
    display_table, vol_displayable_fields, nw_vol_displayable_fields,
    volume_fields, connection_fields, deindent,
)
from vastai.cli.display import strip_strings
from vastai.cli.util import (
    default_start_date,
    parse_day_cron_style, parse_hour_cron_style,
    validate_frequency_values, add_scheduled_job,
)
from vastai.api import storage as storage_api
from vastai.api import offers as offers_api


from vastai.cli.utils import get_parser as _get_parser, get_client  # noqa: F401


parser = _get_parser()


# ---------------------------------------------------------------------------
# copy / cancel copy / cancel sync
# ---------------------------------------------------------------------------

@parser.command(
    argument("src", help="Source location for copy operation (supports multiple formats)", type=str),
    argument("dst", help="Target location for copy operation (supports multiple formats)", type=str),
    argument("-i", "--identity", help="Location of ssh private key", type=str),
    usage="vastai copy SRC DST",
    help="Copy directories between instances and/or local",
    epilog=deindent("""
        Copies a directory from a source location to a target location. Each of source and destination
        directories can be either local or remote, subject to appropriate read and write
        permissions required to carry out the action.

        Supported location formats:
        - [instance_id:]path               (legacy format, still supported)
        - C.instance_id:path              (container copy format)
        - cloud_service:path              (cloud service format)
        - cloud_service.cloud_service_id:path  (cloud service with ID)
        - local:path                      (explicit local path)
        - V.volume_id:path                (volume copy, see restrictions)

        You should not copy to /root or / as a destination directory, as this can mess up the permissions on your instance ssh folder, breaking future copy operations (as they use ssh authentication)
        You can see more information about constraints here: https://vast.ai/docs/gpu-instances/data-movement#constraints
        Volume copy is currently only supported for copying to other volumes or instances, not cloud services or local.

        Examples:
         vast copy 6003036:/workspace/ 6003038:/workspace/
         vast copy C.11824:/data/test local:data/test
         vast copy local:data/test C.11824:/data/test
         vast copy drive:/folder/file.txt C.6003036:/workspace/
         vast copy s3.101:/data/ C.6003036:/workspace/
         vast copy V.1234:/file C.5678:/workspace/

        The first example copy syncs all files from the absolute directory '/workspace' on instance 6003036 to the directory '/workspace' on instance 6003038.
        The second example copy syncs files from container 11824 to the local machine using structured syntax.
        The third example copy syncs files from local to container 11824 using structured syntax.
        The fourth example copy syncs files from Google Drive to an instance.
        The fifth example copy syncs files from S3 bucket with id 101 to an instance.
    """),
)
def copy(args):
    """Transfer data from one instance to another."""
    from vastai.utils import parse_vast_url
    client = get_client(args)

    (src_id, src_path) = parse_vast_url(args.src)
    (dst_id, dst_path) = parse_vast_url(args.dst)

    print(f"copying {str(src_id)+':' if src_id else ''}{src_path} {str(dst_id)+':' if dst_id else ''}{dst_path}")

    if args.explain:
        print("request json: ")
        print({"client_id": "me", "src_id": src_id, "dst_id": dst_id, "src_path": src_path, "dst_path": dst_path})

    rj = storage_api.copy(client, src_id=src_id, dst_id=dst_id, src_path=src_path, dst_path=dst_path)

    if (rj.get("success")) and ((src_id is None or src_id == "local") or (dst_id is None or dst_id == "local")):
        identity = f"-i {args.identity}" if (args.identity is not None) else ""
        if (src_id is None or src_id == "local"):
            remote_port = rj["dst_port"]
            remote_addr = rj["dst_addr"]
            cmd = f"rsync -arz -v --progress --rsh=ssh -e 'ssh {identity} -p {remote_port} -o StrictHostKeyChecking=no' {src_path} vastai_kaalia@{remote_addr}::{dst_id}/{dst_path}"
            print(cmd)
            subprocess.run(cmd, shell=True)
        elif (dst_id is None or dst_id == "local"):
            subprocess.run(f"mkdir -p {dst_path}", shell=True)
            remote_port = rj["src_port"]
            remote_addr = rj["src_addr"]
            cmd = f"rsync -arz -v --progress --rsh=ssh -e 'ssh {identity} -p {remote_port} -o StrictHostKeyChecking=no' vastai_kaalia@{remote_addr}::{src_id}/{src_path} {dst_path}"
            print(cmd)
            subprocess.run(cmd, shell=True)
    else:
        if rj.get("success"):
            print("Remote to Remote copy initiated - check instance status bar for progress updates (~30 seconds delayed).")
        else:
            if rj.get("msg") == "src_path not supported VMs.":
                print("copy between VM instances does not currently support subpaths (only full disk copy)")
            elif rj.get("msg") == "dst_path not supported for VMs.":
                print("copy between VM instances does not currently support subpaths (only full disk copy)")
            else:
                print(rj.get("msg", rj))


@parser.command(
    argument("dst", help="instance_id:/path to target of copy operation", type=str),
    usage="vastai cancel copy DST",
    help="Cancel a remote copy in progress, specified by DST id",
    epilog=deindent("""
        Use this command to cancel any/all current remote copy operations copying to a specific named instance, given by DST.

        Examples:
         vast cancel copy 12371

        The first example cancels all copy operations currently copying data into instance 12371

    """),
)
def cancel__copy(args):
    """Cancel a remote copy in progress, specified by DST id."""
    client = get_client(args)
    dst_id = args.dst
    if dst_id is None:
        print("invalid arguments")
        return

    print(f"canceling remote copies to {dst_id} ")

    rj = storage_api.cancel_copy(client, dst_id=dst_id)
    if rj.get("success"):
        print("Remote copy canceled - check instance status bar for progress updates (~30 seconds delayed).")
    else:
        print(rj.get("msg", rj))


@parser.command(
    argument("dst", help="instance_id:/path to target of sync operation", type=str),
    usage="vastai cancel sync DST",
    help="Cancel a remote cloud sync in progress, specified by DST id",
    epilog=deindent("""
        Use this command to cancel any/all current remote cloud sync operations copying to a specific named instance, given by DST.

        Examples:
         vast cancel sync 12371

        The first example cancels all copy operations currently copying data into instance 12371

    """),
)
def cancel__sync(args):
    """Cancel a remote cloud sync in progress, specified by DST id."""
    client = get_client(args)
    dst_id = args.dst
    if dst_id is None:
        print("invalid arguments")
        return

    print(f"canceling remote copies to {dst_id} ")

    rj = storage_api.cancel_sync(client, dst_id=dst_id)
    if rj.get("success"):
        print("Remote copy canceled - check instance status bar for progress updates (~30 seconds delayed).")
    else:
        print(rj.get("msg", rj))


# ---------------------------------------------------------------------------
# cloud copy
# ---------------------------------------------------------------------------

@parser.command(
    argument("--src", help="path to source of object to copy", type=str),
    argument("--dst", help="path to target of copy operation", type=str, default="/workspace"),
    argument("--instance", help="id of the instance", type=str),
    argument("--connection", help="id of cloud connection on your account (get from calling 'vastai show connections')", type=str),
    argument("--transfer", help="type of transfer, possible options include Instance To Cloud and Cloud To Instance", type=str, default="Instance to Cloud"),
    argument("--dry-run", help="show what would have been transferred", action="store_true"),
    argument("--size-only", help="skip based on size only, not mod-time or checksum", action="store_true"),
    argument("--ignore-existing", help="skip all files that exist on destination", action="store_true"),
    argument("--update", help="skip files that are newer on the destination", action="store_true"),
    argument("--delete-excluded", help="delete files on dest excluded from transfer", action="store_true"),
    argument("--schedule", choices=["HOURLY", "DAILY", "WEEKLY"], help="try to schedule a command to run hourly, daily, or weekly. Valid values are HOURLY, DAILY, WEEKLY  For ex. --schedule DAILY"),
    argument("--start_date", type=str, default=default_start_date(), help="Start date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is now. (optional)"),
    argument("--end_date", type=str, help="End date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is contract's end. (optional)"),
    argument("--day", type=parse_day_cron_style, help="Day of week you want scheduled job to run on (0-6, where 0=Sunday) or \"*\". Default will be 0. For ex. --day 0", default=0),
    argument("--hour", type=parse_hour_cron_style, help="Hour of day you want scheduled job to run on (0-23) or \"*\" (UTC). Default will be 0. For ex. --hour 16", default=0),
    usage="vastai cloud copy --src SRC --dst DST --instance INSTANCE_ID --connection CONNECTION_ID --transfer TRANSFER_TYPE",
    help="Copy files/folders to and from cloud providers",
    epilog=deindent("""
        Copies a directory from a source location to a target location. Each of source and destination
        directories can be either local or remote, subject to appropriate read and write
        permissions required to carry out the action. The format for both src and dst is [instance_id:]path.
        You can find more information about the cloud copy operation here: https://vast.ai/docs/gpu-instances/cloud-sync

        Examples:
         vastai show connections
         ID    NAME      Cloud Type
         1001  test_dir  drive
         1003  data_dir  drive

         vastai cloud copy --src /folder --dst /workspace --instance 6003036 --connection 1001 --transfer "Instance To Cloud"

        The example copies all contents of /folder into /workspace on instance 6003036 from gdrive connection 'test_dir'.
    """),
)
def cloud__copy(args):
    """Transfer data to/from cloud providers."""
    client = get_client(args)

    if (args.src is None) and (args.dst is None):
        print("invalid arguments")
        return

    flags = []
    if args.dry_run:
        flags.append("--dry-run")
    if args.size_only:
        flags.append("--size-only")
    if args.ignore_existing:
        flags.append("--ignore-existing")
    if args.update:
        flags.append("--update")
    if args.delete_excluded:
        flags.append("--delete-excluded")

    print(f"copying {args.src} {args.dst} {args.instance} {args.connection} {args.transfer}")

    req_json = {
        "src": args.src,
        "dst": args.dst,
        "instance_id": args.instance,
        "selected": args.connection,
        "transfer": args.transfer,
        "flags": flags
    }

    if args.explain:
        print("request json: ")
        print(req_json)

    if args.schedule:
        validate_frequency_values(args.day, args.hour, args.schedule)
        r = client.get(f"/instances/{args.instance}/", query_args={"owner": "me"})
        r.raise_for_status()
        row = r.json()["instances"]

        if args.transfer.lower() == "instance to cloud":
            if row:
                up_cost = row.get("internet_up_cost_per_tb", None)
                if up_cost is not None:
                    confirm = input(
                        f"Internet upload cost is ${up_cost} per TB. "
                        "Are you sure you want to schedule a cloud backup? (y/n): "
                    ).strip().lower()
                    if confirm != "y":
                        print("Cloud backup scheduling aborted.")
                        return
                else:
                    print("Warning: Could not retrieve internet upload cost. Proceeding without confirmation. You can use show scheduled-jobs and delete scheduled-job commands to delete scheduled cloud backup job.")

                cli_command = "cloud copy"
                api_endpoint = "/api/v0/commands/rclone/"
                contract_end_date = row.get("end_date", None)
                add_scheduled_job(client, args, req_json, cli_command, api_endpoint, "POST", instance_id=args.instance, contract_end_date=contract_end_date)
                return
            else:
                print("Instance not found. Please check the instance ID.")
                return

    rj = storage_api.cloud_copy(client, src=args.src, dst=args.dst, instance=args.instance,
                                connection=args.connection, transfer=args.transfer, flags=flags)
    if rj:
        print("Cloud Copy Started - check instance status bar for progress updates (~30 seconds delayed).")
        print("When the operation is finished you should see 'Cloud Copy Operation Finished' in the instance status bar.")


# ---------------------------------------------------------------------------
# show connections
# ---------------------------------------------------------------------------

@parser.command(
    usage="vastai show connections [--api-key API_KEY] [--raw]",
    help="Display user's cloud connections",
)
def show__connections(args):
    """Show the user's cloud connections."""
    client = get_client(args)
    rows = storage_api.show_connections(client)

    if args.raw:
        return rows
    else:
        display_table(rows, connection_fields)


# ---------------------------------------------------------------------------
# Note: show__network_disks and add__network_disk are in machines.py.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# search volumes
# ---------------------------------------------------------------------------

@parser.command(
    argument("-n", "--no-default", action="store_true", help="Disable default query"),
    argument("--limit", type=int, help=""),
    argument("--storage", type=float, default=1.0, help="Amount of storage to use for pricing, in GiB. default=1.0GiB"),
    argument("-o", "--order", type=str, help="Comma-separated list of fields to sort on. postfix field with - to sort desc.", default='score-'),
    argument("query", help="Query to search for. default: 'external=false verified=true disk_space>=1', pass -n to ignore default", nargs="*", default=None),
    usage="vastai search volumes [--help] [--api-key API_KEY] [--raw] <query>",
    help="Search for volume offers using custom query",
)
def search__volumes(args):
    """Search for volume offers using custom query."""
    from vastai.api.query import parse_query, vol_offers_fields, offers_alias, offers_mult

    try:
        if args.no_default:
            query = {}
        else:
            query = {"verified": {"eq": True}, "external": {"eq": False}, "disk_space": {"gte": 1}}

        if args.query is not None:
            query = parse_query(args.query, query, vol_offers_fields, {}, offers_mult)

        order = []
        for name in args.order.split(","):
            name = name.strip()
            if not name:
                continue
            direction = "asc"
            field = name
            if name.strip("-") != name:
                direction = "desc"
                field = name.strip("-")
            if name.strip("+") != name:
                direction = "asc"
                field = name.strip("+")
            if field in offers_alias:
                field = offers_alias[field]
            order.append([field, direction])
    except ValueError as e:
        print("Error: ", e)
        return 1

    client = get_client(args)

    if args.explain:
        print("request json: ")
        print(query)

    rows = offers_api.search_volumes(
        client, query=query, order=order,
        limit=args.limit, storage=args.storage,
        no_default=True,  # defaults already applied above
    )

    if args.raw:
        return rows
    else:
        display_table(rows, vol_displayable_fields)


# ---------------------------------------------------------------------------
# search network volumes
# ---------------------------------------------------------------------------

@parser.command(
    argument("-n", "--no-default", action="store_true", help="Disable default query"),
    argument("--limit", type=int, help=""),
    argument("--storage", type=float, default=1.0, help="Amount of storage to use for pricing, in GiB. default=1.0GiB"),
    argument("-o", "--order", type=str, help="Comma-separated list of fields to sort on.", default='score-'),
    argument("query", help="Query to search for.", nargs="*", default=None),
    usage="vastai search network volumes [--help] [--api-key API_KEY] [--raw] <query>",
    help="Search for network volume offers using custom query",
)
def search__network_volumes(args):
    """Search for network volume offers using custom query."""
    from vastai.api.query import parse_query, vol_offers_fields, offers_alias, offers_mult

    try:
        if args.no_default:
            query = {}
        else:
            query = {"verified": {"eq": True}, "external": {"eq": False}, "disk_space": {"gte": 1}}

        if args.query is not None:
            query = parse_query(args.query, query, vol_offers_fields, {}, offers_mult)

        order = []
        for name in args.order.split(","):
            name = name.strip()
            if not name:
                continue
            direction = "asc"
            field = name
            if name.strip("-") != name:
                direction = "desc"
                field = name.strip("-")
            if name.strip("+") != name:
                direction = "asc"
                field = name.strip("+")
            if field in offers_alias:
                field = offers_alias[field]
            order.append([field, direction])
    except ValueError as e:
        print("Error: ", e)
        return 1

    client = get_client(args)

    if args.explain:
        print("request json: ")
        print(query)

    rows = offers_api.search_network_volumes(
        client, query=query, order=order,
        limit=args.limit, storage=args.storage,
        no_default=True,  # defaults already applied above
    )

    if args.raw:
        return rows
    else:
        display_table(rows, nw_vol_displayable_fields)


# ---------------------------------------------------------------------------
# create / delete / clone volume
# ---------------------------------------------------------------------------

@parser.command(
    argument("id", help="id of volume offer", type=int),
    argument("-s", "--size", help="size in GB of volume. Default 15 GB.", default=15, type=float),
    argument("-n", "--name", help="Optional name of volume.", type=str),
    usage="vastai create volume ID [options]",
    help="Create a new volume",
)
def create__volume(args):
    """Create a new volume from an offer ID."""
    if args.explain:
        print("request json: ")
        print({"size": int(args.size), "id": int(args.id)})

    client = get_client(args)
    result = storage_api.create_volume(client, id=args.id, size=args.size, name=args.name)
    if args.raw:
        return result
    else:
        print("Created. {}".format(result))


@parser.command(
    argument("id", help="id of network volume offer", type=int),
    argument("-s", "--size", help="size in GB of network volume. Default 15 GB.", default=15, type=float),
    argument("-n", "--name", help="Optional name of network volume.", type=str),
    usage="vastai create network volume ID [options]",
    help="Create a new network volume",
)
def create__network_volume(args):
    """Create a new network volume from an offer ID."""
    if args.explain:
        print("request json: ")
        print({"size": int(args.size), "id": int(args.id)})

    client = get_client(args)
    result = storage_api.create_network_volume(client, id=args.id, size=args.size, name=args.name)
    if args.raw:
        return result
    else:
        print("Created. {}".format(result))


@parser.command(
    argument("id", help="id of volume contract", type=int),
    usage="vastai delete volume ID",
    help="Delete a volume",
)
def delete__volume(args):
    """Delete a volume."""
    client = get_client(args)
    result = storage_api.delete_volume(client, id=args.id)
    if args.raw:
        return result
    else:
        print("Deleted. {}".format(result))


@parser.command(
    argument("source", help="id of volume contract being cloned", type=int),
    argument("dest", help="id of volume offer volume is being copied to", type=int),
    argument("-s", "--size", help="Size of new volume contract, in GB.", type=float),
    argument("-d", "--disable_compression", action="store_true", help="Do not compress volume data before copying."),
    usage="vastai copy volume <source_id> <dest_id> [options]",
    help="Clone an existing volume",
)
def clone__volume(args):
    """Clone an existing volume."""
    if args.explain:
        print("request json: ")
        print({"src_id": args.source, "dst_id": args.dest})

    client = get_client(args)
    result = storage_api.clone_volume(client, source=args.source, dest=args.dest,
                                      size=args.size, disable_compression=args.disable_compression)
    if args.raw:
        return result
    else:
        print("Created. {}".format(result))


# ---------------------------------------------------------------------------
# show volumes
# ---------------------------------------------------------------------------

@parser.command(
    argument("-t", "--type", help="volume type to display. Default to all. Possible values are \"local\", \"all\", \"network\"", type=str, default="all"),
    usage="vastai show volumes [OPTIONS]",
    help="Show stats on owned volumes.",
)
def show__volumes(args):
    """Show stats on owned volumes."""
    client = get_client(args)
    processed = storage_api.show_volumes(client, type=args.type)
    for row in processed:
        for k, v in row.items():
            row[k] = strip_strings(v)
    if args.raw:
        return processed
    else:
        display_table(processed, volume_fields, replace_spaces=False)


# ---------------------------------------------------------------------------
# list / unlist volumes (host)
# ---------------------------------------------------------------------------

@parser.command(
    argument("id", help="id of machine to list", type=int),
    argument("-p", "--price_disk", help="storage price in $/GB/month, default: $0.10/GB/month", default=.10, type=float),
    argument("-e", "--end_date", help="contract offer expiration date", type=str),
    argument("-s", "--size", help="size of disk space allocated to offer in GB, default 15 GB", default=15),
    usage="vastai list volume ID [options]",
    help="[Host] list disk space for rent as a volume on a machine",
)
def list__volume(args):
    """List disk space for rent as a volume on a machine."""
    from vastai.cli.util import string_to_unix_epoch

    end_date = string_to_unix_epoch(args.end_date) if args.end_date else None

    if args.explain:
        print("request json: ")
        print({"size": int(args.size), "machine": int(args.id), "price_disk": float(args.price_disk)})

    client = get_client(args)
    result = storage_api.list_volume(client, id=args.id, size=int(args.size),
                                     price_disk=float(args.price_disk), end_date=end_date)
    if args.raw:
        return result
    else:
        print("Created. {}".format(result))


@parser.command(
    argument("ids", help="id of machines list", type=int, nargs='+'),
    argument("-p", "--price_disk", help="storage price in $/GB/month, default: $0.10/GB/month", default=.10, type=float),
    argument("-e", "--end_date", help="contract offer expiration date", type=str),
    argument("-s", "--size", help="size of disk space allocated to offer in GB, default 15 GB", default=15),
    usage="vastai list volume IDs [options]",
    help="[Host] list disk space for rent as a volume on machines",
)
def list__volumes(args):
    """List disk space for rent as a volume on multiple machines."""
    from vastai.cli.util import string_to_unix_epoch

    end_date = string_to_unix_epoch(args.end_date) if args.end_date else None

    if args.explain:
        print("request json: ")
        print({"size": int(args.size), "machine": [int(id) for id in args.ids], "price_disk": float(args.price_disk)})

    client = get_client(args)
    result = storage_api.list_volumes(client, ids=args.ids, size=int(args.size),
                                      price_disk=float(args.price_disk), end_date=end_date)
    if args.raw:
        return result
    else:
        print("Created. {}".format(result))


@parser.command(
    argument("disk_id", help="id of network disk to list", type=int),
    argument("-p", "--price_disk", help="storage price in $/GB/month, default: $0.15/GB/month", default=.15, type=float),
    argument("-e", "--end_date", help="contract offer expiration date", type=str, default=None),
    argument("-s", "--size", help="size of disk space allocated to offer in GB, default 15 GB", default=15, type=int),
    usage="vastai list network volume DISK_ID [options]",
    help="[Host] list disk space for rent as a network volume",
)
def list__network_volume(args):
    """List disk space for rent as a network volume."""
    from vastai.cli.util import string_to_unix_epoch

    end_date = string_to_unix_epoch(args.end_date) if args.end_date else None

    if args.explain:
        print("request json: ")
        print({"disk_id": args.disk_id, "price_disk": args.price_disk, "size": args.size})

    client = get_client(args)
    result = storage_api.list_network_volume(client, disk_id=args.disk_id, price_disk=args.price_disk,
                                             size=args.size, end_date=end_date)
    if args.raw:
        return result
    print(result["msg"])


@parser.command(
    argument("id", help="volume ID you want to unlist", type=int),
    usage="vastai unlist volume ID",
    help="[Host] unlist volume offer",
)
def unlist__volume(args):
    """Unlist a volume offer."""
    if args.explain:
        print("request json:", {"id": args.id})

    client = get_client(args)
    result = storage_api.unlist_volume(client, id=args.id)
    if args.raw:
        return result
    else:
        print(result["msg"])


@parser.command(
    argument("id", help="id of network volume offer to unlist", type=int),
    usage="vastai unlist network volume OFFER_ID",
    help="[Host] Unlists network volume offer",
)
def unlist__network_volume(args):
    """Unlist a network volume offer."""
    if args.explain:
        print("request json: ")
        print({"id": args.id})

    client = get_client(args)
    result = storage_api.unlist_network_volume(client, id=args.id)
    if args.raw:
        return result
    print(result["msg"])
