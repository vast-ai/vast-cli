"""CLI commands for miscellaneous operations (execute, logs, reports, ssh/scp urls, snapshots, templates, self-test).

Note: create/update/delete template commands are registered in offers.py.
      self_test__machine is registered in machines.py.
"""

import json
import re
import time
import subprocess
import argparse
import os
import requests as req_lib

from vastai.cli.parser import argument
from vastai.cli.display import deindent
from vastai.cli.util import (
    default_start_date, default_end_date,
    parse_day_cron_style, parse_hour_cron_style,
    validate_frequency_values, add_scheduled_job,
)
from vastai.api import instances as instances_api
from vastai.api import machines as machines_api


from vastai.cli.utils import get_parser as _get_parser, get_client  # noqa: F401


parser = _get_parser()


# ---------------------------------------------------------------------------
# execute
# ---------------------------------------------------------------------------

@parser.command(
    argument("id", help="id of instance to execute on", type=int),
    argument("COMMAND", help="bash command surrounded by single quotes", type=str),
    argument("--schedule", choices=["HOURLY", "DAILY", "WEEKLY"], help="try to schedule a command to run hourly, daily, or weekly. Valid values are HOURLY, DAILY, WEEKLY  For ex. --schedule DAILY"),
    argument("--start_date", type=str, default=default_start_date(), help="Start date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is now. (optional)"),
    argument("--end_date", type=str, default=default_end_date(), help="End date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is 7 days from now. (optional)"),
    argument("--day", type=parse_day_cron_style, help="Day of week you want scheduled job to run on (0-6, where 0=Sunday) or \"*\". Default will be 0. For ex. --day 0", default=0),
    argument("--hour", type=parse_hour_cron_style, help="Hour of day you want scheduled job to run on (0-23) or \"*\" (UTC). Default will be 0. For ex. --hour 16", default=0),
    usage="vastai execute id COMMAND",
    help="Execute a (constrained) remote command on a machine",
    epilog=deindent("""
        Examples:
          vastai execute 99999 'ls -l -o -r'
          vastai execute 99999 'rm -r home/delete_this.txt'
          vastai execute 99999 'du -d2 -h'

        available commands:
          ls                 List directory contents
          rm                 Remote files or directories
          du                 Summarize device usage for a set of files

        Return value:
        Returns the output of the command which was executed on the instance, if successful. May take a few seconds to retrieve the results.

    """),
)
def execute(args):
    """Execute a (constrained) remote command on a machine."""
    json_blob = {"command": args.COMMAND}
    if args.explain:
        print("request json: ")
        print(json_blob)

    client = get_client(args)
    rj = instances_api.execute(client, id=args.id, command=args.COMMAND)

    if args.schedule:
        validate_frequency_values(args.day, args.hour, args.schedule)
        cli_command = "execute"
        api_endpoint = "/api/v0/instances/command/{id}/".format(id=args.id)
        json_blob["instance_id"] = args.id
        add_scheduled_job(client, args, json_blob, cli_command, api_endpoint, "PUT", instance_id=args.id)
        return

    if rj.get("success"):
        for i in range(0, 30):
            time.sleep(0.3)
            url = rj["result_url"]
            r2 = req_lib.get(url)
            if r2.status_code == 200:
                filtered_text = r2.text.replace(rj["writeable_path"], '')
                print(filtered_text)
                break
    else:
        print(rj)


# ---------------------------------------------------------------------------
# logs
# ---------------------------------------------------------------------------

@parser.command(
    argument("INSTANCE_ID", help="id of instance", type=int),
    argument("--tail", help="Number of lines to show from the end of the logs (default '1000')", type=str),
    argument("--filter", help="Grep filter for log entries", type=str),
    argument("--daemon-logs", help="Fetch daemon system logs instead of container logs", action="store_true"),
    usage="vastai logs INSTANCE_ID [OPTIONS] ",
    help="Get the logs for an instance",
)
def logs(args):
    """Get the logs for an instance."""
    if args.explain:
        print("request json: ")
        json_blob = {}
        if args.filter:
            json_blob['filter'] = args.filter
        if args.tail:
            json_blob['tail'] = args.tail
        if args.daemon_logs:
            json_blob['daemon_logs'] = 'true'
        print(json_blob)

    client = get_client(args)
    rj = instances_api.logs(client, instance_id=args.INSTANCE_ID, tail=args.tail,
                            filter=args.filter, daemon_logs=args.daemon_logs)

    if rj.get("result_url"):
        for i in range(0, 30):
            time.sleep(0.3)
            url = rj["result_url"]
            print(f"waiting on logs for instance {args.INSTANCE_ID} fetching from {url}")
            r2 = req_lib.get(url)
            if r2.status_code == 200:
                result = r2.text
                cleaned_text = re.sub(r'\n\s*\n', '\n', result)
                print(cleaned_text)
                break
        else:
            print(rj.get("msg", "Timed out waiting for logs"))
    else:
        print(rj.get("msg", rj))


# ---------------------------------------------------------------------------
# reports
# ---------------------------------------------------------------------------

@parser.command(
    argument("id", help="machine id", type=int),
    usage="vastai reports ID",
    help="Get the user reports for a given machine",
)
def reports(args):
    """Get the user reports for a given machine."""
    if args.explain:
        print("request json: ")
        print({"machine_id": args.id})

    client = get_client(args)
    result = machines_api.reports(client, id=args.id)
    print(f"reports: {json.dumps(result, indent=2)}")


# ---------------------------------------------------------------------------
# ssh-url / scp-url
# ---------------------------------------------------------------------------

@parser.command(
    argument("id", help="id of instance", type=int),
    usage="vastai ssh-url ID",
    help="ssh url helper",
)
def ssh_url(args):
    """Get the SSH URL for an instance."""
    return _ssh_url(args, "ssh://")


@parser.command(
    argument("id", help="id", type=int),
    usage="vastai scp-url ID",
    help="scp url helper",
)
def scp_url(args):
    """Get the SCP URL for an instance."""
    return _ssh_url(args, "scp://")


def _ssh_url(args, protocol):
    """Internal helper for ssh/scp URL generation."""
    from vastai.cli.util import DIRS

    json_object = None

    # Try reading cached SSH info
    try:
        with open(f"{DIRS['temp']}/ssh_{args.id}.json", 'r') as openfile:
            json_object = json.load(openfile)
    except Exception:
        pass

    port = None
    ipaddr = None

    if json_object is not None:
        ipaddr = json_object["ipaddr"]
        port = json_object["port"]

    if ipaddr is None or ipaddr.endswith('.vast.ai'):
        client = get_client(args)
        rows = instances_api.show_instances(client)

        if args.id:
            matches = [row for row in rows if row['id'] == args.id]
            if not matches:
                print(f"error: no instance found with id {args.id}")
                return 1
            instance = matches[0]
        elif len(rows) > 1:
            print("Found multiple running instances")
            return 1
        else:
            instance = rows[0]

        ports = instance.get("ports", {})
        port_22d = ports.get("22/tcp", None)
        port = -1
        try:
            if port_22d is not None:
                ipaddr = instance["public_ipaddr"]
                port = int(port_22d[0]["HostPort"])
            else:
                ipaddr = instance["ssh_host"]
                port = int(instance["ssh_port"]) + 1 if "jupyter" in instance["image_runtype"] else int(instance["ssh_port"])
        except Exception:
            port = -1

    if port > 0:
        print(f'{protocol}root@{ipaddr}:{port}')
    else:
        print('error: ssh port not found')

    # Cache SSH info
    try:
        with open(f"{DIRS['temp']}/ssh_{args.id}.json", "w") as outfile:
            json.dump({"ipaddr": ipaddr, "port": port}, outfile)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# take snapshot
# ---------------------------------------------------------------------------

@parser.command(
    argument("instance_id", help="instance_id of the container instance to snapshot", type=str),
    argument("--container_registry", help="Container registry to push the snapshot to. Default will be docker.io", type=str, default="docker.io"),
    argument("--repo", help="repo to push the snapshot to", type=str),
    argument("--docker_login_user", help="Username for container registry with repo", type=str),
    argument("--docker_login_pass", help="Password or token for container registry with repo", type=str),
    argument("--pause", help="Pause container's processes being executed by the CPU to take snapshot (true/false). Default will be true", type=str, default="true"),
    usage="vastai take snapshot INSTANCE_ID "
          "--repo REPO --docker_login_user USER --docker_login_pass PASS"
          "[--container_registry REGISTRY] [--pause true|false]",
    help="Schedule a snapshot of a running container and push it to your repo in a container registry",
    epilog=deindent("""
        Takes a snapshot of a running container instance and pushes snapshot to the specified repository in container registry.

        Use pause=true to pause the container during commit (safer but slower),
        or pause=false to leave it running (faster but may produce a less safe snapshot).
    """),
)
def take__snapshot(args):
    """Take a container snapshot and push to registry."""
    instance_id = args.instance_id
    repo = args.repo
    container_registry = args.container_registry
    user = args.docker_login_user
    password = args.docker_login_pass
    pause_flag = args.pause

    print(f"Taking snapshot for instance {instance_id} and pushing to repo {repo} in container registry {container_registry}")

    if args.explain:
        print("Request JSON:")
        print(json.dumps({
            "id": instance_id, "container_registry": container_registry,
            "personal_repo": repo, "docker_login_user": user,
            "docker_login_pass": password, "pause": pause_flag,
        }, indent=2))

    client = get_client(args)
    data = instances_api.take_snapshot(
        client, instance_id=instance_id, repo=repo,
        container_registry=container_registry,
        docker_login_user=user, docker_login_pass=password,
        pause=pause_flag,
    )

    if data.get("success"):
        print(f"Snapshot request sent successfully. Please check your repo {repo} in container registry {container_registry} in 5-10 mins. It can take longer than 5-10 mins to push your snapshot image to your repo depending on the size of your image.")
    else:
        print(data.get("msg", "Unknown error with snapshot request"))



# ---------------------------------------------------------------------------
# Note: create__template, update__template, delete__template are in offers.py.
# Note: self_test__machine is in machines.py.
# ---------------------------------------------------------------------------
