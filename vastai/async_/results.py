from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Union

from vastai.data.offer import Offer
from vastai.data.instance import InstanceConfig

if TYPE_CHECKING:
    from vastai.async_.client import AsyncClient
    from vastai.data.instance import Instance


class AsyncOffer:
    def __init__(self, data: Offer, client: AsyncClient):
        self._data = data
        self._client = client

    async def create_instance(self, config: InstanceConfig) -> AsyncInstance:
        """Create an instance from this offer. Synonym for AsyncClient.create_instance(self.id, config)."""
        return await self._client.create_instance(self._data.id, config)

    def __getattr__(self, name: str):
        return getattr(self._data, name)

    def __repr__(self) -> str:
        return f"AsyncOffer({self._data!r})"


class AsyncInstance:
    def __init__(self, data: Instance, client: AsyncClient):
        self._data = data
        self._client = client

    async def destroy(self) -> None:
        """Synonym for AsyncClient.destroy_instance(self)."""
        return await self._client.destroy_instance(self._data.id)

    def __getattr__(self, name: str):
        return getattr(self._data, name)

    def __repr__(self) -> str:
        return f"AsyncInstance({self._data!r})"
