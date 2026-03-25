"""Team CRUD operations, members, and roles."""
from vastai.api.client import VastClient


def create_team(client: VastClient, team_name: str) -> dict:
    """Create a new team.

    Args:
        client: VastClient instance.
        team_name: Name of the team to create.

    Returns:
        Response dict with team info.
    """
    r = client.post("/team/", json_data={"team_name": team_name})
    r.raise_for_status()
    return r.json()


def destroy_team(client: VastClient) -> dict:
    """Destroy the current team.

    Args:
        client: VastClient instance.

    Returns:
        Response dict.
    """
    r = client.delete("/team/")
    r.raise_for_status()
    return r.json()


def show_members(client: VastClient) -> dict:
    """Show members of the current team.

    Args:
        client: VastClient instance.

    Returns:
        Response dict with member info.
    """
    r = client.get("/team/members/")
    r.raise_for_status()
    return r.json()


def invite_member(client: VastClient, email: str, role: str) -> dict:
    """Invite a member to the current team.

    Args:
        client: VastClient instance.
        email: Email address of the member to invite.
        role: Role to assign to the invited member.

    Returns:
        Response dict.
    """
    r = client.post("/team/invite/", query_args={"email": email, "role": role})
    r.raise_for_status()
    return r.json()


def remove_member(client: VastClient, id: int) -> dict:
    """Remove a member from the current team.

    Args:
        client: VastClient instance.
        id: Member ID to remove.

    Returns:
        Response dict.
    """
    r = client.delete(f"/team/members/{id}/")
    r.raise_for_status()
    return r.json()


def create_team_role(client: VastClient, name: str, permissions: dict) -> dict:
    """Add a new role to the current team.

    Args:
        client: VastClient instance.
        name: Name of the role.
        permissions: Dict of permissions for the role.

    Returns:
        Response dict.
    """
    r = client.post("/team/roles/", json_data={"name": name, "permissions": permissions})
    r.raise_for_status()
    return r.json()


def show_team_role(client: VastClient, name: str) -> dict:
    """Show details of a specific team role.

    Args:
        client: VastClient instance.
        name: Name of the role.

    Returns:
        Role details dict.
    """
    r = client.get(f"/team/roles/{name}/")
    r.raise_for_status()
    return r.json()


def show_team_roles(client: VastClient) -> dict:
    """Show all roles for the current team.

    Args:
        client: VastClient instance.

    Returns:
        Response dict with roles info.
    """
    r = client.get("/team/roles-full/")
    r.raise_for_status()
    return r.json()


def update_team_role(client: VastClient, id: int, name: str = None,
                     permissions: dict = None) -> dict:
    """Update an existing team role.

    Args:
        client: VastClient instance.
        id: Role ID.
        name: New name for the role.
        permissions: Updated permissions dict.

    Returns:
        Response dict.
    """
    json_blob = {}
    if name is not None:
        json_blob["name"] = name
    if permissions is not None:
        json_blob["permissions"] = permissions
    r = client.put(f"/team/roles/{id}/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def remove_team_role(client: VastClient, name: str) -> dict:
    """Remove a role from the current team.

    Args:
        client: VastClient instance.
        name: Name of the role to remove.

    Returns:
        Response dict.
    """
    r = client.delete(f"/team/roles/{name}/")
    r.raise_for_status()
    return r.json()


def transfer_credit(client: VastClient, recipient: str, amount: float) -> dict:
    """Transfer credit to another account.

    Args:
        client: VastClient instance.
        recipient: Recipient identifier (email or user ID).
        amount: Amount of credit to transfer.

    Returns:
        Response dict.
    """
    json_blob = {
        "sender": "me",
        "recipient": recipient,
        "amount": amount,
    }
    r = client.put("/commands/transfer_credit/", json_data=json_blob)
    r.raise_for_status()
    return r.json()
