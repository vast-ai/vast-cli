"""CLI commands for managing teams."""

import json

from vastai.cli.parser import argument
from vastai.cli.display import deindent
from vastai.api import teams as teams_api


from vastai.cli.utils import get_parser as _get_parser, get_client  # noqa: F401


parser = _get_parser()


# ---------------------------------------------------------------------------
# create / destroy team
# ---------------------------------------------------------------------------

@parser.command(
    argument("--team_name", help="name of the team", type=str),
    usage="vastai create-team --team_name TEAM_NAME",
    help="Create a new team",
    epilog=deindent("""
        Creates a new team under your account.
        Unlike legacy teams, this command does NOT convert your personal account into a team.
    """),
)
def create__team(args):
    """Create a new team."""
    client = get_client(args)
    result = teams_api.create_team(client, team_name=args.team_name)
    print(result)


@parser.command(
    usage="vastai destroy team",
    help="Destroy your team",
)
def destroy__team(args):
    """Destroy your team."""
    client = get_client(args)
    result = teams_api.destroy_team(client)
    print(result)


# ---------------------------------------------------------------------------
# team roles
# ---------------------------------------------------------------------------

@parser.command(
    argument("--name", help="name of the role", type=str),
    argument("--permissions", help="file path for json encoded permissions", type=str),
    usage="vastai create team-role --name NAME --permissions PERMISSIONS",
    help="Add a new role to your team",
)
def create__team_role(args):
    """Create a new team role."""
    from vastai.cli.util import load_permissions_from_file
    client = get_client(args)
    permissions = load_permissions_from_file(args.permissions)
    result = teams_api.create_team_role(client, name=args.name, permissions=permissions)
    print(result)


@parser.command(
    argument("NAME", help="name of the role", type=str),
    usage="vastai show team-role NAME",
    help="Show your team role",
)
def show__team_role(args):
    """Show a specific team role."""
    client = get_client(args)
    result = teams_api.show_team_role(client, name=args.NAME)
    print(json.dumps(result, indent=1, sort_keys=True))


@parser.command(
    usage="vastai show team-roles",
    help="Show roles for a team",
)
def show__team_roles(args):
    """Show all team roles."""
    client = get_client(args)
    result = teams_api.show_team_roles(client)
    if args.raw:
        return result
    else:
        print(result)


@parser.command(
    argument("id", help="id of the role", type=int),
    argument("--name", help="name of the role", type=str),
    argument("--permissions", help="file path for json encoded permissions", type=str),
    usage="vastai update team-role ID --name NAME --permissions PERMISSIONS",
    help="Update an existing team role",
)
def update__team_role(args):
    """Update an existing team role."""
    from vastai.cli.util import load_permissions_from_file
    client = get_client(args)
    permissions = load_permissions_from_file(args.permissions)
    result = teams_api.update_team_role(client, id=args.id, name=args.name, permissions=permissions)
    if args.raw:
        return result
    else:
        print(json.dumps(result, indent=1))


@parser.command(
    argument("NAME", help="name of role to remove", type=str),
    usage="vastai remove team-role NAME",
    help="Remove a role from the team",
)
def remove__team_role(args):
    """Remove a team role."""
    client = get_client(args)
    result = teams_api.remove_team_role(client, name=args.NAME)
    print(result)


# ---------------------------------------------------------------------------
# team members
# ---------------------------------------------------------------------------

@parser.command(
    argument("--email", help="email of user to be invited", type=str),
    argument("--role", help="role of user to be invited", type=str),
    usage="vastai invite member --email EMAIL --role ROLE",
    help="Invite a team member",
)
def invite__member(args):
    """Invite a team member."""
    client = get_client(args)
    result = teams_api.invite_member(client, email=args.email, role=args.role)
    if result:
        print(f"successfully invited {args.email} to your current team")


@parser.command(
    usage="vastai show members",
    help="Show your team members",
)
def show__members(args):
    """Show team members."""
    client = get_client(args)
    result = teams_api.show_members(client)
    if args.raw:
        return result
    else:
        print(result)


@parser.command(
    argument("id", help="id of user to remove", type=int),
    usage="vastai remove member ID",
    help="Remove a member from the team",
)
def remove__member(args):
    """Remove a team member."""
    client = get_client(args)
    result = teams_api.remove_member(client, id=args.id)
    print(result)

