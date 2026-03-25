"""
CLI utility functions and constants for the Vast.ai CLI.

Extracted from vast.py - contains version checking, config directory setup,
constants, and various helper functions used by CLI commands.
"""

from __future__ import unicode_literals, print_function

import re
import json
import sys
import argparse
import os
import time
import math
import subprocess
import shutil
import importlib.metadata
import requests
import getpass
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

# Re-export string_to_unix_epoch so CLI command modules can import from here
from vastai.api.query import string_to_unix_epoch  # noqa: F401


# ---------------------------------------------------------------------------
# PyPI / version constants
# ---------------------------------------------------------------------------

PYPI_BASE_PATH = "https://pypi.org"
# INFO - Change to False if you don't want to check for update each run.
should_check_for_update = False

# Server URL default — canonical definition lives in api/client.py
from vastai.api.client import server_url_default  # noqa: E402, F401

# Sentinel for API key argument default (to distinguish "not provided" from None)
api_key_guard = object()


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------

def parse_version(version: str) -> tuple:
    parts = version.split(".")

    if len(parts) < 3:
        print(f"Invalid version format: {version}", file=sys.stderr)

    return tuple(int(part) for part in parts)


def get_git_version():
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            check=True,
        )
        tag = result.stdout.strip()

        return tag[1:] if tag.startswith("v") else tag
    except Exception:
        return "0.0.0"


def get_pip_version():
    try:
        return importlib.metadata.version("vastai")
    except Exception:
        return "0.0.0"


def is_pip_package():
    try:
        return importlib.metadata.metadata("vastai") is not None
    except Exception:
        return False

def get_update_command(stable_version: str) -> str:
    if is_pip_package():
        if "test.pypi.org" in PYPI_BASE_PATH:
            return f"{sys.executable} -m pip install --force-reinstall --no-cache-dir -i {PYPI_BASE_PATH} vastai=={stable_version}"
        else:
            return f"{sys.executable} -m pip install --force-reinstall --no-cache-dir vastai=={stable_version}"
    else:
        return f"git fetch --all --tags --prune && git checkout tags/v{stable_version}"


def get_local_version():
    if is_pip_package():
        return get_pip_version()
    return get_git_version()


def get_project_data(project_name: str) -> dict:
    url = PYPI_BASE_PATH + f"/pypi/{project_name}/json"
    response = requests.get(url, headers={"Accept": "application/json"})

    # this will raise for HTTP status 4xx and 5xx
    response.raise_for_status()

    # this will raise for HTTP status >200,<=399
    if response.status_code != 200:
        raise Exception(
            f"Could not get PyPi Project: {project_name}. Response: {response.status_code}"
        )

    response_data: dict = response.json()
    return response_data


def get_pypi_version(project_data: dict) -> str:
    info_data = project_data.get("info")

    if not info_data:
        raise Exception("Could not get PyPi Project")

    version_data: str = str(info_data.get("version"))

    return str(version_data)

def check_for_update():
    pypi_data = get_project_data("vastai")
    pypi_version = get_pypi_version(pypi_data)

    local_version = get_local_version()

    local_tuple = parse_version(local_version)
    pypi_tuple = parse_version(pypi_version)

    if local_tuple >= pypi_tuple:
        return

    user_wants_update = input(
        f"Update available from {local_version} to {pypi_version}. Would you like to update [Y/n]: "
    ).lower()

    if user_wants_update not in ["y", ""]:
        print("You selected no. If you don't want to check for updates each time, update should_check_for_update in vast.py")
        return

    update_command = get_update_command(pypi_version)

    print("Updating...")
    _ = subprocess.run(
        update_command,
        shell=True,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    print("Update completed successfully!\nAttempt to run your command again!")
    sys.exit(0)


# ---------------------------------------------------------------------------
# App constants
# ---------------------------------------------------------------------------

APP_NAME = "vastai"
VERSION = get_local_version()

# Define emoji support and fallbacks
_HAS_EMOJI = sys.stdout.encoding and 'utf' in sys.stdout.encoding.lower()
SUCCESS = "\u2705" if _HAS_EMOJI else "[OK]"
WARN    = "\u26a0\ufe0f" if _HAS_EMOJI else "[!]"
FAIL    = "\u274c" if _HAS_EMOJI else "[X]"
INFO    = "\u2139\ufe0f" if _HAS_EMOJI else "[i]"


# ---------------------------------------------------------------------------
# Config directory setup
# ---------------------------------------------------------------------------

try:
    # Although xdg-base-dirs is the newer name, there's
    # python compatibility issues with dependencies that
    # can be unresolvable using things like python 3.9
    # So we actually use the older name, thus older
    # version for now. This is as of now (2024/11/15)
    # the safer option. -cjm
    import xdg

    DIRS = {
        'config': xdg.xdg_config_home(),
        'temp': xdg.xdg_cache_home()
    }

except Exception:
    # Reasonable defaults.
    DIRS = {
        'config': os.path.join(os.getenv('HOME'), '.config'),
        'temp': os.path.join(os.getenv('HOME'), '.cache'),
    }

for key in DIRS.keys():
    DIRS[key] = path = os.path.join(DIRS[key], APP_NAME)
    if not os.path.exists(path):
        os.makedirs(path)

CACHE_FILE = os.path.join(DIRS['temp'], "gpu_names_cache.json")
CACHE_DURATION = timedelta(hours=24)

APIKEY_FILE = os.path.join(DIRS['config'], "vast_api_key")
APIKEY_FILE_HOME = os.path.expanduser("~/.vast_api_key")  # Legacy
TFAKEY_FILE = os.path.join(DIRS['config'], "vast_tfa_key")

if not os.path.exists(APIKEY_FILE) and os.path.exists(APIKEY_FILE_HOME):
    #print(f'copying key from {APIKEY_FILE_HOME} -> {APIKEY_FILE}')
    shutil.copyfile(APIKEY_FILE_HOME, APIKEY_FILE)


# ---------------------------------------------------------------------------
# Simple utility class
# ---------------------------------------------------------------------------

class Object(object):
    pass


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_seconds(value):
    """Validate that the input value is a valid number for seconds between yesterday and Jan 1, 2100."""
    try:
        val = int(value)

        # Calculate min_seconds as the start of yesterday in seconds
        yesterday = datetime.now() - timedelta(days=1)
        min_seconds = int(yesterday.timestamp())

        # Calculate max_seconds for Jan 1st, 2100 in seconds
        max_date = datetime(2100, 1, 1, 0, 0, 0)
        max_seconds = int(max_date.timestamp())

        if not (min_seconds <= val <= max_seconds):
            raise argparse.ArgumentTypeError(f"{value} is not a valid second timestamp.")
        return val
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value} is not a valid integer.")


# ---------------------------------------------------------------------------
# VRL (Vast Resource Locator) parsing
# ---------------------------------------------------------------------------

class VRLException(Exception):
    pass

def parse_vast_url(url_str):
    """
    Breaks up a vast-style url in the form instance_id:path and does
    some basic sanity type-checking.

    :param url_str:
    :return:
    """

    instance_id = None
    path = url_str
    #print(f'url_str: {url_str}')
    if (":" in url_str):
        url_parts = url_str.split(":", 2)
        if len(url_parts) == 2:
            (instance_id, path) = url_parts
        else:
            raise VRLException("Invalid VRL (Vast resource locator).")
    else:
        try:
            instance_id = int(path)
            path = "/"
        except:
            pass

    valid_unix_path_regex = re.compile('^(/)?([^/\0]+(/)?)+$')
    # Got this regex from https://stackoverflow.com/questions/537772/what-is-the-most-correct-regular-expression-for-a-unix-file-path
    if (path != "/") and (valid_unix_path_regex.match(path) is None):
        raise VRLException(f"Path component: {path} of VRL is not a valid Unix style path.")

    #print(f'instance_id: {instance_id}')
    #print(f'path: {path}')
    return (instance_id, path)


# ---------------------------------------------------------------------------
# SSH key helpers
# ---------------------------------------------------------------------------

def get_ssh_key(argstr):
    # Import deindent from display module (avoids circular imports)
    from vastai.cli.display import deindent

    ssh_key = argstr
    # Including a path to a public key is pretty reasonable.
    if os.path.exists(argstr):
        with open(argstr) as f:
            ssh_key = f.read()

    if "PRIVATE KEY" in ssh_key:
        raise ValueError(deindent("""
            \U0001f434 Woah, hold on there, partner!

            That's a *private* SSH key.  You need to give the *public*
            one. It usually starts with 'ssh-rsa', is on a single line,
            has around 200 or so "base64" characters and ends with
            some-user@some-where. "Generate public ssh key" would be
            a good search term if you don't know how to do this.
        """, add_separator=False))

    if not ssh_key.lower().startswith('ssh'):
        raise ValueError(deindent("""
            Are you sure that's an SSH public key?

            Usually it starts with the stanza 'ssh-(keytype)'
            where the keytype can be things such as rsa, ed25519-sk,
            or dsa. What you passed me was:

            {}

            And welp, that just don't look right.
        """.format(ssh_key), add_separator=False))

    return ssh_key


def generate_ssh_key(auto_yes=False):
    """
    Generate a new SSH key pair using ssh-keygen and return the public key content.

    Args:
        auto_yes (bool): If True, automatically answer yes to prompts

    Returns:
        str: The content of the generated public key

    Raises:
        SystemExit: If ssh-keygen is not available or key generation fails
    """

    print("No SSH key provided. Generating a new SSH key pair and adding public key to account...")

    # Define paths
    ssh_dir = Path.home() / '.ssh'
    private_key_path = ssh_dir / 'id_ed25519'
    public_key_path = ssh_dir / 'id_ed25519.pub'

    # Create .ssh directory if it doesn't exist
    try:
        ssh_dir.mkdir(mode=0o700, exist_ok=True)
    except OSError as e:
        print(f"Error creating .ssh directory: {e}", file=sys.stderr)
        sys.exit(1)

    # Check if any part of the key pair already exists and backup if needed
    if private_key_path.exists() or public_key_path.exists():
        print(f"An SSH key pair 'id_ed25519' already exists in {ssh_dir}")
        if auto_yes:
            print("Auto-answering yes to backup existing key pair.")
            response = 'y'
        else:
            response = input("Would you like to generate a new key pair and backup your existing id_ed25519 key pair. [y/N]: ").lower()
        if response not in ['y', 'yes']:
            print("Aborted. No new key generated.")
            sys.exit(0)

        # Generate timestamp for backup
        timestamp = int(time.time())
        backup_private_path = ssh_dir / f'id_ed25519.backup_{timestamp}'
        backup_public_path = ssh_dir / f'id_ed25519.pub.backup_{timestamp}'

        try:
            # Backup existing private key if it exists
            if private_key_path.exists():
                private_key_path.rename(backup_private_path)
                print(f"Backed up existing private key to: {backup_private_path}")

            # Backup existing public key if it exists
            if public_key_path.exists():
                public_key_path.rename(backup_public_path)
                print(f"Backed up existing public key to: {backup_public_path}")

        except OSError as e:
            print(f"Error backing up existing SSH keys: {e}", file=sys.stderr)
            sys.exit(1)

        print("Generating new SSH key pair and adding public key to account...")

    # Check if ssh-keygen is available
    try:
        subprocess.run(['ssh-keygen', '--help'], capture_output=True, check=False)
    except FileNotFoundError:
        print("Error: ssh-keygen not found. Please install OpenSSH client tools.", file=sys.stderr)
        sys.exit(1)

    # Generate the SSH key pair
    try:
        cmd = [
            'ssh-keygen',
            '-t', 'ed25519',       # Ed25519 key type
            '-f', str(private_key_path),  # Output file path
            '-N', '',              # Empty passphrase
            '-C', f'{os.getenv("USER") or os.getenv("USERNAME", "user")}-vast.ai'  # User
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            input='y\n',           # Automatically answer 'yes' to overwrite prompts
            check=True
        )

    except subprocess.CalledProcessError as e:
        print(f"Error generating SSH key: {e}", file=sys.stderr)
        if e.stderr:
            print(f"ssh-keygen error: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error during key generation: {e}", file=sys.stderr)
        sys.exit(1)

    # Set proper permissions for the private key
    try:
        private_key_path.chmod(0o600)  # Read/write for owner only
    except OSError as e:
        print(f"Warning: Could not set permissions for private key: {e}", file=sys.stderr)

    # Read and return the public key content
    try:
        with open(public_key_path, 'r') as f:
            public_key_content = f.read().strip()

        return public_key_content

    except IOError as e:
        print(f"Error reading generated public key: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Environment / Docker option parsing
# ---------------------------------------------------------------------------

def smart_split(s, char):
    in_double_quotes = False
    in_single_quotes = False  # note that isn't designed to work with nested quotes within the env
    parts = []
    current = []

    for c in s:
        if c == char and not (in_double_quotes or in_single_quotes):
            parts.append(''.join(current))
            current = []
        elif c == '\'':
            in_single_quotes = not in_single_quotes
            current.append(c)
        elif c == '\"':
            in_double_quotes = not in_double_quotes
            current.append(c)
        else:
            current.append(c)
    parts.append(''.join(current))  # add last part
    return parts


def parse_env(envs):
    result = {}
    if (envs is None):
        return result
    env = smart_split(envs, ' ')
    prev = None
    for e in env:
        if (prev is None):
            if (e in {"-e", "-p", "-h", "-v", "-n"}):
                prev = e
            else:
                pass
        else:
            if (prev == "-p"):
                if set(e).issubset(set("0123456789:tcp/udp")):
                    result["-p " + e] = "1"
                else:
                    pass
            elif (prev == "-e"):
                kv = e.split('=')
                if len(kv) >= 2:
                    val = kv[1]
                    if len(kv) > 2:
                        val = '='.join(kv[1:])
                    result[kv[0]] = val.strip("'\"")
                else:
                    pass
            elif (prev == "-v"):
                if (set(e).issubset(set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:./_"))):
                    result["-v " + e] = "1"
            elif (prev == "-n"):
                if (set(e).issubset(set("abcdefghijklmnopqrstuvwxyz0123456789-"))):
                    result["-n " + e] = "1"
            else:
                result[prev] = e
            prev = None
    return result


# ---------------------------------------------------------------------------
# List / threading helpers
# ---------------------------------------------------------------------------

def split_list(lst, k):
    """
    Splits a list into sublists of maximum size k.
    """
    return [lst[i:i + k] for i in range(0, len(lst), k)]


def exec_with_threads(f, args, nt=16, max_retries=5):
    def worker(sub_args):
        for arg in sub_args:
            retries = 0
            while retries <= max_retries:
                try:
                    result = None
                    if isinstance(arg, tuple):
                        result = f(*arg)
                    else:
                        result = f(arg)
                    if result:  # Assuming a truthy return value means success
                        break
                except Exception as e:
                    print(str(e))
                    pass
                retries += 1
                stime = 0.25 * 1.3 ** retries
                print(f"retrying in {stime}s")
                time.sleep(stime)  # Exponential backoff

    # Split args into nt sublists
    args_per_thread = math.ceil(len(args) / nt)
    sublists = [args[i:i + args_per_thread] for i in range(0, len(args), args_per_thread)]

    with ThreadPoolExecutor(max_workers=nt) as executor:
        executor.map(worker, sublists)


# ---------------------------------------------------------------------------
# Date / scheduling helpers
# ---------------------------------------------------------------------------

def default_start_date():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def default_end_date():
    return (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")

def convert_timestamp_to_date(unix_timestamp):
    utc_datetime = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
    return utc_datetime.strftime("%Y-%m-%d")

def parse_day_cron_style(value):
    """
    Accepts an integer string 0-6 or '*' to indicate 'Every day'.
    Returns 0-6 as int, or None if '*'.
    """
    val = str(value).strip()
    if val == "*":
        return None
    try:
        day = int(val)
        if 0 <= day <= 6:
            return day
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("Day must be 0-6 (0=Sunday) or '*' for every day.")

def parse_hour_cron_style(value):
    """
    Accepts an integer string 0-23 or '*' to indicate 'Every hour'.
    Returns 0-23 as int, or None if '*'.
    """
    val = str(value).strip()
    if val == "*":
        return None
    try:
        hour = int(val)
        if 0 <= hour <= 23:
            return hour
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("Hour must be 0-23 or '*' for every hour.")

def convert_dates_to_timestamps(args):
    selector_flag = ""
    end_timestamp = time.time()
    start_timestamp = time.time() - (24*60*60)
    start_date_txt = ""
    end_date_txt = ""

    import dateutil
    from dateutil import parser

    if args.end_date:
        try:
            end_date = dateutil.parser.parse(str(args.end_date))
            end_date_txt = end_date.isoformat()
            end_timestamp = time.mktime(end_date.timetuple())
        except ValueError as e:
            print(f"Warning: Invalid end date format! Ignoring end date! \n {str(e)}")

    if args.start_date:
        try:
            start_date = dateutil.parser.parse(str(args.start_date))
            start_date_txt = start_date.isoformat()
            start_timestamp = time.mktime(start_date.timetuple())
        except ValueError as e:
            print(f"Warning: Invalid start date format! Ignoring start date! \n {str(e)}")

    return start_timestamp, end_timestamp

def validate_frequency_values(day_of_the_week, hour_of_the_day, frequency):

    # Helper to raise an error with a consistent message.
    def raise_frequency_error():
        msg = ""
        if frequency == "HOURLY":
            msg += "For HOURLY jobs, day and hour must both be \"*\"."
        elif frequency == "DAILY":
            msg += "For DAILY jobs, day must be \"*\" and hour must have a value between 0-23."
        elif frequency == "WEEKLY":
            msg += "For WEEKLY jobs, day must have a value between 0-6 and hour must have a value between 0-23."
        sys.exit(msg)

    if frequency == "HOURLY":
        if not (day_of_the_week is None and hour_of_the_day is None):
            raise_frequency_error()
    if frequency == "DAILY":
        if not (day_of_the_week is None and hour_of_the_day is not None):
            raise_frequency_error()
    if frequency == "WEEKLY":
        if not (day_of_the_week is not None and hour_of_the_day is not None):
            raise_frequency_error()


def add_scheduled_job(client, args, req_json, cli_command, api_endpoint, request_method, instance_id, contract_end_date=None):
    start_timestamp, end_timestamp = convert_dates_to_timestamps(args)
    if args.end_date is None:
        end_timestamp = contract_end_date
        args.end_date = convert_timestamp_to_date(contract_end_date)

    if start_timestamp >= end_timestamp:
        raise ValueError("--start_date must be less than --end_date.")

    day, hour, frequency = args.day, args.hour, args.schedule

    request_body = {
        "start_time": start_timestamp,
        "end_time": end_timestamp,
        "api_endpoint": api_endpoint,
        "request_method": request_method,
        "request_body": req_json,
        "day_of_the_week": day,
        "hour_of_the_day": hour,
        "frequency": frequency,
        "instance_id": instance_id
    }

    response = client.post("/commands/schedule_job/", json_data=request_body)

    if args.explain:
        print("request json: ")
        print(request_body)

    if response.status_code == 200:
        print(f"add_scheduled_job insert: success - Scheduling {frequency} job to {cli_command} from {args.start_date} UTC to {args.end_date} UTC")
    elif response.status_code == 401:
        print(f"add_scheduled_job insert: failed status_code: {response.status_code}. It could be because you aren't using a valid api_key.")
    elif response.status_code == 422:
        user_input = input("Existing scheduled job found. Do you want to update it (y|n)? ")
        if user_input.strip().lower() == "y":
            scheduled_job_id = response.json()["scheduled_job_id"]
            response = update_scheduled_job(client, cli_command, f"/commands/schedule_job/{scheduled_job_id}/", frequency, args.start_date, args.end_date, request_body)
        else:
            print("Job update aborted by the user.")
    else:
        print(f"add_scheduled_job insert: failed error: {response.status_code}. Response body: {response.text}")

def update_scheduled_job(client, cli_command, schedule_job_path, frequency, start_date, end_date, request_body):
    response = client.put(schedule_job_path, json_data=request_body)

    response.raise_for_status()
    if response.status_code == 200:
        print(f"add_scheduled_job update: success - Scheduling {frequency} job to {cli_command} from {start_date} UTC to {end_date} UTC")
        print(response.json())
    elif response.status_code == 401:
        print(f"add_scheduled_job update: failed status_code: {response.status_code}. It could be because you aren't using a valid api_key.")
    else:
        print(f"add_scheduled_job update: failed status_code: {response.status_code}.")
        print(response.json())

    return response


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

def load_permissions_from_file(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)


# ---------------------------------------------------------------------------
# Instance creation helpers
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
        raise argparse.ArgumentTypeError("Error: --volume-size can only be used with --create-volume. Please specify a volume ask ID to create a new volume of that size.")
    if (args.create_volume or args.link_volume) and not args.mount_path:
        raise argparse.ArgumentTypeError("Error: --mount-path is required when creating or linking a volume.")

    # This regex matches absolute or relative Linux file paths (no null bytes)
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
    elif args.create_volume:  # If creating a new volume and size is not passed in, default size is 15GB
        volume_info["size"] = 15

    return volume_info

def validate_portal_config(json_blob):
    # jupyter runtypes already self-correct
    if 'jupyter' in json_blob['runtype']:
        return

    # remove jupyter configs from portal_config if not a jupyter runtype
    portal_config = json_blob['env']['PORTAL_CONFIG'].split("|")
    filtered_config = [config_str for config_str in portal_config if 'jupyter' not in config_str.lower()]

    if not filtered_config:
        raise ValueError("Error: env variable PORTAL_CONFIG must contain at least one non-jupyter related config string if runtype is not jupyter")
    else:
        json_blob['env']['PORTAL_CONFIG'] = "|".join(filtered_config)


def get_template_arguments():
    from vastai.cli.parser import argument
    return [
        argument("--name", help="name of the template", type=str),
        argument("--image", help="docker container image to launch", type=str),
        argument("--image_tag", help="docker image tag (can also be appended to end of image_path)", type=str),
        argument("--href", help="link you want to provide", type=str),
        argument("--repo", help="link to repository", type=str),
        argument("--login", help="docker login arguments for private repo authentication, surround with ''", type=str),
        argument("--env", help="Contents of the 'Docker options' field", type=str),
        argument("--ssh", help="Launch as an ssh instance type", action="store_true"),
        argument("--jupyter", help="Launch as a jupyter instance instead of an ssh instance", action="store_true"),
        argument("--direct", help="Use (faster) direct connections for jupyter & ssh", action="store_true"),
        argument("--jupyter-dir", help="For runtype 'jupyter', directory in instance to use to launch jupyter. Defaults to image's working directory", type=str),
        argument("--jupyter-lab", help="For runtype 'jupyter', Launch instance with jupyter lab", action="store_true"),
        argument("--onstart-cmd", help="contents of onstart script as single argument", type=str),
        argument("--search_params", help="search offers filters", type=str),
        argument("-n", "--no-default", action="store_true", help="Disable default search param query args"),
        argument("--disk_space", help="disk storage space, in GB", type=str),
        argument("--readme", help="readme string", type=str),
        argument("--hide-readme", help="hide the readme from users", action="store_true"),
        argument("--desc", help="description string", type=str),
        argument("--public", help="make template available to public", action="store_true"),
    ]
