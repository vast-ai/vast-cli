"""CLI commands for managing instances."""

import json
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
)
from vastai.api import instances as instances_api
from vastai.api import offers as offers_api


from vastai.cli.utils import get_parser as _get_parser, get_client  # noqa: F401


# ---------------------------------------------------------------------------
# Instance display
# ---------------------------------------------------------------------------

from vastai.cli.display import display_table, instance_fields, deindent

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
    argument("id", help="id of instance to show info for", type=int),
    usage="vastai show instance ID [options]",
    help="Display user's current instance",
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
        print("Error: Can't use --jupyter and --args together. Try --onstart or --onstart-cmd instead of --args.", file=__import__('sys').stderr)
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

        Examples:

        # create an on-demand instance with the PyTorch (cuDNN Devel) template and 64GB of disk
        vastai create instance 384826 --template_hash 661d064bbda1f2a133816b6d55da07c3 --disk 64

        # create an on-demand instance with the pytorch/pytorch image, 40GB of disk, direct ssh
        vastai create instance 6995713 --image pytorch/pytorch --disk 40 --ssh --direct --onstart-cmd "env | grep _ >> /etc/environment; echo 'starting up'";

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
    usage="vastai destroy instance id [-h] [--api-key API_KEY] [--raw]",
    help="Destroy an instance (irreversible, deletes data)",
    epilog=deindent("""
        Perfoms the same action as pressing the "DESTROY" button on the website at https://console.vast.ai/instances/
        Example: vastai destroy instance 4242
    """),
)
def destroy__instance(args):
    """Destroy a single instance."""
    destroy_instance_impl(args.id, args)


@parser.command(
    argument("ids", help="ids of instance to destroy", type=int, nargs='+'),
    usage="vastai destroy instances [--raw] <id>",
    help="Destroy a list of instances (irreversible, deletes data)",
)
def destroy__instances(args):
    """Bulk destroy instances."""
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
        This command attempts to bring an instance from the "stopped" state into the "running" state.
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
        This command brings an instance from the "running" state into the "stopped" state.
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
    argument("-g", "--gpu-name", type=str, required=True, help="Name of the GPU model, replace spaces with underscores"),
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
    argument("--template_hash", help="template hash which contains all relevant information about an instance", type=str),
    usage="vastai launch instance [--help] [--api-key API_KEY] <gpu_name> <num_gpus> <image> [geolocation] [disk_space]",
    help="Launch the top instance from the search offers based on the given parameters",
    epilog=deindent("""
        Launches an instance based on the given parameters.

        Examples:
            python vast.py launch instance -g RTX_3090 -n 1 -i pytorch/pytorch
            python vast.py launch instance -g RTX_3090 -n 4 -i pytorch/pytorch -d 32.0 -r North_America
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
