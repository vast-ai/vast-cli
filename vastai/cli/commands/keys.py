"""CLI commands for managing API keys and SSH keys."""

import json
import os

from vastai.cli.parser import argument
from vastai.cli.display import deindent
from vastai.api import keys as keys_api


from vastai.cli.utils import get_parser as _get_parser, get_client  # noqa: F401


parser = _get_parser()


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------

@parser.command(
    argument("--name", help="name of the api-key", type=str),
    argument("--permission_file", help="file path for json encoded permissions, see https://vast.ai/docs/cli/roles-and-permissions for more information", type=str),
    argument("--key_params", help="optional wildcard key params for advanced keys", type=str),
    usage="vastai create api-key --name NAME --permission_file PERMISSIONS",
    help="Create a new api-key with restricted permissions. Can be sent to other users and teammates",
    epilog=deindent("""
        In order to create api keys you must understand how permissions must be sent via json format.
        You can find more information about permissions here: https://vast.ai/docs/cli/roles-and-permissions
    """)
)
def create__api_key(args):
    """Create a new api-key with restricted permissions."""
    from vastai.cli.util import load_permissions_from_file
    try:
        client = get_client(args)
        permissions = load_permissions_from_file(args.permission_file)
        result = keys_api.create_api_key(client, name=args.name, permissions=permissions, key_params=args.key_params)
        print("api-key created {}".format(result))
    except FileNotFoundError:
        print("Error: Permission file '{}' not found.".format(args.permission_file))
    except Exception as e:
        print("An unexpected error occurred:", e)


@parser.command(
    argument("id", help="id of apikey to get", type=int),
    usage="vastai show api-key",
    help="Show an api-key",
)
def show__api_key(args):
    """Show an api-key."""
    client = get_client(args)
    result = keys_api.show_api_key(client, id=args.id)
    print(result)


@parser.command(
    usage="vastai show api-keys",
    help="List your api-keys associated with your account",
)
def show__api_keys(args):
    """List api-keys associated with your account."""
    client = get_client(args)
    result = keys_api.show_api_keys(client)
    if args.raw:
        return result
    else:
        print(result)


@parser.command(
    argument("id", help="id of apikey to remove", type=int),
    usage="vastai delete api-key ID",
    help="Remove an api-key",
)
def delete__api_key(args):
    """Remove an api-key."""
    client = get_client(args)
    result = keys_api.delete_api_key(client, id=args.id)
    print(result)


@parser.command(
    usage="vastai reset api-key",
    help="Reset your api-key (get new key from website)",
)
def reset__api_key(args):
    """Reset your api-key."""
    client = get_client(args)
    rj = keys_api.reset_api_key(client)
    if rj.get("success"):
        print("New api-key: {}".format(rj.get("new_api_key", "")))
    else:
        print(rj.get("msg", "Failed to reset api-key"))


# ---------------------------------------------------------------------------
# SSH keys
# ---------------------------------------------------------------------------

@parser.command(
    argument("ssh_key", help="add your existing ssh public key to your account (from the .pub file). If no public key is provided, a new key pair will be generated.", type=str, nargs='?'),
    argument("-y", "--yes", help="automatically answer yes to prompts", action="store_true"),
    usage="vastai create ssh-key [ssh_public_key] [-y]",
    help="Create a new ssh-key",
    epilog=deindent("""
        You may use this command to add an existing public key, or create a new ssh key pair and add that public key, to your Vast account.

        If you provide an ssh_public_key.pub argument, that public key will be added to your Vast account. All ssh public keys should be in OpenSSH format.

                Example: $vastai create ssh-key 'ssh_public_key.pub'

        If you don't provide an ssh_public_key.pub argument, a new Ed25519 key pair will be generated.

                Example: $vastai create ssh-key

        The generated keys are saved as ~/.ssh/id_ed25519 (private) and ~/.ssh/id_ed25519.pub (public). Any existing id_ed25519 keys are backed up as .backup_<timestamp>.
        The public key will be added to your Vast account.

        All ssh public keys are stored in your Vast account and can be used to connect to instances they've been added to.
    """)
)
def create__ssh_key(args):
    """Create or add an SSH key to your account."""
    from vastai.cli.util import get_ssh_key, generate_ssh_key

    ssh_key_content = args.ssh_key

    if not ssh_key_content:
        ssh_key_content = generate_ssh_key(args.yes)
    else:
        print("Adding provided SSH public key to account...")

    client = get_client(args)
    result = keys_api.create_ssh_key(client, ssh_key=ssh_key_content)
    print("ssh-key created {}\nNote: You may need to add the new public key to any pre-existing instances".format(result))


@parser.command(
    usage="vastai show ssh-keys",
    help="List your ssh keys associated with your account",
)
def show__ssh_keys(args):
    """List ssh keys associated with your account."""
    client = get_client(args)
    result = keys_api.show_ssh_keys(client)
    if args.raw:
        return result
    else:
        print(result)


@parser.command(
    argument("id", help="id ssh key to delete", type=int),
    usage="vastai delete ssh-key ID",
    help="Remove an ssh-key",
)
def delete__ssh_key(args):
    """Remove an ssh-key."""
    client = get_client(args)
    result = keys_api.delete_ssh_key(client, id=args.id)
    print(result)


@parser.command(
    argument("id", help="id of the ssh key to update", type=int),
    argument("ssh_key", help="new public key value", type=str),
    usage="vastai update ssh-key ID SSH_KEY",
    help="Update an existing SSH key",
)
def update__ssh_key(args):
    """Update an existing SSH key."""
    from vastai.cli.util import get_ssh_key

    ssh_key = get_ssh_key(args.ssh_key)
    client = get_client(args)
    result = keys_api.update_ssh_key(client, id=args.id, ssh_key=ssh_key)
    print(result)


# ---------------------------------------------------------------------------
# attach / detach ssh
# ---------------------------------------------------------------------------

@parser.command(
    argument("instance_id", help="id of instance to attach to", type=int),
    argument("ssh_key", help="ssh key to attach to instance", type=str),
    usage="vastai attach ssh instance_id ssh_key",
    help="Attach an ssh key to an instance. This will allow you to connect to the instance with the ssh key",
    epilog=deindent("""
        Attach an ssh key to an instance. This will allow you to connect to the instance with the ssh key.

        Examples:
         vast attach ssh 12371 AAAAB3NzaC1yc2EAAA...
         vast attach ssh 12371 $(cat ~/.ssh/id_rsa.pub)
         vast attach ssh 12371 ~/.ssh/id_rsa.pub

        All examples attaches the ssh key to instance 12371
    """),
)
def attach__ssh(args):
    """Attach an ssh key to an instance."""
    from vastai.cli.util import get_ssh_key

    ssh_key = get_ssh_key(args.ssh_key)
    client = get_client(args)
    result = keys_api.attach_ssh(client, instance_id=args.instance_id, ssh_key=ssh_key)
    print(result)


@parser.command(
    argument("instance_id", help="id of the instance", type=int),
    argument("ssh_key_id", help="id of the key to detach from the instance", type=str),
    usage="vastai detach instance_id ssh_key_id",
    help="Detach an ssh key from an instance",
    epilog=deindent("""
        Example: vastai detach 99999 12345
    """)
)
def detach__ssh(args):
    """Detach an ssh key from an instance."""
    client = get_client(args)
    result = keys_api.detach_ssh(client, instance_id=args.instance_id, ssh_key_id=args.ssh_key_id)
    print(result)
