"""Price-increase contract extension API.

Backend pairs (vast/web/views/instance.py:257-312,
vast/web/views/pydantic/models/instance.py):

    GET  /api/v0/instances/pending-price-increases/
    PUT  /api/v0/instances/accept-price-increase/
    PUT  /api/v0/instances/reject-price-increase/

Both PUT endpoints require body exactly
``{"pending_price_increase_id": <int>}`` (``_Base.Config.extra='forbid'``).
The backend has no batch endpoint, no ``instance_ids``, no ``host_id``,
and no ``snapshot`` field. The pending row id IS the identity.

Stale rows return ``HTTP 404`` with body
``{"success": false, "error": "no_pending_price_increase"}``; older
backends may still return ``HTTP 409`` (the frontend recognises both).
"""

from vastai.api.client import VastClient


NO_PENDING_PRICE_INCREASE = "no_pending_price_increase"


def list_pending(client: VastClient) -> dict:
    """Return the pending-price-increase envelope.

    Shape (from web/price_increase_pending.py:_serialize_pending_row):

        {
          "success": True,
          "count": <int>,
          "truncated": <bool>,
          "pending_price_increases": [
              {
                "pending_price_increase_id": <int>,
                "contract_id":               <int>,
                "host_id":                   <int>,
                "new_gpu_costpersec":        <float|null>,
                "new_disk_ram_costpersec":   <float|null>,
                "new_bwu_cost":              <float|null>,
                "new_bwd_cost":              <float|null>,
                "new_platform_fee":          <float|null>,
                "old_gpu_costpersec":        <float|null>,
                "old_disk_ram_costpersec":   <float|null>,
                "old_bwu_cost":              <float|null>,
                "old_bwd_cost":              <float|null>,
                "old_platform_fee":          <float|null>,
                "contract_end_date":         <float|null>,
                "ask_end_date":              <float|null>,
                "created_at":                <float|null>
              },
              ...
          ]
        }
    """
    r = client.get("/instances/pending-price-increases/")
    r.raise_for_status()
    return r.json()


def accept(client: VastClient, pending_id: int) -> dict:
    """Accept one pending price-increase row.

    The body must be exactly ``{"pending_price_increase_id": int}``;
    backend ``extra='forbid'`` returns 422 for any extra key. Returns
    ``{"success": True, "pending_price_increase_id": int, "contract_id": int}``.
    """
    r = client.put(
        "/instances/accept-price-increase/",
        json_data={"pending_price_increase_id": int(pending_id)},
    )
    r.raise_for_status()
    return r.json()


def reject(client: VastClient, pending_id: int) -> dict:
    """Reject one pending price-increase row.

    Same body shape and response shape as :func:`accept`. The backend
    tombstones the row (status=rejected); no cutover follows.
    """
    r = client.put(
        "/instances/reject-price-increase/",
        json_data={"pending_price_increase_id": int(pending_id)},
    )
    r.raise_for_status()
    return r.json()
