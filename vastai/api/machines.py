"""Machine management operations for hosts."""
from vastai.api.client import VastClient


def show_machine(client: VastClient, id: int) -> list:
    """Show a single hosted machine.

    Args:
        client: VastClient instance.
        id: Machine ID.

    Returns:
        List of machine data dicts (API returns list even for single machine).
    """
    r = client.get(f"/machines/{id}", query_args={"owner": "me"})
    r.raise_for_status()
    return r.json()


def show_machines(client: VastClient) -> list:
    """Show all hosted machines for the current user.

    Args:
        client: VastClient instance.

    Returns:
        List of machine dicts.
    """
    r = client.get("/machines", query_args={"owner": "me"})
    r.raise_for_status()
    return r.json()["machines"]


def show_maints(client: VastClient, machine_ids: list) -> list:
    """Show maintenance information for host machines.

    Args:
        client: VastClient instance.
        machine_ids: List of machine ID integers.

    Returns:
        List of maintenance info dicts.
    """
    r = client.get("/machines/maintenances", query_args={"owner": "me", "machine_ids": machine_ids})
    r.raise_for_status()
    return r.json()


def list_machine(client: VastClient, id: int, price_gpu: float = None,
                 price_disk: float = None, price_inetu: float = None,
                 price_inetd: float = None, price_min_bid: float = None,
                 min_chunk: int = None, end_date: float = None,
                 discount_rate: float = None, duration: str = None,
                 vol_size: int = None, vol_price: float = None) -> dict:
    """List a machine for rent (create offers).

    Args:
        client: VastClient instance.
        id: Machine ID.
        price_gpu: Per GPU rental price in $/hour.
        price_disk: Storage price in $/GB/month.
        price_inetu: Price for upload bandwidth in $/GB.
        price_inetd: Price for download bandwidth in $/GB.
        price_min_bid: Per GPU minimum bid price floor in $/hour.
        min_chunk: Minimum number of GPUs.
        end_date: Contract offer expiration as unix epoch timestamp.
        discount_rate: Max long-term prepay discount rate fraction.
        duration: Duration string or seconds.
        vol_size: Volume contract offer size in GB.
        vol_price: Volume disk price.

    Returns:
        Response dict.
    """
    json_blob = {
        "machine": id,
        "price_gpu": price_gpu,
        "price_disk": price_disk,
        "price_inetu": price_inetu,
        "price_inetd": price_inetd,
        "price_min_bid": price_min_bid,
        "min_chunk": min_chunk,
        "end_date": end_date,
        "credit_discount_max": discount_rate,
        "duration": duration,
        "vol_size": vol_size,
        "vol_price": vol_price,
    }
    r = client.put("/machines/create_asks/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def unlist_machine(client: VastClient, id: int) -> dict:
    """Unlist a listed machine (remove all offers).

    Args:
        client: VastClient instance.
        id: Machine ID.

    Returns:
        Response dict.
    """
    r = client.delete(f"/machines/{id}/asks/")
    r.raise_for_status()
    return r.json()


def cancel_maint(client: VastClient, id: int) -> dict:
    """Cancel scheduled maintenance window(s) for a machine.

    Args:
        client: VastClient instance.
        id: Machine ID.

    Returns:
        Response dict.
    """
    json_blob = {"client_id": "me", "machine_id": id}
    r = client.put(f"/machines/{id}/cancel_maint/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def schedule_maint(client: VastClient, id: int, sdate: float = None,
                   duration: float = None, maintenance_category: str = None) -> dict:
    """Schedule a maintenance window for a machine.

    Args:
        client: VastClient instance.
        id: Machine ID.
        sdate: Start date as unix epoch timestamp.
        duration: Duration in hours.
        maintenance_category: Category of maintenance.

    Returns:
        Response dict.
    """
    json_blob = {
        "client_id": "me",
        "sdate": sdate,
        "duration": duration,
        "maintenance_category": maintenance_category,
    }
    r = client.put(f"/machines/{id}/dnotify/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def cleanup_machine(client: VastClient, id: int) -> dict:
    """Remove all expired storage instances from a machine.

    Args:
        client: VastClient instance.
        id: Machine ID.

    Returns:
        Response dict.
    """
    r = client.put(f"/machines/{id}/cleanup/", json_data={})
    r.raise_for_status()
    return r.json()


def defrag_machines(client: VastClient, machine_ids: list) -> dict:
    """Defragment machines to rearrange GPU assignments.

    Args:
        client: VastClient instance.
        machine_ids: List of machine ID integers.

    Returns:
        Response dict with defragmentation results.
    """
    json_blob = {"machine_ids": machine_ids}
    r = client.put("/machines/defrag_offers/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def delete_machine(client: VastClient, id: int) -> dict:
    """Force delete a machine if not in use by clients.

    Args:
        client: VastClient instance.
        id: Machine ID.

    Returns:
        Response dict.
    """
    r = client.post(f"/machines/{id}/force_delete/")
    r.raise_for_status()
    return r.json()


def reports(client: VastClient, id: int) -> dict:
    """Get user reports for a given machine.

    Args:
        client: VastClient instance.
        id: Machine ID.

    Returns:
        Reports dict.
    """
    json_blob = {"machine_id": id}
    r = client.get(f"/machines/{id}/reports/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def set_defjob(client: VastClient, id: int, price_gpu: float = None,
               price_inetu: float = None, price_inetd: float = None,
               image: str = None, args: list = None) -> dict:
    """Create default jobs for a machine.

    Args:
        client: VastClient instance.
        id: Machine ID.
        price_gpu: Per GPU rental price in $/hour.
        price_inetu: Price for upload bandwidth in $/GB.
        price_inetd: Price for download bandwidth in $/GB.
        image: Docker container image to launch.
        args: List of arguments passed to container launch.

    Returns:
        Response dict.
    """
    json_blob = {
        "machine": id,
        "price_gpu": price_gpu,
        "price_inetu": price_inetu,
        "price_inetd": price_inetd,
        "image": image,
        "args": args,
    }
    r = client.put("/machines/create_bids/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def remove_defjob(client: VastClient, id: int) -> dict:
    """Remove default jobs from a machine.

    Args:
        client: VastClient instance.
        id: Machine ID.

    Returns:
        Response dict.
    """
    r = client.delete(f"/machines/{id}/defjob/")
    r.raise_for_status()
    return r.json()


def set_min_bid(client: VastClient, id: int, price: float = None) -> dict:
    """Set the minimum bid/rental price for a machine.

    Args:
        client: VastClient instance.
        id: Machine ID.
        price: Per GPU min bid price in $/hour.

    Returns:
        Response dict.
    """
    json_blob = {"client_id": "me", "price": price}
    r = client.put(f"/machines/{id}/minbid/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


