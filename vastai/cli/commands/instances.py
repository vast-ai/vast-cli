"""CLI commands for managing instances."""

import json
import sys
import time
import re
import argparse
import subprocess

from vastai.cli.parser import argument, hidden_aliases, MyWideHelpFormatter
from vastai.cli.util import (
    default_start_date, default_end_date,
    parse_day_cron_style, parse_hour_cron_style,
    validate_frequency_values, add_scheduled_job,
    parse_env, split_list, exec_with_threads,
    _get_gpu_names,
)
from vastai.api import instances as instances_api
from vastai.api import offers as offers_api


from vastai.cli.utils import get_parser as _get_parser, get_client  # noqa: F401


# ---------------------------------------------------------------------------
# Instance display
# ---------------------------------------------------------------------------

from vastai.cli.display import display_table, print_or_page, instance_fields, deindent

parser = _get_parser()


# ---------------------------------------------------------------------------
# show instances
# ---------------------------------------------------------------------------

@parser.command(
    argument("-q", "--quiet", action="store_true", help="only display numeric ids"),
    usage="vastai show instances [OPTIONS]",
    help="Display user's current instances",
    epilog=deindent("""
        Shows the stats on the instances the user is currently renting. Various options available to
        limit which instances are shown and jeir data.

        Examples:
            vastai show instances
            vastai show instances --raw
            vastai show instances -q
    """),
)
def show__instances(args, extra_filters=None):
    """Show the user's current instances."""
    client = get_client(args)
    rows = instances_api.show_instances(client)

    if extra_filters and extra_filters.get('internal'):
        field = extra_filters.get('field', 'id')
        return [str(r.get(field, '')) for r in rows]

    if args.quiet:
        for row in rows:
            id = row.get("id", None)
            if id is not None:
                print(id)
    elif args.raw:
        return rows
    else:
        display_table(rows, instance_fields)


@parser.command(
    argument("id", help="id of instance to get", type=int),
    argument("-q", "--quiet", action="store_true", help="only display numeric id"),
    usage="vastai show instance ID [options]",
    help="Display user's current instances",
)
def show__instance(args):
    """Shows stats for a single instance."""
    client = get_client(args)
    result = instances_api.show_instance(client, id=args.id)
    if args.raw:
        return result
    if args.quiet:
        print(result.get("id", ""))
    else:
        display_table([result], instance_fields)


# ---------------------------------------------------------------------------
# create instance
# ---------------------------------------------------------------------------

def get_runtype(args):
    runtype = 'ssh'
    if args.args:
        runtype = 'args'
    if (args.args == '') or (args.args == ['']) or (args.args == []):
        runtype = 'args'
        args.args = None
    if not args.jupyter and (args.jupyter_dir or args.jupyter_lab):
        args.jupyter = True
    if args.jupyter and runtype == 'args':
        print("Error: Can't use --jupyter and --args together. Try --onstart or --onstart-cmd instead of --args.", file=sys.stderr)
        return 1
    if args.jupyter:
        runtype = 'jupyter_direc ssh_direc ssh_proxy' if args.direct else 'jupyter_proxy ssh_proxy'
    elif args.ssh:
        runtype = 'ssh_direc ssh_proxy' if args.direct else 'ssh_proxy'
    return runtype


def validate_volume_params(args):
    if args.volume_size and not args.create_volume:
        raise argparse.ArgumentTypeError("Error: --volume-size can only be used with --create-volume.")
    if (args.create_volume or args.link_volume) and not args.mount_path:
        raise argparse.ArgumentTypeError("Error: --mount-path is required when creating or linking a volume.")

    valid_linux_path_regex = re.compile(r'^(/)?([^/\0]+(/)?)+$')
    if not valid_linux_path_regex.match(args.mount_path):
        raise argparse.ArgumentTypeError(f"Error: --mount-path '{args.mount_path}' is not a valid Linux file path.")

    volume_info = {
        "mount_path": args.mount_path,
        "create_new": True if args.create_volume else False,
        "volume_id": args.create_volume if args.create_volume else args.link_volume
    }
    if args.volume_label:
        volume_info["name"] = args.volume_label
    if args.volume_size:
        volume_info["size"] = args.volume_size
    elif args.create_volume:
        volume_info["size"] = 15
    return volume_info


def validate_portal_config(json_blob):
    runtype = json_blob.get('runtype')
    if runtype and 'jupyter' in runtype:
        return
    portal_config = json_blob['env']['PORTAL_CONFIG'].split("|")
    filtered_config = [config_str for config_str in portal_config if 'jupyter' not in config_str.lower()]
    if not filtered_config:
        raise ValueError("Error: env variable PORTAL_CONFIG must contain at least one non-jupyter related config string if runtype is not jupyter")
    else:
        json_blob['env']['PORTAL_CONFIG'] = "|".join(filtered_config)


def create_instance_impl(id, args):
    if args.onstart:
        with open(args.onstart, "r") as reader:
            args.onstart_cmd = reader.read()
    if args.onstart_cmd is None:
        args.onstart_cmd = args.entrypoint

    env = parse_env(args.env)
    runtype = None
    if args.template_hash is None:
        runtype = get_runtype(args)
        if runtype == 1:
            return 1

    volume_info = None
    if args.create_volume or args.link_volume:
        volume_info = validate_volume_params(args)

    # Validate portal config before sending to API
    if "PORTAL_CONFIG" in env:
        temp_blob = {"runtype": runtype, "env": env}
        validate_portal_config(temp_blob)
        env = temp_blob["env"]

    json_blob = {
        "client_id": "me",
        "image": args.image,
        "env": env,
        "price": args.bid_price,
        "disk": args.disk,
        "label": args.label,
        "extra": args.extra,
        "onstart": args.onstart_cmd,
        "image_login": args.login,
        "python_utf8": args.python_utf8,
        "lang_utf8": args.lang_utf8,
        "use_jupyter_lab": args.jupyter_lab,
        "jupyter_dir": args.jupyter_dir,
        "force": args.force,
        "cancel_unavail": args.cancel_unavail,
        "template_hash_id": args.template_hash,
        "user": args.user,
    }
    if runtype:
        json_blob["runtype"] = runtype
    if args.args is not None:
        json_blob["args"] = args.args
    if volume_info:
        json_blob["volume_info"] = volume_info

    if args.explain:
        print("request json: ")
        print(json_blob)

    client = get_client(args)
    rj = instances_api.create_instance(
        client, id=id, image=args.image, disk=args.disk, env=env,
        price=args.bid_price, label=args.label, extra=args.extra,
        onstart_cmd=args.onstart_cmd, login=args.login,
        python_utf8=args.python_utf8, lang_utf8=args.lang_utf8,
        jupyter_lab=args.jupyter_lab, jupyter_dir=args.jupyter_dir,
        force=args.force, cancel_unavail=args.cancel_unavail,
        template_hash=args.template_hash, user=args.user,
        runtype=runtype, args=args.args, volume_info=volume_info,
    )

    if args.raw:
        return rj
    else:
        print("Started. {}".format(rj))
    return True


_create_instance_args = [
    argument("--template_hash", help="Create instance from template info", type=str),
    argument("--user", help="User to use with docker create. This breaks some images, so only use this if you are certain you need it.", type=str),
    argument("--disk", help="size of local disk partition in GB", type=float, default=10),
    argument("--image", help="docker container image to launch", type=str),
    argument("--login", help="docker login arguments for private repo authentication, surround with '' ", type=str),
    argument("--label", help="label to set on the instance", type=str),
    argument("--onstart", help="filename to use as onstart script", type=str),
    argument("--onstart-cmd", help="contents of onstart script as single argument", type=str),
    argument("--entrypoint", help="override entrypoint for args launch instance", type=str),
    argument("--ssh", help="Launch as an ssh instance type", action="store_true"),
    argument("--jupyter", help="Launch as a jupyter instance instead of an ssh instance", action="store_true"),
    argument("--direct", help="Use (faster) direct connections for jupyter & ssh", action="store_true"),
    argument("--jupyter-dir", help="For runtype 'jupyter', directory in instance to use to launch jupyter. Defaults to image's working directory", type=str),
    argument("--jupyter-lab", help="For runtype 'jupyter', Launch instance with jupyter lab", action="store_true"),
    argument("--lang-utf8", help="Workaround for images with locale problems: install and generate locales before instance launch, and set locale to C.UTF-8", action="store_true"),
    argument("--python-utf8", help="Workaround for images with locale problems: set python's locale to C.UTF-8", action="store_true"),
    argument("--extra", help=argparse.SUPPRESS),
    argument("--env", help="env variables and port mapping options, surround with '' ", type=str),
    argument("--args", nargs=argparse.REMAINDER, help="list of arguments passed to container ENTRYPOINT. Onstart is recommended for this purpose. (must be last argument)"),
    argument("--force", help="Skip sanity checks when creating from an existing instance", action="store_true"),
    argument("--cancel-unavail", help="Return error if scheduling fails (rather than creating a stopped instance)", action="store_true"),
    argument("--bid_price", help="(OPTIONAL) create an INTERRUPTIBLE instance with per machine bid price in $/hour", type=float),
    argument("--create-volume", metavar="VOLUME_ASK_ID", help="Create a new local volume using an ID returned from the \"search volumes\" command and link it to the new instance", type=int),
    argument("--link-volume", metavar="EXISTING_VOLUME_ID", help="ID of an existing rented volume to link to the instance during creation. (returned from \"show volumes\" cmd)", type=int),
    argument("--volume-size", help="Size of the volume to create in GB. Only usable with --create-volume (default 15GB)", type=int),
    argument("--mount-path", help="The path to the volume from within the new instance container. e.g. /root/volume", type=str),
    argument("--volume-label", help="(optional) A name to give the new volume. Only usable with --create-volume", type=str),
]

@parser.command(
    argument("id", help="id of instance type to launch (returned from search offers)", type=int),
    *_create_instance_args,
    usage="vastai create instance ID [OPTIONS] [--args ...]",
    help="Create a new instance",
    epilog=deindent("""
        Performs the same action as pressing the "RENT" button on the website at https://console.vast.ai/create/
        Creates an instance from an offer ID (which is returned from "search offers"). Each offer ID can only be used to create one instance.
        Besides the offer ID, you must pass in an '--image' argument as a minimum.

        If you use args/entrypoint launch mode, we create a container from your image as is, without attempting to inject ssh and or jupyter.
        If you use the args launch mode, you can override the entrypoint with --entrypoint, and pass arguments to the entrypoint with --args.
        If you use --args, that must be the last argument, as any following tokens are consumed into the args string.
        For ssh/jupyter launch types, use --onstart-cmd to pass in startup script, instead of --entrypoint and --args.

        Examples:

        # create an on-demand instance with the PyTorch (cuDNN Devel) template and 64GB of disk
        vastai create instance 384826 --template_hash 661d064bbda1f2a133816b6d55da07c3 --disk 64

        # create an on-demand instance with the pytorch/pytorch image, 40GB of disk, open 8081 udp, direct ssh, set hostname to billybob, and a small onstart script
        vastai create instance 6995713 --image pytorch/pytorch --disk 40 --env '-p 8081:8081/udp -h billybob' --ssh --direct --onstart-cmd "env | grep _ >> /etc/environment; echo 'starting up'";

        # create an on-demand instance with the bobsrepo/pytorch:latest image, 20GB of disk, open 22, 8080, jupyter ssh, and set some env variables
        vastai create instance 384827  --image bobsrepo/pytorch:latest --login '-u bob -p 9d8df!fd89ufZ docker.io' --jupyter --direct --env '-e TZ=PDT -e XNAME=XX4 -p 22:22 -p 8080:8080' --disk 20

        # create an on-demand instance with the pytorch/pytorch image, 40GB of disk, override the entrypoint to bash and pass bash a simple command to keep the instance running. (args launch without ssh/jupyter)
        vastai create instance 5801802 --image pytorch/pytorch --disk 40 --onstart-cmd 'bash' --args -c 'echo hello; sleep infinity;'

        # create an interruptible (spot) instance with the PyTorch (cuDNN Devel) template, 64GB of disk, and a bid price of $0.10/hr
        vastai create instance 384826 --template_hash 661d064bbda1f2a133816b6d55da07c3 --disk 64 --bid_price 0.1

        Return value:
        Returns a json reporting the instance ID of the newly created instance:
        {'success': True, 'new_contract': 7835610}
    """),
)
def create__instance(args):
    """Create an instance from an offer ID."""
    create_instance_impl(args.id, args)


@parser.command(
    argument("ids", help="ids of instance types to launch (returned from search offers)", type=int, nargs='+'),
    *_create_instance_args,
    usage="vastai create instances [OPTIONS] ID0 ID1 ID2... [--args ...]",
    help="Create instances from a list of offers",
)
def create__instances(args):
    """Bulk create instances."""
    idlist = split_list(args.ids, 64)
    exec_with_threads(lambda ids: create_instance_impl(ids, args), idlist, nt=8)


# ---------------------------------------------------------------------------
# destroy instance
# ---------------------------------------------------------------------------

def destroy_instance_impl(id, args):
    client = get_client(args)
    rj = instances_api.destroy_instance(client, id=id)

    if args.raw:
        return rj
    elif rj.get("success"):
        print("destroying instance {id}.".format(**(locals())))
    else:
        print(rj.get("msg", rj))


@parser.command(
    argument("id", help="id of instance to delete", type=int),
    argument("-y", "--yes", help="Skip confirmation prompt", action="store_true"),
    usage="vastai destroy instance id [-h] [-y] [--api-key API_KEY] [--raw]",
    help="Destroy an instance (irreversible, deletes data)",
    epilog=deindent("""
        Perfoms the same action as pressing the "DESTROY" button on the website at https://console.vast.ai/instances/
        Example: vastai destroy instance 4242
        Use -y or --yes to skip the confirmation prompt.
    """),
)
def destroy__instance(args):
    """Destroy a single instance."""
    if not args.yes:
        try:
            confirm = input(f"Are you sure you want to destroy instance {args.id}? This is irreversible and will delete all data. [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return
        if confirm != "y":
            print("Aborted.")
            return
    destroy_instance_impl(args.id, args)


@parser.command(
    argument("ids", help="ids of instance to destroy", type=int, nargs='+'),
    argument("-y", "--yes", help="Skip confirmation prompt", action="store_true"),
    usage="vastai destroy instances [--raw] [-y] <id> [<id> ...]",
    help="Destroy a list of instances (irreversible, deletes data)",
)
def destroy__instances(args):
    """Bulk destroy instances."""
    if not args.yes:
        id_list_str = ", ".join(str(i) for i in args.ids)
        try:
            confirm = input(f"Are you sure you want to destroy instances {id_list_str}? This is irreversible and will delete all data. [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return
        if confirm != "y":
            print("Aborted.")
            return
    idlist = split_list(args.ids, 64)
    exec_with_threads(lambda ids: destroy_instance_impl(ids, args), idlist, nt=8)


# ---------------------------------------------------------------------------
# start/stop/reboot/recycle instance
# ---------------------------------------------------------------------------

def start_instance_impl(id, args):
    client = get_client(args)
    rj = instances_api.start_instance(client, id=id)

    if args.explain:
        print("request json: ")
        print({"state": "running"})
    if rj.get("success"):
        print("starting instance {id}.".format(**(locals())))
        return True
    else:
        print(rj.get("msg", rj))
    return False


@parser.command(
    argument("id", help="ID of instance to start/restart", type=int),
    usage="vastai start instance ID [OPTIONS]",
    help="Start a stopped instance",
    epilog=deindent("""
        This command attempts to bring an instance from the "stopped" state into the "running" state. This is subject to resource availability on the machine that the instance is located on.
        If your instance is stuck in the "scheduling" state for more than 30 seconds after running this, it likely means that the required resources on the machine to run your instance are currently unavailable.
        Examples:
            vastai start instances $(vastai show instances -q)
            vastai start instance 329838
    """),
)
def start__instance(args):
    """Start a stopped instance."""
    start_instance_impl(args.id, args)


@parser.command(
    argument("ids", help="ids of instance to start", type=int, nargs='+'),
    usage="vastai start instances [OPTIONS] ID0 ID1 ID2...",
    help="Start a list of instances",
)
def start__instances(args):
    """Bulk start instances."""
    idlist = split_list(args.ids, 64)
    exec_with_threads(lambda ids: start_instance_impl(ids, args), idlist, nt=8)


def stop_instance_impl(id, args):
    client = get_client(args)
    rj = instances_api.stop_instance(client, id=id)

    if args.explain:
        print("request json: ")
        print({"state": "stopped"})
    if rj.get("success"):
        print("stopping instance {id}.".format(**(locals())))
        return True
    else:
        print(rj.get("msg", rj))
    return False


@parser.command(
    argument("id", help="id of instance to stop", type=int),
    usage="vastai stop instance ID [OPTIONS]",
    help="Stop a running instance",
    epilog=deindent("""
        This command brings an instance from the "running" state into the "stopped" state. When an instance is "stopped" all of your data on the instance is preserved,
        and you can resume use of your instance by starting it again. Once stopped, starting an instance is subject to resource availability on the machine that the instance is located on.
        There are ways to move data off of a stopped instance, which are described here: https://vast.ai/docs/gpu-instances/data-movement
    """),
)
def stop__instance(args):
    """Stop a running instance."""
    stop_instance_impl(args.id, args)


@parser.command(
    argument("ids", help="ids of instance to stop", type=int, nargs='+'),
    usage="vastai stop instances [OPTIONS] ID0 ID1 ID2...",
    help="Stop a list of instances",
    epilog=deindent("""
        Examples:
            vastai stop instances $(vastai show instances -q)
            vastai stop instances 329838 984849
    """),
)
def stop__instances(args):
    """Bulk stop instances."""
    idlist = split_list(args.ids, 64)
    exec_with_threads(lambda ids: stop_instance_impl(ids, args), idlist, nt=8)


@parser.command(
    argument("id", help="id of instance to reboot", type=int),
    argument("--schedule", choices=["HOURLY", "DAILY", "WEEKLY"], help="try to schedule a command to run hourly, daily, or weekly. Valid values are HOURLY, DAILY, WEEKLY  For ex. --schedule DAILY"),
    argument("--start_date", type=str, default=default_start_date(), help="Start date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is now. (optional)"),
    argument("--end_date", type=str, default=default_end_date(), help="End date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is 7 days from now. (optional)"),
    argument("--day", type=parse_day_cron_style, help="Day of week you want scheduled job to run on (0-6, where 0=Sunday) or \"*\". Default will be 0. For ex. --day 0", default=0),
    argument("--hour", type=parse_hour_cron_style, help="Hour of day you want scheduled job to run on (0-23) or \"*\" (UTC). Default will be 0. For ex. --hour 16", default=0),
    usage="vastai reboot instance ID [OPTIONS]",
    help="Reboot (stop/start) an instance",
    epilog=deindent("""
        Stops and starts container without any risk of losing GPU priority.
    """),
)
def reboot__instance(args):
    """Reboot an instance."""
    client = get_client(args)
    rj = instances_api.reboot_instance(client, id=args.id)

    if args.schedule:
        validate_frequency_values(args.day, args.hour, args.schedule)
        cli_command = "reboot instance"
        api_endpoint = "/api/v0/instances/reboot/{id}/".format(id=args.id)
        json_blob = {"instance_id": args.id}
        add_scheduled_job(client, args, json_blob, cli_command, api_endpoint, "PUT", instance_id=args.id)
        return

    if rj.get("success"):
        print("Rebooting instance {args.id}.".format(**(locals())))
    else:
        print(rj.get("msg", rj))


@parser.command(
    argument("id", help="id of instance to recycle", type=int),
    usage="vastai recycle instance ID [OPTIONS]",
    help="Recycle (destroy/create) an instance",
    epilog=deindent("""
        Destroys and recreates container in place (from newly pulled image) without any risk of losing GPU priority.
    """),
)
def recycle__instance(args):
    """Recycle an instance."""
    client = get_client(args)
    rj = instances_api.recycle_instance(client, id=args.id)
    if rj.get("success"):
        print("Recycling instance {args.id}.".format(**(locals())))
    else:
        print(rj.get("msg", rj))


# ---------------------------------------------------------------------------
# update instance
# ---------------------------------------------------------------------------

@parser.command(
    argument("id", help="id of instance to update", type=int),
    argument("--template_id", help="new template ID to associate with the instance", type=int),
    argument("--template_hash_id", help="new template hash ID to associate with the instance", type=str),
    argument("--image", help="new image UUID for the instance", type=str),
    argument("--args", help="new arguments for the instance", type=str),
    argument("--env", help="new environment variables for the instance", type=json.loads),
    argument("--onstart", help="new onstart script for the instance", type=str),
    usage="vastai update instance ID [OPTIONS]",
    help="Update recreate an instance from a new/updated template",
    epilog=deindent("""
        Example: vastai update instance 1234 --template_hash_id 661d064bbda1f2a133816b6d55da07c3
    """),
)
def update__instance(args):
    """Update/recreate an instance from a new or updated template."""
    client = get_client(args)
    rj = instances_api.update_instance(
        client, id=args.id,
        template_id=args.template_id,
        template_hash_id=args.template_hash_id,
        image=args.image,
        args=args.args,
        env=args.env,
        onstart=args.onstart,
    )

    if args.raw:
        return rj
    if rj.get("success"):
        print(f"Instance {args.id} updated successfully.")
        if rj.get("updated_instance"):
            print("Updated instance details:")
            print(rj.get("updated_instance"))
    else:
        print(f"Failed to update instance {args.id}: {rj.get('msg')}")


# ---------------------------------------------------------------------------
# label / prepay / change bid
# ---------------------------------------------------------------------------

@parser.command(
    argument("id", help="id of instance to label", type=int),
    argument("label", help="label to set", type=str),
    usage="vastai label instance <id> <label>",
    help="Assign a string label to an instance",
)
def label__instance(args):
    """Set a label on an instance."""
    if args.explain:
        print("request json: ")
        print({"label": args.label})

    client = get_client(args)
    rj = instances_api.label_instance(client, id=args.id, label=args.label)
    if rj.get("success"):
        print("label for {args.id} set to {args.label}.".format(**(locals())))
    else:
        print(rj.get("msg", rj))


@parser.command(
    argument("id", help="id of instance to prepay for", type=int),
    argument("amount", help="amount of instance credit prepayment (default discount func of 0.2 for 1 month, 0.3 for 3 months)", type=float),
    usage="vastai prepay instance ID AMOUNT",
    help="Deposit credits into reserved instance",
)
def prepay__instance(args):
    """Prepay for an instance."""
    if args.explain:
        print("request json: ")
        print({"amount": args.amount})

    client = get_client(args)
    rj = instances_api.prepay_instance(client, id=args.id, amount=args.amount)
    if rj.get("success"):
        timescale = round(rj["timescale"], 3)
        discount_rate = 100.0 * round(rj["discount_rate"], 3)
        print("prepaid for {timescale} months of instance {args.id} applying ${args.amount} credits for a discount of {discount_rate}%".format(**(locals())))
    else:
        print(rj.get("msg", rj))


@parser.command(
    argument("id", help="id of instance type to change bid", type=int),
    argument("--price", help="per machine bid price in $/hour", type=float),
    argument("--schedule", choices=["HOURLY", "DAILY", "WEEKLY"], help="try to schedule a command to run hourly, daily, or weekly. Valid values are HOURLY, DAILY, WEEKLY  For ex. --schedule DAILY"),
    argument("--start_date", type=str, default=default_start_date(), help="Start date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is now. (optional)"),
    argument("--end_date", type=str, default=default_end_date(), help="End date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is 7 days from now. (optional)"),
    argument("--day", type=parse_day_cron_style, help="Day of week you want scheduled job to run on (0-6, where 0=Sunday) or \"*\". Default will be 0. For ex. --day 0", default=0),
    argument("--hour", type=parse_hour_cron_style, help="Hour of day you want scheduled job to run on (0-23) or \"*\" (UTC). Default will be 0. For ex. --hour 16", default=0),
    usage="vastai change bid id [--price PRICE]",
    help="Change the bid price for a spot/interruptible instance",
    epilog=deindent("""
        Change the current bid price of instance id to PRICE.
        If PRICE is not specified, then a winning bid price is used as the default.
    """),
)
def change__bid(args):
    """Change the bid price for a spot instance."""
    if args.explain:
        print("request json: ")
        print({"client_id": "me", "price": args.price})

    client = get_client(args)

    if args.schedule:
        validate_frequency_values(args.day, args.hour, args.schedule)
        cli_command = "change bid"
        api_endpoint = "/api/v0/instances/bid_price/{id}/".format(id=args.id)
        json_blob = {"client_id": "me", "price": args.price, "instance_id": args.id}
        add_scheduled_job(client, args, json_blob, cli_command, api_endpoint, "PUT", instance_id=args.id)
        return

    instances_api.change_bid(client, id=args.id, price=args.price)
    print("Per gpu bid price changed")


# ---------------------------------------------------------------------------
# launch instance
# ---------------------------------------------------------------------------

@parser.command(
    argument("-g", "--gpu-name", type=str, required=True, choices=_get_gpu_names(), help="Name of the GPU model, replace spaces with underscores"),
    argument("-n", "--num-gpus", type=str, required=True, choices=["1", "2", "4", "8", "12", "14"], help="Number of GPUs required"),
    argument("-r", "--region", type=str, help="Geographical location of the instance"),
    argument("-i", "--image", required=True, help="Name of the image to use for instance"),
    argument("-d", "--disk", type=float, default=16.0, help="Disk space required in GB"),
    argument("--limit", default=3, type=int, help=""),
    argument("-o", "--order", type=str, help="Comma-separated list of fields to sort on. postfix field with - to sort desc. ex: -o 'num_gpus,total_flops-'.  default='score-'", default='score-'),
    argument("--login", help="docker login arguments for private repo authentication, surround with '' ", type=str),
    argument("--label", help="label to set on the instance", type=str),
    argument("--onstart", help="filename to use as onstart script", type=str),
    argument("--onstart-cmd", help="contents of onstart script as single argument", type=str),
    argument("--entrypoint", help="override entrypoint for args launch instance", type=str),
    argument("--ssh", help="Launch as an ssh instance type", action="store_true"),
    argument("--jupyter", help="Launch as a jupyter instance instead of an ssh instance", action="store_true"),
    argument("--direct", help="Use (faster) direct connections for jupyter & ssh", action="store_true"),
    argument("--jupyter-dir", help="For runtype 'jupyter', directory in instance to use to launch jupyter. Defaults to image's working directory", type=str),
    argument("--jupyter-lab", help="For runtype 'jupyter', Launch instance with jupyter lab", action="store_true"),
    argument("--lang-utf8", help="Workaround for images with locale problems: install and generate locales before instance launch, and set locale to C.UTF-8", action="store_true"),
    argument("--python-utf8", help="Workaround for images with locale problems: set python's locale to C.UTF-8", action="store_true"),
    argument("--extra", help=argparse.SUPPRESS),
    argument("--env", help="env variables and port mapping options, surround with '' ", type=str),
    argument("--args", nargs=argparse.REMAINDER, help="list of arguments passed to container ENTRYPOINT. Onstart is recommended for this purpose. (must be last argument)"),
    argument("--force", help="Skip sanity checks when creating from an existing instance", action="store_true"),
    argument("--cancel-unavail", help="Return error if scheduling fails (rather than creating a stopped instance)", action="store_true"),
    argument("--template_hash", help="template hash which contains all relevant information about an instance. This can be used as a replacement for other parameters describing the instance configuration", type=str),
    usage="vastai launch instance [--help] [--api-key API_KEY] <gpu_name> <num_gpus> <image> [geolocation] [disk_space]",
    help="Launch the top instance from the search offers based on the given parameters",
    epilog=deindent("""
        Launches an instance based on the given parameters. The instance will be created with the top offer from the search results.
        Besides the gpu_name and num_gpus, you must pass in an '--image' argument as a minimum.

        If you use args/entrypoint launch mode, we create a container from your image as is, without attempting to inject ssh and or jupyter.
        If you use the args launch mode, you can override the entrypoint with --entrypoint, and pass arguments to the entrypoint with --args.
        If you use --args, that must be the last argument, as any following tokens are consumed into the args string.
        For ssh/jupyter launch types, use --onstart-cmd to pass in startup script, instead of --entrypoint and --args.

        Examples:

            # launch a single RTX 3090 instance with the pytorch image and 16 GB of disk space located anywhere
            python vast.py launch instance -g RTX_3090 -n 1 -i pytorch/pytorch

            # launch a 4x RTX 3090 instance with the pytorch image and 32 GB of disk space located in North America
            python vast.py launch instance -g RTX_3090 -n 4 -i pytorch/pytorch -d 32.0 -r North_America

        Available fields:

            Name                    Type      Description

            num_gpus:               int       # of GPUs
            gpu_name:               string    GPU model name
            region:                 string    Region of the instance
            image:                  string    Docker image name
            disk_space:             float     Disk space in GB
            ssh, jupyter, direct:   bool      Flags to specify the instance type and connection method.
            env:                    str       Environment variables and port mappings, encapsulated in single quotes.
            args:                   list      Arguments passed to the container's ENTRYPOINT, used only if '--args' is specified.
    """),
)
def launch__instance(args):
    """Launch the top instance from search offers."""
    if args.onstart:
        with open(args.onstart, "r") as reader:
            args.onstart_cmd = reader.read()
    if args.onstart_cmd is None:
        args.onstart_cmd = args.entrypoint

    runtype = None
    if args.template_hash is None:
        runtype = get_runtype(args)
        if runtype == 1:
            return 1

    client = get_client(args)
    try:
        response_data = offers_api.launch_instance(
            client,
            gpu_name=args.gpu_name,
            num_gpus=args.num_gpus,
            image=args.image,
            region=args.region,
            disk=args.disk,
            order=args.order,
            limit=args.limit,
            env=parse_env(args.env),
            label=args.label,
            extra=args.extra,
            onstart_cmd=args.onstart_cmd,
            login=args.login,
            python_utf8=args.python_utf8,
            lang_utf8=args.lang_utf8,
            jupyter_lab=args.jupyter_lab,
            jupyter_dir=args.jupyter_dir,
            force=args.force,
            cancel_unavail=args.cancel_unavail,
            template_hash=args.template_hash,
            runtype=runtype,
            args=args.args,
        )
        if args.raw:
            return response_data
        else:
            print("Started. {}".format(response_data))
        if response_data.get('success'):
            print(f"Instance launched successfully: {response_data.get('new_contract')}")
        else:
            print(f"Failed to launch instance: {response_data.get('error')}, {response_data.get('message')}")
    except Exception as err:
        print(f"An error occurred: {err}")


# ---------------------------------------------------------------------------
# show instances-v1 (paginated, Rich tables)
# ---------------------------------------------------------------------------

_DEFAULT_INSTANCE_SELECT_COLS = [
    "id", "actual_status", "label",
    "num_gpus", "gpu_name", "gpu_util",
    "disk_space", "disk_usage", "disk_util",
    "volume_info",
    "dph_total", "image_uuid",
    "start_date", "verification",
]

_VERBOSE_INSTANCE_SELECT_COLS = _DEFAULT_INSTANCE_SELECT_COLS + [
    "machine_id", "template_id", "template_name",
    "geolocation", "inet_up", "inet_down",
    "ssh_host", "ssh_port", "status_msg",
]


def _fmt_age(start_date):
    """Format seconds elapsed since start_date as e.g. '2d 3h' or '4h 15m'."""
    if not start_date:
        return "—"
    secs = max(0, time.time() - start_date)
    d, rem  = divmod(int(secs), 86400)
    h, rem  = divmod(rem, 3600)
    m, _    = divmod(rem, 60)
    if d:   return f"{d}d {h}h"
    if h:   return f"{h}h {m}m"
    return f"{m}m"


def _fmt_disk(disk_usage, disk_space, disk_util):
    """Format disk as 'used/total GB (X%)' or '?/total GB'."""
    total = f"{disk_space:.0f}" if disk_space is not None else "?"
    if disk_usage is None or disk_usage < 0:
        return f"?/{total} GB"
    used = f"{disk_usage:.1f}"
    if disk_util is not None and disk_util >= 0:
        pct = disk_util * 100
        return f"{used}/{total} GB ({pct:.0f}%)"
    return f"{used}/{total} GB"


def _fmt_volumes(volume_info):
    """Format volume_info list as a compact string showing IDs and usage."""
    if not volume_info:
        return "—"
    if len(volume_info) == 1:
        v = volume_info[0]
        vid = v.get("id", "?")
        avail = v.get("avail_space")
        total = v.get("total_space")
        if avail is not None and total is not None:
            used = total - avail
            return f"#{vid} {used:.0f}/{total:.0f} GB"
        return f"#{vid}"
    return ", ".join(f"#{v.get('id', '?')}" for v in volume_info)


def _fmt_gpu(num_gpus, gpu_name, gpu_util):
    """Format as '4x RTX 3090' or '4x RTX 3090 (72%)'."""
    base = f"{int(num_gpus)}x {gpu_name}" if num_gpus and gpu_name else (gpu_name or "—")
    if gpu_util is not None and gpu_util >= 0:
        return f"{base} ({gpu_util:.0f}%)"
    return base


_STATUS_COLORS = {"running": "bold green", "loading": "bold yellow", "exited": "bright_red", "created": "bright_white"}
_VERIF_COLORS  = {"verified": "sea_green2", "unverified": "gold1", "deverified": "bright_red"}


def _status_style(status):
    return _STATUS_COLORS.get(status, "white")

def _verif_style(v):
    return _VERIF_COLORS.get(v, "white")


_INSTANCE_COL_MAX_WIDTHS = {
    "gpu":      20,
    "image":    30,
    "age":       8,
    "volumes":  17,
    "location": 22,
    "net":      11,
    "ssh":      22,
    "template": 32,
    "msg":      30,
}

# Column spec: (name, header, style, justify, min_width, drop_order, verbose_only)
_INSTANCE_COL_SPECS = [
    ("id",       "ID",       "bright_white", "right",  4,   0,  False),
    ("status",   "Status",   None,           "center", 7,   0,  False),
    ("label",    "Label",    "bright_white", "left",   7,   0,  False),
    ("gpu",      "GPU",      "steel_blue1",  "left",   13,  0,  False),
    ("disk",     "Disk",     "bright_white", "right",  8,   5,  False),
    ("volumes",  "Volumes",  "bright_white", "left",   10,  6,  False),
    ("dph",      "$/hr",     "sea_green2",   "right",  7,   1,  False),
    ("image",    "Image",    "orchid",       "left",   30,  2,  False),
    ("age",      "Age",      "bright_white", "left",   8,   3,  False),
    ("verified", "Verified", None,           "center", 10,  0,  False),
    ("machine",  "Machine",  "gold1",        "center", 5,   8,  True),
    ("net",      "Net Mbps", "bright_white", "left",   9,   9,  True),
    ("location", "Location", "bright_white", "center", 10,  10, True),
    ("template", "Template", "bright_white", "center", 20,  11, True),
    ("ssh",      "SSH",      "cyan",         "left",   21,  7,  True),
    ("msg",      "Msg",      "dim white",    "left",   15,  12, True),
]

_INSTANCE_COL_SPEC_BY_NAME = {s[0]: s for s in _INSTANCE_COL_SPECS}

try:
    from rich.text import Text as _RichText
except ImportError:
    _RichText = None


def _render_instance_col(name, inst):
    """Render a single cell value for the given column name."""
    if name == "id":
        return str(inst.get("id", "—"))
    if name == "status":
        s = inst.get("actual_status") or "—"
        return _RichText(s, style=_status_style(s))
    if name == "label":
        return inst.get("label") or "—"
    if name == "gpu":
        return _fmt_gpu(inst.get("num_gpus"), inst.get("gpu_name"), inst.get("gpu_util"))
    if name == "disk":
        return _fmt_disk(inst.get("disk_usage"), inst.get("disk_space"), inst.get("disk_util"))
    if name == "volumes":
        return _fmt_volumes(inst.get("volume_info") or [])
    if name == "dph":
        dph = inst.get("dph_total")
        return f"${dph:.4f}" if dph is not None else "—"
    if name == "image":
        return (inst.get("image_uuid") or "—")[:50]
    if name == "age":
        return _fmt_age(inst.get("start_date"))
    if name == "verified":
        v = inst.get("verification") or "—"
        return _RichText(v, style=_verif_style(v))
    if name == "ssh":
        return f"{inst.get('ssh_host')}:{inst.get('ssh_port', '')}" if inst.get("ssh_host") else "—"
    if name == "machine":
        return str(inst.get("machine_id", "—"))
    if name == "net":
        up, down = inst.get("inet_up"), inst.get("inet_down")
        return f"↑{up:.0f} ↓{down:.0f}" if (up is not None and down is not None) else "—"
    if name == "location":
        return inst.get("geolocation") or "—"
    if name == "template":
        tid, tname = inst.get("template_id"), inst.get("template_name") or ""
        return (f"{tname[:28]} ({tid})" if tid else tname[:30] or "—")
    if name == "msg":
        return (inst.get("status_msg") or "—")[:40]
    return "—"


def _estimate_table_width(specs):
    """Estimate rendered table width for a list of col specs."""
    n = len(specs)
    content = sum(
        _INSTANCE_COL_MAX_WIDTHS.get(s[0]) or max(len(s[1]), s[4])
        for s in specs
    )
    return 4 + 2 * n + (n - 1) + content


def _build_instances_table(instances, verbose=False, cols=None):
    """Build the Rich table for instances."""
    import shutil
    from rich.table import Table
    from rich import box

    show_volumes = any(inst.get("volume_info") for inst in instances)
    term_width = shutil.get_terminal_size((120, 24)).columns

    if cols is not None:
        active = [_INSTANCE_COL_SPEC_BY_NAME[c] for c in cols if c in _INSTANCE_COL_SPEC_BY_NAME]
        hidden = []
    else:
        candidate = [
            s for s in _INSTANCE_COL_SPECS
            if (not s[6] or verbose) and not (s[0] == "volumes" and not show_volumes)
        ]
        droppable = sorted((s for s in candidate if s[5] > 0), key=lambda s: s[5], reverse=True)
        active = list(candidate)
        for drop_spec in droppable:
            if _estimate_table_width(active) <= term_width:
                break
            active.remove(drop_spec)
        hidden = [s[1] for s in candidate if s not in active]

    tbl = Table(
        style="white",
        header_style="bold bright_yellow",
        box=box.DOUBLE_EDGE,
        row_styles=["on grey11", "none"],
    )
    for name, header, style, justify, min_width, *_ in active:
        kwargs = dict(justify=justify, no_wrap=True, min_width=min_width)
        if name in _INSTANCE_COL_MAX_WIDTHS:
            kwargs["max_width"] = _INSTANCE_COL_MAX_WIDTHS[name]
        if style:
            kwargs["style"] = style
        tbl.add_column(_RichText(header, justify="center"), **kwargs)

    for inst in instances:
        tbl.add_row(*[_render_instance_col(name, inst) for name, *_ in active])

    return tbl, hidden


_FILTER_VALUE_COLORS = {
    "status":       _STATUS_COLORS,
    "verification": _VERIF_COLORS,
}


def _render_filter_values(values, colors=None, bold=False, line_sep=False):
    """Render a sequence of filter values as a Rich Text, dot-separated."""
    t = _RichText()
    for i, v in enumerate(values):
        if i: t.append("|" if line_sep else "  ·  ", style="bright_white")
        style = (colors or {}).get(v, "bright_white")
        t.append(v, style=("bold " + style) if bold else style)
    return t


def _build_summary_panel(total, label_counts, active_filters=None, order_by=None):
    """Build a Rich Panel summarising the instance query."""
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    lines = []
    lines.append(Text.assemble(("Total: ", "bold bright_yellow"), (f"{total} instances", "bold bright_white")))

    if label_counts:
        parts = []
        for lbl, cnt in sorted(label_counts.items(), key=lambda x: -x[1]):
            display = lbl if lbl else "(unlabeled)"
            parts.append(f"{display}: {cnt}")
        lines.append(Text.assemble(("Labels: ", "bold bright_yellow"), ("  ·  ".join(parts), "bright_white")))

    if active_filters:
        filter_line = Text.assemble(("Filters: ", "bold bright_yellow"))
        for i, (k, vals) in enumerate(active_filters.items()):
            if i: filter_line.append("   ", style="dim")
            filter_line.append(f"{k}=", style="bold bright_white")
            filter_line.append_text(_render_filter_values(vals, _FILTER_VALUE_COLORS.get(k), bold=True, line_sep=True))
        lines.append(filter_line)

    if order_by:
        order_line = Text.assemble(("Order by: ", "bold bright_yellow"))
        for i, key in enumerate(order_by):
            if i: order_line.append("  >  ", style="bright_white")
            order_line.append(key["col"], style="bold bright_white")
            order_line.append(f" ({key['dir']})", style="bright_white")
        lines.append(order_line)

    grid = Table.grid(padding=(0, 0))
    grid.add_column()
    for line in lines:
        grid.add_row(line)

    return Panel(grid, title="[bold bright_yellow]Results Summary[/bold bright_yellow]", style="on #000000", border_style="bright_yellow", expand=False)


def _build_filters_panel(filters):
    """Build a Rich Panel showing the distinct filterable values."""
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    statuses = sorted({f["actual_status"] for f in filters if f.get("actual_status")})
    verifs   = sorted({f["verification"]   for f in filters if f.get("verification")})
    gpus     = sorted({f["gpu_name"]        for f in filters if f.get("gpu_name")})

    lines = [
        Text.assemble(("--status:       ", "bold bright_yellow"), _render_filter_values(statuses, _STATUS_COLORS)),
        Text.assemble(("--verification: ", "bold bright_yellow"), _render_filter_values(verifs, _VERIF_COLORS)),
        Text.assemble(("--gpu-name:     ", "bold bright_yellow"), _render_filter_values(gpus)),
    ]

    grid = Table.grid(padding=(0, 0))
    grid.add_column()
    for line in lines:
        grid.add_row(line)

    return Panel(grid, title="[bright_white]Filterable Values[/bright_white]", style="on #000000", border_style="bright_white", expand=False)


def _rich_object_to_string(rich_obj, no_color=True):
    """Render a Rich object to a string."""
    from io import StringIO
    from rich.console import Console
    buffer = StringIO()
    console = Console(record=True, file=buffer)
    console.print(rich_obj)
    return console.export_text(clear=True, styles=not no_color)


@parser.command(
    argument("-q", "--quiet",       action="store_true", help="only print instance IDs, one per line"),
    argument("-v", "--verbose",     action="store_true", help="show additional columns (SSH, location, template, etc.)"),
    argument("-a", "--all",         action="store_true", help="fetch all pages automatically; useful for scripting"),
    argument("-s", "--status",      metavar="STATUS",    nargs="+", help="filter by container status: running loading exited"),
    argument("--label",             metavar="LABEL",     nargs="+", help="filter by instance label; pass empty string '' for unlabeled"),
    argument("--gpu-name",          metavar="GPU",       nargs="+", dest="gpu_name", help="filter by GPU model name"),
    argument("--verification",      metavar="VERIF",     nargs="+", choices=["verified", "unverified", "deverified"], help="filter by verification status"),
    argument("-l", "--limit",       type=int, default=25, help="max instances per page (1-25, default 25)"),
    argument("-t", "--next-token",  dest="next_token",   help="resume from a pagination token"),
    argument("--order-by",          dest="order_by",     metavar="COL [asc|desc]", action="append", help="sort by column; repeat for multiple keys"),
    argument("--cols",              metavar="COLS",       help=f"override displayed columns (available: {','.join(s[0] for s in _INSTANCE_COL_SPECS)})"),
    usage="vastai show instances-v1 [OPTIONS]",
    help="List instances with filtering, sorting, and pagination",
    epilog=deindent("""
        Displays your instances in a table with auto-sizing columns. Narrow terminals
        drop lower-priority columns automatically; use --cols to override.

        Examples:
            vastai show instances-v1
            vastai show instances-v1 -v
            vastai show instances-v1 --status running loading
            vastai show instances-v1 --gpu-name 'RTX A5000' 'GTX 1070'
            vastai show instances-v1 --label training --order-by start_date desc
            vastai show instances-v1 --cols id,status,gpu,dph
            vastai show instances-v1 --next-token eyJ2YWx1ZXMi...
    """),
)
def show__instances_v1(args):
    try:
        from rich.prompt import Confirm
        from rich.text import Text
        from rich.padding import Padding
        has_rich = True
    except ImportError:
        has_rich = False

    client = get_client(args)

    # build select_filters
    select_filters = {}
    active_display_filters = {}

    if args.status:
        invalid_statuses = [s for s in args.status if s not in _STATUS_COLORS]
        if invalid_statuses:
            valid = ", ".join(sorted(_STATUS_COLORS))
            print(f"Warning: unknown status value(s): {', '.join(invalid_statuses)}. Valid: {valid}", file=sys.stderr)
        select_filters["actual_status"] = {"in": args.status}
        active_display_filters["status"] = args.status

    if args.label is not None:
        vals = [None if l == "" else l for l in args.label]
        select_filters["label"] = {"in": vals}
        active_display_filters["label"] = [l or "(unlabeled)" for l in vals]

    if args.gpu_name:
        select_filters["gpu_name"] = {"in": args.gpu_name}
        active_display_filters["gpu_name"] = args.gpu_name

    if args.verification:
        select_filters["verification"] = {"in": args.verification}
        active_display_filters["verification"] = args.verification

    # order_by
    order_by = [{"col": "id", "dir": "asc"}]
    if args.order_by:
        order_by = []
        seen_cols = set()
        for entry in args.order_by:
            parts = entry.split()
            col  = parts[0]
            dirn = parts[1].lower() if len(parts) > 1 and parts[1].lower() in ("asc", "desc") else "asc"
            order_by.append({"col": col, "dir": dirn})
            seen_cols.add(col)
        if "id" not in seen_cols:
            order_by.append({"col": "id", "dir": "asc"})

    limit = max(1, min(args.limit, 25))

    params = {
        "select_filters": json.dumps(select_filters),
        "order_by":       json.dumps(order_by),
        "limit":          limit,
    }
    if not args.raw:
        select_cols = _VERBOSE_INSTANCE_SELECT_COLS if args.verbose else _DEFAULT_INSTANCE_SELECT_COLS
        if not has_rich:
            select_cols = [s[0] for s in instance_fields]
        params["select_cols"] = json.dumps(select_cols)
    if args.next_token:
        params["after_token"] = args.next_token

    # fetch filter breakdown
    filter_combos = None
    if not args.quiet and not args.raw:
        try:
            filter_combos = instances_api.show_instance_filters(client)
        except Exception:
            pass

    user_cols = [c.strip() for c in args.cols.split(",")] if args.cols and has_rich else None

    page = 0
    offset = 0
    looping = True
    all_instances = []
    while looping:
        if args.all and page > 0:
            time.sleep(1)

        data = instances_api.show_instances_v1(client, params)

        instances   = data.get("instances", [])
        next_token  = data.get("next_token")
        total       = data.get("total_instances", 0)
        label_cnts  = data.get("label_counts", {})
        page       += 1

        if args.raw:
            print(json.dumps(data, indent=1))
            return

        if args.quiet:
            for inst in instances:
                instance_id = inst.get("id")
                if instance_id is not None:
                    print(instance_id)
            break

        if args.all:
            all_instances.extend(instances)
            if next_token:
                sys.stderr.write(f"\rLoading more... (page {page + 1})")
                sys.stderr.flush()
                params["after_token"] = next_token
                continue
            sys.stderr.write("\r\033[K")
            sys.stderr.flush()
            instances = all_instances

        output_parts = []

        if has_rich:
            if page == 1 or args.all:
                if filter_combos:
                    output_parts.append(_rich_object_to_string(_build_filters_panel(filter_combos), no_color=args.no_color))
                output_parts.append(_rich_object_to_string(_build_summary_panel(
                    total, label_cnts,
                    active_filters=active_display_filters,
                    order_by=order_by if args.order_by else None,
                ), no_color=args.no_color).rstrip("\n"))
            else:
                output_parts.append('')

            if not instances:
                empty_msg = "No instances matched your filters." if active_display_filters else "No instances found."
                output_parts.append(_rich_object_to_string(Text(empty_msg, style="bright_white"), no_color=args.no_color).rstrip())
            else:
                tbl, hidden = _build_instances_table(instances, verbose=args.verbose, cols=user_cols)

                caption = Text()
                if not args.all:
                    if not args.next_token:
                        caption.append(f"[Page {page}]", style="bright_white")
                        caption.append("  ·  ", style="bright_white")
                    caption.append("Fetched Results: ", style="bright_white")
                    caption.append(f"{offset + 1} – {offset + len(instances)}", style="bright_white")
                    caption.append(f" of {total}", style="bright_white")
                if hidden and (page == 1 or args.all):
                    caption.append(
                        f"\nColumns hidden to fit terminal width: {', '.join(hidden)}"
                        f"  ·  use --cols to customize (see --help)",
                        style="dim",
                    )
                if caption:
                    tbl.caption = caption
                    tbl.caption_justify = "left"

                padded = Padding(tbl, (0, 1, 0, 1), style="on #000000", expand=False)
                output_parts.append(_rich_object_to_string(padded, no_color=args.no_color))
                if next_token:
                    output_parts.append(f"Next page token: {next_token}\n")
        else:
            if page == 1 or args.all:
                if filter_combos:
                    statuses = sorted({f["actual_status"] for f in filter_combos if f.get("actual_status")})
                    verifs   = sorted({f["verification"]   for f in filter_combos if f.get("verification")})
                    gpus     = sorted({f["gpu_name"]        for f in filter_combos if f.get("gpu_name")})
                    print("Filterable Values:")
                    print(f"  --status:       {' | '.join(statuses) if statuses else '(none)'}")
                    print(f"  --verification: {' | '.join(verifs) if verifs else '(none)'}")
                    print(f"  --gpu-name:     {' | '.join(gpus) if gpus else '(none)'}")
                    print()
                summary_lines = [f"Total: {total} instances"]
                if label_cnts:
                    lbl_parts = [f"{(lbl or '(unlabeled)')}: {cnt}" for lbl, cnt in sorted(label_cnts.items(), key=lambda x: -x[1])]
                    summary_lines.append(f"Labels: {'  ·  '.join(lbl_parts)}")
                if active_display_filters:
                    filter_parts = [f"{k}={' | '.join(str(v) for v in vals)}" for k, vals in active_display_filters.items()]
                    summary_lines.append(f"Filters: {'   '.join(filter_parts)}")
                if args.order_by:
                    order_parts = [f"{o['col']} ({o['dir']})" for o in order_by]
                    summary_lines.append(f"Order by: {'  >  '.join(order_parts)}")
                print("Results Summary:")
                for line in summary_lines:
                    print(f"  {line}")
                print()

            if not instances:
                print("No instances matched your filters." if active_display_filters else "No instances found.")
            else:
                display_table(instances, instance_fields)
                if not args.all:
                    print(f"[Page {page}]  Fetched Results: {offset + 1} – {offset + len(instances)} of {total}")
                if next_token:
                    print(f"Next page token: {next_token}")
            if page == 1:
                print("\nNOTE: install the 'rich' module for colored output  (pip install rich)")

        if not args.all:
            offset += len(instances)

        if args.all or not next_token:
            print_or_page(args, "\n".join(output_parts))
            looping = False
        else:
            print("\n".join(output_parts))
            try:
                if has_rich:
                    ans = Confirm.ask(f"Fetch next page? (page {page + 1})", default=False)
                else:
                    ans = input(f"Fetch next page? (page {page + 1}) (y/N): ").strip().lower() == "y"
            except (EOFError, KeyboardInterrupt):
                ans = False
            if ans:
                params["after_token"] = next_token
            else:
                looping = False
