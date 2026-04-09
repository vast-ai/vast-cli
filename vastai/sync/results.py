from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Union

from vastai.data.offer import Offer
from vastai.data.instance import InstanceConfig

if TYPE_CHECKING:
    from vastai.sync.client import SyncClient
    from vastai.data.instance import Instance


class SyncOffer:
    def __init__(self, data: Offer, client: SyncClient):
        self._data = data
        self._client = client

    def create_instance(self, config: InstanceConfig) -> SyncInstance:
        """Create an instance from this offer. Synonym for SyncClient.create_instance(self.id, config)."""
        return self._client.create_instance(self._data.id, config)

    def __getattr__(self, name: str):
        return getattr(self._data, name)

    def __repr__(self) -> str:
        return f"SyncOffer({self._data!r})"


class SyncInstance:
    def __init__(self, data: Instance, client: SyncClient):
        self._data = data
        self._client = client

    def destroy(self) -> None:
        """Synonym for SyncClient.destroy_instance(self)."""
        return self._client.destroy_instance(self._data.id)

    def __getattr__(self, name: str):
        return getattr(self._data, name)

    def __repr__(self) -> str:
        return f"SyncInstance({self._data!r})"
