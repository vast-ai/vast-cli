"""Storage, volume, and data transfer API functions for the Vast.ai SDK."""

import time


def copy(client, src_id, dst_id, src_path, dst_path):
    """Copy directories between instances.

    PUT /commands/copy_direct/ (remote-to-remote) or
    PUT /commands/rsync/ (when one side is local/None)

    Args:
        client: VastClient instance.
        src_id: Source instance ID (or None/\"local\" for local).
        dst_id: Destination instance ID (or None/\"local\" for local).
        src_path (str): Source path.
        dst_path (str): Destination path.

    Returns:
        dict: API response data.
    """
    req_json = {
        "client_id": "me",
        "src_id": src_id,
        "dst_id": dst_id,
        "src_path": src_path,
        "dst_path": dst_path,
    }

    if src_id is None or dst_id is None:
        r = client.put("/commands/rsync/", json_data=req_json)
    else:
        r = client.put("/commands/copy_direct/", json_data=req_json)

    r.raise_for_status()
    return r.json()


def cancel_copy(client, dst_id):
    """Cancel a remote copy in progress.

    DELETE /commands/copy_direct/

    Args:
        client: VastClient instance.
        dst_id: ID of copy destination to cancel.

    Returns:
        dict: API response data.
    """
    req_json = {"client_id": "me", "dst_id": dst_id}
    r = client.delete("/commands/copy_direct/", json_data=req_json)
    r.raise_for_status()
    return r.json()


def cancel_sync(client, dst_id):
    """Cancel a remote cloud sync in progress.

    DELETE /commands/rclone/

    Args:
        client: VastClient instance.
        dst_id: ID of cloud sync destination to cancel.

    Returns:
        dict: API response data.
    """
    req_json = {"client_id": "me", "dst_id": dst_id}
    r = client.delete("/commands/rclone/", json_data=req_json)
    r.raise_for_status()
    return r.json()


def cloud_copy(client, src, dst, instance, connection, transfer, flags=None):
    """Copy files/folders to and from cloud providers.

    POST /commands/rclone/

    Args:
        client: VastClient instance.
        src (str): Path to source of object to copy.
        dst (str): Path to target of copy operation. Default \"/workspace\".
        instance (str): ID of the instance.
        connection (str): ID of cloud connection on your account.
        transfer (str): Type of transfer (e.g. \"Instance to Cloud\",
            \"Cloud to Instance\").
        flags (list, optional): Additional rclone flags such as
            [\"--dry-run\", \"--size-only\", \"--ignore-existing\",
            \"--update\", \"--delete-excluded\"].

    Returns:
        dict: API response data.
    """
    req_json = {
        "src": src,
        "dst": dst,
        "instance_id": instance,
        "selected": connection,
        "transfer": transfer,
        "flags": flags or [],
    }

    r = client.post("/commands/rclone/", json_data=req_json)
    r.raise_for_status()
    return r.json()


def clone_volume(client, source, dest, size=None, disable_compression=False):
    """Clone a volume to another volume.

    POST /volumes/copy/

    Args:
        client: VastClient instance.
        source: Source volume ID.
        dest: Destination volume ID.
        size (float, optional): Size in GB for destination volume.
        disable_compression (bool): Disable compression during clone.
            Default False.

    Returns:
        dict: API response data.
    """
    json_blob = {
        "src_id": source,
        "dst_id": dest,
    }
    if size is not None:
        json_blob["size"] = size
    if disable_compression:
        json_blob["disable_compression"] = True

    r = client.post("/volumes/copy/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def show_volumes(client, type="all"):
    """Show stats on owned volumes.

    GET /volumes

    Args:
        client: VastClient instance.
        type (str): Volume type to display. Options: \"local\", \"network\",
            \"all\". Default \"all\".

    Returns:
        list: Volume data with computed duration field.
    """
    types = {
        "local": "local_volume",
        "network": "network_volume",
        "all": "all_volume",
    }
    vol_type = types.get(type, "all_volume")
    r = client.get("/volumes", query_args={"owner": "me", "type": vol_type})
    r.raise_for_status()
    rows = r.json()["volumes"]
    processed = []
    for row in rows:
        row['duration'] = time.time() - row['start_date']
        processed.append(row)
    return processed


def create_volume(client, id, size=15, name=None):
    """Create a new volume.

    PUT /volumes/

    Args:
        client: VastClient instance.
        id (int): ID of volume offer.
        size (float): Size in GB. Default 15.
        name (str, optional): Optional name of volume.

    Returns:
        dict: API response data.
    """
    json_blob = {
        "size": int(size),
        "id": int(id),
    }
    if name:
        json_blob["name"] = name

    r = client.put("/volumes/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def delete_volume(client, id):
    """Delete a volume.

    DELETE /volumes/

    All instances using the volume must be destroyed before deletion.

    Args:
        client: VastClient instance.
        id (int): ID of volume contract.

    Returns:
        dict: API response data.
    """
    r = client.delete("/volumes/", query_args={"id": id})
    r.raise_for_status()
    return r.json()


def list_volume(client, id, size=15, price_disk=0.10, end_date=None):
    """[Host] List disk space for rent as a volume on a machine.

    POST /volumes/

    Args:
        client: VastClient instance.
        id (int): ID of machine to list.
        size (int): Size of disk space in GB. Default 15.
        price_disk (float): Storage price in $/GB/month. Default 0.10.
        end_date (str, optional): Contract offer expiration date
            (unix timestamp or MM/DD/YYYY format).

    Returns:
        dict: API response data.
    """
    json_blob = {
        "size": int(size),
        "machine": int(id),
        "price_disk": float(price_disk),
    }
    if end_date is not None:
        json_blob["end_date"] = end_date

    r = client.post("/volumes/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def list_volumes(client, ids, size=15, price_disk=0.10, end_date=None):
    """[Host] List disk space for rent as volumes on multiple machines.

    POST /volumes/

    Args:
        client: VastClient instance.
        ids (list[int]): IDs of machines to list.
        size (int): Size of disk space in GB. Default 15.
        price_disk (float): Storage price in $/GB/month. Default 0.10.
        end_date (str, optional): Contract offer expiration date
            (unix timestamp or MM/DD/YYYY format).

    Returns:
        dict: API response data.
    """
    json_blob = {
        "size": int(size),
        "machine": [int(mid) for mid in ids],
        "price_disk": float(price_disk),
    }
    if end_date is not None:
        json_blob["end_date"] = end_date

    r = client.post("/volumes/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def unlist_volume(client, id):
    """[Host] Unlist a volume offer.

    POST /volumes/unlist

    Args:
        client: VastClient instance.
        id (int): Volume ID to unlist.

    Returns:
        dict: API response data.
    """
    json_blob = {"id": id}
    r = client.post("/volumes/unlist", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def create_network_volume(client, id, size=15, name=None):
    """Create a new network volume.

    PUT /network_volumes/

    Args:
        client: VastClient instance.
        id (int): ID of network volume offer.
        size (float): Size in GB. Default 15.
        name (str, optional): Optional name of network volume.

    Returns:
        dict: API response data.
    """
    json_blob = {
        "size": int(size),
        "id": int(id),
    }
    if name:
        json_blob["name"] = name

    r = client.put("/network_volumes/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def list_network_volume(client, disk_id, price_disk=0.15, size=15, end_date=None):
    """[Host] List disk space for rent as a network volume.

    POST /network_volumes/

    Args:
        client: VastClient instance.
        disk_id (int): ID of disk to list.
        price_disk (float): Storage price in $/GB/month. Default 0.15.
        size (int): Size of disk space in GB. Default 15.
        end_date (str, optional): Contract offer expiration date.

    Returns:
        dict: API response data.
    """
    json_blob = {
        "disk_id": disk_id,
        "price_disk": price_disk,
        "size": size,
    }
    if end_date is not None:
        json_blob["end_date"] = end_date

    r = client.post("/network_volumes/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def unlist_network_volume(client, id):
    """[Host] Unlist a network volume offer.

    POST /network_volumes/unlist/

    Args:
        client: VastClient instance.
        id (int): ID of network volume offer to unlist.

    Returns:
        dict: API response data.
    """
    json_blob = {"id": id}
    r = client.post("/network_volumes/unlist/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def show_network_disks(client):
    """[Host] Show network disks associated with your account.

    GET /network_disk/

    Args:
        client: VastClient instance.

    Returns:
        dict: Network disk data including cluster and machine info.
    """
    r = client.get("/network_disk/")
    r.raise_for_status()
    return r.json()


def add_network_disk(client, machines, mount_point, disk_id=None):
    """[Host] Add network disk to physical cluster.

    POST /network_disk/

    Args:
        client: VastClient instance.
        machines (list[int]): IDs of machines to add disk to.
        mount_point (str): Mount path of disk to add.
        disk_id (int, optional): ID of network disk to attach to machines.

    Returns:
        dict: API response data including disk_id.
    """
    json_blob = {
        "machines": [int(mid) for mid in machines],
        "mount_point": mount_point,
    }
    if disk_id is not None:
        json_blob["disk_id"] = disk_id

    r = client.post("/network_disk/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def show_connections(client):
    """Display user's cloud connections/integrations.

    GET /users/cloud_integrations/

    Args:
        client: VastClient instance.

    Returns:
        dict/list: Cloud integration data.
    """
    r = client.get("/users/cloud_integrations/")
    r.raise_for_status()
    return r.json()
