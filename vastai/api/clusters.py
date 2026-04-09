"""Cluster and overlay network API functions for the Vast.ai SDK."""


def show_clusters(client):
    """Show clusters associated with your account.

    GET /clusters/

    Args:
        client: VastClient instance.

    Returns:
        dict: Cluster data including nodes, subnets, and manager info.
    """
    r = client.get("/clusters/")
    r.raise_for_status()
    return r.json()


def create_cluster(client, subnet, manager_id):
    """Create a Vast cluster.

    POST /cluster/

    Args:
        client: VastClient instance.
        subnet (str): Local subnet for cluster (e.g. '0.0.0.0/24').
        manager_id (int): Machine ID of manager node. Must already exist.

    Returns:
        dict: API response data.
    """
    json_blob = {
        "subnet": subnet,
        "manager_id": manager_id,
    }

    r = client.post("/cluster/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def delete_cluster(client, cluster_id):
    """Delete a Vast cluster.

    DELETE /cluster/

    Args:
        client: VastClient instance.
        cluster_id (int): ID of cluster to delete.

    Returns:
        dict: API response data.
    """
    json_blob = {"cluster_id": cluster_id}
    r = client.delete("/cluster/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def join_cluster(client, cluster_id, machine_ids):
    """Join machine(s) to a cluster.

    PUT /cluster/

    Args:
        client: VastClient instance.
        cluster_id (int): ID of cluster to join.
        machine_ids (list[int]): Machine IDs to join to the cluster.

    Returns:
        dict: API response data.
    """
    json_blob = {
        "cluster_id": cluster_id,
        "machine_ids": machine_ids,
    }

    r = client.put("/cluster/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def remove_machine_from_cluster(client, cluster_id, machine_id, new_manager_id=None):
    """Remove a machine from a cluster.

    DELETE /cluster/remove_machine/

    If removing the manager node, a new_manager_id must be specified.

    Args:
        client: VastClient instance.
        cluster_id (int): ID of cluster.
        machine_id (int): ID of machine to remove.
        new_manager_id (int, optional): ID of machine to promote to manager.
            Must already be in the cluster.

    Returns:
        dict: API response data.
    """
    json_blob = {
        "cluster_id": cluster_id,
        "machine_id": machine_id,
    }
    if new_manager_id is not None:
        json_blob["new_manager_id"] = new_manager_id

    r = client.delete("/cluster/remove_machine/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def show_overlays(client):
    """Show overlays associated with your account.

    GET /overlay/

    Args:
        client: VastClient instance.

    Returns:
        list: Overlay network data including instances and subnets.
    """
    r = client.get("/overlay/")
    r.raise_for_status()
    return r.json()


def create_overlay(client, cluster_id, name):
    """Create an overlay network on top of a physical cluster.

    POST /overlay/

    Args:
        client: VastClient instance.
        cluster_id (int): ID of cluster to create overlay on.
        name (str): Overlay network name.

    Returns:
        dict: API response data.
    """
    json_blob = {
        "cluster_id": cluster_id,
        "name": name,
    }

    r = client.post("/overlay/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def delete_overlay(client, overlay_identifier):
    """Delete an overlay and remove all associated instances.

    DELETE /overlay/

    Args:
        client: VastClient instance.
        overlay_identifier: ID (int) or name (str) of overlay to delete.

    Returns:
        dict: API response data.
    """
    try:
        overlay_id = int(overlay_identifier)
        json_blob = {"overlay_id": overlay_id}
    except (ValueError, TypeError):
        json_blob = {"overlay_name": overlay_identifier}

    r = client.delete("/overlay/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def join_overlay(client, name, instance_id):
    """Add an instance to an overlay network.

    PUT /overlay/

    Args:
        client: VastClient instance.
        name (str): Overlay network name to join.
        instance_id (int): Instance ID to add to the overlay.

    Returns:
        dict: API response data.
    """
    json_blob = {
        "name": name,
        "instance_id": instance_id,
    }

    r = client.put("/overlay/", json_data=json_blob)
    r.raise_for_status()
    return r.json()
