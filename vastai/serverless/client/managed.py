from __future__ import annotations
from typing import TYPE_CHECKING, Awaitable, Generic, Optional, Union, TypeVar

from vastai.data.endpoint import EndpointData
from vastai.data.deployment import DeploymentData, DeploymentPutResponse
from vastai.data.workergroup import WorkergroupConfig
from .endpoint import Endpoint_
import requests

if TYPE_CHECKING:
    from .client import _ServerlessBase

R = TypeVar("R", bound=Awaitable)


class ManagedEndpoint(Generic[R]):
    """Wraps an endpoint with lazy data fetching, caching, and request dispatch.

    The .id property is always available. All other data is fetched on first
    access via .get() and cached. Call .invalidate() to force a re-fetch.
    """

    def __init__(
        self, id: int, client: _ServerlessBase[R], data: Optional[EndpointData] = None
    ):
        self._id = id
        self._client = client
        self._routing_endpoint: Optional[Endpoint_[R]] = (
            Endpoint_[R](client, data=data) if isinstance(data, EndpointData) else None
        )

    @property
    def id(self) -> int:
        return self._id

    def invalidate(self):
        """Clear cached data so the next .get() re-fetches from the API."""
        self._data = None
        self._routing_endpoint = None

    async def _get_routing_endpoint(self) -> Endpoint_[R]:
        if self._routing_endpoint is None:
            data = await self._client.fetch_endpoint(self._id)
            self._routing_endpoint = Endpoint_(client=self._client, data=data)
        return self._routing_endpoint

    async def request(self, route: str, payload: dict, **kwargs) -> dict:
        """Route a request to this endpoint's workers. Fetches endpoint data if needed."""
        ep = await self._get_routing_endpoint()
        return await self._client.queue_endpoint_request(
            endpoint=ep,
            worker_route=route,
            worker_payload=payload,
            **kwargs,
        )

    async def add_workergroup(
        self,
        config_or_template_hash: Union[WorkergroupConfig, str, None] = None,
        **kwargs,
    ) -> int:
        """Add a workergroup to this endpoint. Returns the workergroup ID.

        Accepts either:
          - A WorkergroupConfig object
          - A template_hash string (common case)
          - Keyword arguments passed to WorkergroupConfig
        """
        if isinstance(config_or_template_hash, WorkergroupConfig):
            config = config_or_template_hash
            if config.endpoint_id is None:
                config.endpoint_id = self._id
        elif isinstance(config_or_template_hash, str):
            config = WorkergroupConfig(
                endpoint_id=self._id, template_hash=config_or_template_hash, **kwargs
            )
        else:
            config = WorkergroupConfig(endpoint_id=self._id, **kwargs)
        return await self._client.create_workergroup(config)

    async def delete(self) -> None:
        """Delete this endpoint."""
        await self._client.delete_endpoint(self._id)

    def __repr__(self) -> str:
        status = "loaded" if self._routing_endpoint is not None else "lazy"
        return f"<ManagedEndpoint id={self._id} ({status})>"


class ManagedDeployment(Generic[R]):
    """Wraps a deployment with lazy data fetching, caching, and endpoint access.

    The .id and .endpoint_id properties are always available.
    If the deployment was just created/updated, .needs_upload and .upload()
    are available to handle S3 blob uploads.
    """

    def __init__(
        self,
        id: int,
        endpoint_id: int,
        client: _ServerlessBase[R],
        data: Optional[DeploymentData] = None,
        put_response: Optional[DeploymentPutResponse] = None,
    ):
        self._id = id
        self._endpoint_id = endpoint_id
        self._client = client
        self._data = data
        self._put_response = put_response
        self._endpoint: Optional[ManagedEndpoint[R]] = None

    @property
    def id(self) -> int:
        return self._id

    @property
    def endpoint_id(self) -> int:
        return self._endpoint_id

    @property
    def action(self) -> Optional[str]:
        """The action taken by put_deployment (e.g. 'created', 'soft_update', 'exists')."""
        return self._put_response.action if self._put_response else None

    @property
    def workergroup_id(self) -> Optional[int]:
        """The workergroup ID associated with this deployment, if returned by the server."""
        return self._put_response.workergroup_id if self._put_response else None

    @property
    def needs_upload(self) -> bool:
        """True if the deployment requires a blob upload to S3 to complete setup."""
        return (
            self._put_response is not None
            and self._put_response.upload_url is not None
            and self._put_response.upload_fields is not None
        )

    async def upload(self, file_path: str) -> None:
        """Upload a tarball to S3 using the presigned POST from put_deployment.

        Raises ValueError if no upload is needed, RuntimeError on upload failure.
        """
        if not self.needs_upload:
            raise ValueError("No upload needed for this deployment")

        import aiohttp
        import os

        upload_url = self._put_response.upload_url
        upload_fields = self._put_response.upload_fields

        data = aiohttp.FormData()
        for key, value in upload_fields.items():
            data.add_field(key, value)
        data.add_field(
            "file",
            open(file_path, "rb"),
            filename=os.path.basename(file_path),
            content_type="application/gzip",
        )

        session = await self._client._get_session()
        async with session.post(upload_url, data=data) as resp:
            if resp.status not in (200, 201, 204):
                text = await resp.text()
                raise RuntimeError(
                    f"S3 upload failed: HTTP {resp.status} - {text[:512]}"
                )

        self._put_response.upload_url = None
        self._put_response.upload_fields = None

    @property
    def endpoint(self) -> ManagedEndpoint[R]:
        """Get the ManagedEndpoint for this deployment (lazy — data fetched on first use)."""
        if self._endpoint is None:
            self._endpoint = ManagedEndpoint(id=self._endpoint_id, client=self._client)
        return self._endpoint

    async def get(self) -> DeploymentData:
        """Fetch and cache the full deployment data. Returns cached data on subsequent calls."""
        if self._data is None:
            self._data = await self._client.fetch_deployment(self._id)
        return self._data

    def invalidate(self):
        """Clear cached data so the next .get() re-fetches from the API."""
        self._data = None

    def sync_heartbeat(
        self,
    ):  # for use in background thread outside of main aiohttp connection
        headers = {"Authorization": f"Bearer {self._client.api_key}"}
        requests.post(
            url=self._client.vast_web_url.rstrip("/")
            + f"/api/v0/deployment/{self.id}/heartbeat/",
            headers=headers,
        )

    def __repr__(self) -> str:
        status = "loaded" if self._data is not None else "lazy"
        upload = " needs_upload" if self.needs_upload else ""
        return f"<ManagedDeployment id={self._id} endpoint_id={self._endpoint_id} ({status}{upload})>"
