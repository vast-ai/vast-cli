import requests
from typing import Any, Optional, Union

from vastai._base import _BaseClient, _APIKEY_SENTINEL
from vastai.data.query import Query
from vastai.data.offer import Offer
from vastai.data.instance import Instance, InstanceConfig, CreateInstanceResponse
from vastai.sync.results import SyncOffer, SyncInstance


class SyncClient(_BaseClient):
    """
    Synchronous Vast.ai API client.

    api_key resolution order:
      1. Explicit api_key argument
      2. VAST_API_KEY environment variable
      3. $XDG_CONFIG_HOME/vastai/vast_api_key
      4. ~/.vast_api_key (legacy)
    """
    def __init__(self, api_key: object = _APIKEY_SENTINEL, vast_server: str = "https://console.vast.ai"):
        super().__init__(api_key, vast_server)

    def search(
        self,
        query: Query,
        type_: Optional[str] = None,
        order: Optional[list] = [["score", "desc"]],
        limit: Optional[int] = None,
        allocated_storage: Optional[float] = None,
        target_reliability: Optional[float] = None,
        disable_bundling: Optional[bool] = None,
        external: Optional[bool] = None,
        extra_ids: Optional[list] = None,
        has_avx: Optional[int] = None,
        gpu_option: Optional[Any] = None,
        show_incompatible: Optional[Any] = None,
        sort_option: Optional[Any] = None,
        template_id: Optional[Any] = None,
    ) -> list[SyncOffer]:
        """Search available offers and return a list of SyncOffer result wrappers."""
        payload = dict(query.query)
        for key, value in [
            ("type",               type_),
            ("order",              order),
            ("limit",              limit),
            ("allocated_storage",  allocated_storage),
            ("target_reliability", target_reliability),
            ("disable_bundling",   disable_bundling),
            ("external",           external),
            ("extra_ids",          extra_ids),
            ("has_avx",            has_avx),
            ("gpu_option",         gpu_option),
            ("show_incompatible",  show_incompatible),
            ("sort_option",        sort_option),
            ("template_id",        template_id),
        ]:
            if value is not None:
                payload[key] = value

        response = requests.post(
            self._url("/api/v0/bundles/"),
            json=payload,
            headers=self._headers(),
        )
        response.raise_for_status()
        data = response.json()

        return [SyncOffer(Offer.from_dict(o), self) for o in data.get("offers", [])]

    def create_instance(
        self,
        offer_id: int,
        config: InstanceConfig,
    ) -> SyncInstance:
        """Accept an offer and create an instance. Returns a SyncInstance wrapper."""
        payload = config.to_dict()
        response = requests.put(
            self._url(f"/api/v0/asks/{offer_id}/"),
            json=payload,
            headers=self._headers(),
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            raise Exception(f"Failed to create instance: {data.get('error', '')} - {data.get('msg', '')}")

        resp = CreateInstanceResponse.from_dict(data)
        # Fetch the newly created instance
        instances = self.show_instances()
        for inst in instances:
            if inst.id == resp.new_contract:
                return inst
        # Fallback: return a minimal instance
        return SyncInstance(Instance.from_dict({"id": resp.new_contract}), self)

    def show_instances(self) -> list[SyncInstance]:
        """Return all instances owned by the authenticated user."""
        response = requests.get(
            self._url("/api/v0/instances/"),
            params={"owner": "me"},
            headers=self._headers(),
        )
        response.raise_for_status()
        data = response.json()

        return [SyncInstance(Instance.from_dict(i), self) for i in data.get("instances", [])]

    def destroy_instance(self, instance_or_id: Union[SyncInstance, int]) -> None:
        """Destroy a running or stopped instance."""
        instance_id = instance_or_id if isinstance(instance_or_id, int) else instance_or_id.id
        response = requests.delete(
            self._url(f"/api/v0/instances/{instance_id}/"),
            headers=self._headers(),
        )
        response.raise_for_status()
