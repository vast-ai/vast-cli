"""CLI commands for managing deployments."""

from vastai.cli.parser import argument
from vastai.cli.display import display_table, deindent
from vastai.api import deployments as deployments_api

from vastai.cli.utils import get_parser as _get_parser, get_client  # noqa: F401

parser = _get_parser()

deployment_fields = (
    ("id", "ID", "{}", None, True),
    ("name", "Name", "{}", None, True),
    ("tag", "Tag", "{}", None, True),
    ("image", "Image", "{}", None, True),
    ("endpoint_id", "Endpoint", "{}", None, True),
    ("file_hash", "Hash", "{}", None, True),
    ("current_version_id", "Version", "{}", None, True),
    ("ttl", "TTL", "{}", None, True),
    ("created_at", "Created", "{}", None, True),
    ("updated_at", "Updated", "{}", None, True),
)

deployment_detail_fields = (
    ("id", "ID", "{}", None, True),
    ("name", "Name", "{}", None, True),
    ("tag", "Tag", "{}", None, True),
    ("image", "Image", "{}", None, True),
    ("endpoint_id", "Endpoint", "{}", None, True),
    ("endpoint_state", "State", "{}", None, True),
    ("worker_count", "Workers", "{}", None, True),
    ("file_hash", "Hash", "{}", None, True),
    ("s3_key", "S3 Key", "{}", None, True),
    ("current_version_id", "Version", "{}", None, True),
    ("last_healthy_version_id", "Last Healthy", "{}", None, True),
    ("storage", "Storage", "{}", None, True),
    ("ttl", "TTL", "{}", None, True),
    ("created_at", "Created", "{}", None, True),
    ("updated_at", "Updated", "{}", None, True),
)


# ---------------------------------------------------------------------------
# show deployments
# ---------------------------------------------------------------------------

@parser.command(
    argument("-q", "--quiet", action="store_true", help="only display numeric ids"),
    usage="vastai show deployments [OPTIONS]",
    help="Display user's current deployments",
    epilog=deindent("""
        Shows the user's current deployments.

        Examples:
            vastai show deployments
            vastai show deployments --raw
            vastai show deployments -q
    """),
)
def show__deployments(args):
    """Show the user's current deployments."""
    client = get_client(args)
    rows = deployments_api.show_deployments(client)

    if args.quiet:
        for row in rows:
            id = row.get("id", None)
            if id is not None:
                print(id)
    elif args.raw:
        return rows
    else:
        display_table(rows, deployment_fields)


@parser.command(
    argument("id", help="id of deployment to show info for", type=int),
    usage="vastai show deployment ID [OPTIONS]",
    help="Display a single deployment",
    epilog=deindent("""
        Shows detailed info for a single deployment, including endpoint state and worker count.

        Examples:
            vastai show deployment 123
            vastai show deployment 123 --raw
    """),
)
def show__deployment(args):
    """Show details of a single deployment."""
    client = get_client(args)
    result = deployments_api.show_deployment(client, id=args.id)
    if args.raw:
        return result
    if args.quiet:
        print(result.get("id", ""))
    else:
        display_table([result], deployment_detail_fields)


# ---------------------------------------------------------------------------
# delete deployment
# ---------------------------------------------------------------------------

@parser.command(
    argument("id", help="id of deployment to delete", type=int),
    usage="vastai delete deployment ID [OPTIONS]",
    help="Delete a deployment",
    epilog=deindent("""
        Deletes a deployment and its associated endpoint and workergroups.

        Examples:
            vastai delete deployment 123
    """),
)
def delete__deployment(args):
    """Delete a deployment."""
    client = get_client(args)
    rj = deployments_api.delete_deployment(client, id=args.id)

    if args.raw:
        return rj
    elif rj.get("success"):
        print(f"Deleted deployment {args.id}.")
    else:
        print(rj.get("msg", rj))
