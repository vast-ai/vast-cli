"""SSH key and API key operations."""
import json
from vastai.api.client import VastClient


def create_ssh_key(client: VastClient, ssh_key: str) -> dict:
    """Add an SSH public key to the account.

    Args:
        client: VastClient instance.
        ssh_key: SSH public key content string.

    Returns:
        Response dict with created key info.
    """
    r = client.post("/ssh/", json_data={"ssh_key": ssh_key})
    r.raise_for_status()
    return r.json()


def show_ssh_keys(client: VastClient) -> dict:
    """List SSH keys associated with the account.

    Args:
        client: VastClient instance.

    Returns:
        Response dict with SSH key info.
    """
    r = client.get("/ssh/")
    r.raise_for_status()
    return r.json()


def update_ssh_key(client: VastClient, id: int, ssh_key: str) -> dict:
    """Update an existing SSH key.

    Args:
        client: VastClient instance.
        id: SSH key ID.
        ssh_key: New SSH public key content string.

    Returns:
        Response dict.
    """
    payload = {
        "id": id,
        "ssh_key": ssh_key,
    }
    r = client.put(f"/ssh/{id}/", json_data=payload)
    r.raise_for_status()
    return r.json()


def delete_ssh_key(client: VastClient, id: int) -> dict:
    """Delete an SSH key from the account.

    Args:
        client: VastClient instance.
        id: SSH key ID to delete.

    Returns:
        Response dict.
    """
    r = client.delete(f"/ssh/{id}/")
    r.raise_for_status()
    return r.json()


def attach_ssh(client: VastClient, instance_id: int, ssh_key: str) -> dict:
    """Attach an SSH key to an instance.

    Args:
        client: VastClient instance.
        instance_id: Instance ID to attach the key to.
        ssh_key: SSH public key content string.

    Returns:
        Response dict.
    """
    r = client.post(f"/instances/{instance_id}/ssh/", json_data={"ssh_key": ssh_key})
    r.raise_for_status()
    return r.json()


def detach_ssh(client: VastClient, instance_id: int, ssh_key_id: str) -> dict:
    """Detach an SSH key from an instance.

    Args:
        client: VastClient instance.
        instance_id: Instance ID.
        ssh_key_id: SSH key ID to detach.

    Returns:
        Response dict.
    """
    r = client.delete(f"/instances/{instance_id}/ssh/{ssh_key_id}/")
    r.raise_for_status()
    return r.json()


def parse_key_params(key_params):
    """Key parameters as the API takes them: a dict binding the ``$name`` parameters of the permissions.

    Accepts a dict, or the same as a JSON object string (what the CLI flag passes). Raises ValueError for
    anything else, and for a name without the leading ``$``, which would bind nothing.
    """
    if key_params is None:
        return None
    if isinstance(key_params, str):
        try:
            key_params = json.loads(key_params)
        except json.JSONDecodeError as e:
            raise ValueError(f"key_params is not a JSON object: {e}") from e
    if not isinstance(key_params, dict):
        raise ValueError('key_params must be a JSON object, e.g. {"$instance_id": 1234}')
    for name in key_params:
        if not str(name).startswith("$"):
            raise ValueError(f"key_params names start with '$' (got {name!r}), e.g. {{\"$instance_id\": 1234}}")
    return key_params


def create_api_key(client: VastClient, name: str, permissions: dict = None,
                   key_params=None, lifetime_sec: float = None) -> dict:
    """Create a new API key.

    Args:
        client: VastClient instance.
        name: Name for the new API key.
        permissions: Dict of permissions for the key.
        key_params: Optional dict (or JSON object string) binding the ``$name`` parameters the
            permissions mention, e.g. ``{"$instance_id": 1234}``. A key issued from a key keeps the
            issuing key's bindings.
        lifetime_sec: Optional seconds the key lives (60 or more). The key ends no later than the
            key it is issued from. Omit for a key with no expiry of its own.

    Returns:
        Response dict with created API key info, including ``expires_at`` (a Unix time, or None).
    """
    json_blob = {"name": name}
    if permissions is not None:
        json_blob["permissions"] = permissions
    key_params = parse_key_params(key_params)
    if key_params is not None:
        json_blob["key_params"] = key_params
    if lifetime_sec is not None:
        json_blob["lifetime_sec"] = lifetime_sec
    r = client.post("/auth/apikeys/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def show_api_key(client: VastClient, id: int) -> dict:
    """Show details of a specific API key.

    Args:
        client: VastClient instance.
        id: API key ID.

    Returns:
        API key details dict.
    """
    r = client.get(f"/auth/apikeys/{id}/")
    r.raise_for_status()
    return r.json()


def show_api_keys(client: VastClient) -> dict:
    """List all API keys associated with the account.

    Args:
        client: VastClient instance.

    Returns:
        Envelope dict of the form ``{"apikeys": [...]}`` (what the backend
        sends). The high-level ``VastAI.show_api_keys`` wrapper unwraps this
        to a plain list.
    """
    r = client.get("/auth/apikeys/")
    r.raise_for_status()
    return r.json()


def delete_api_key(client: VastClient, id: int) -> dict:
    """Delete an API key.

    Args:
        client: VastClient instance.
        id: API key ID to delete.

    Returns:
        Response dict.
    """
    r = client.delete(f"/auth/apikeys/{id}/")
    r.raise_for_status()
    return r.json()


def reset_api_key(client: VastClient) -> dict:
    """Reset the current API key (generates a new one).

    Args:
        client: VastClient instance.

    Returns:
        Response dict.
    """
    json_blob = {"client_id": "me"}
    r = client.put("/commands/reset_apikey/", json_data=json_blob)
    r.raise_for_status()
    return r.json()
