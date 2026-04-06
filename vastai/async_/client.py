import aiohttp
import ssl
import os
import tempfile
import asyncio
from typing import Any, Optional, Union

from vastai._base import _BaseClient, _APIKEY_SENTINEL
from vastai.data.query import Query
from vastai.data.offer import Offer
from vastai.data.instance import Instance, InstanceConfig, CreateInstanceResponse
from vastai.async_.results import AsyncOffer, AsyncInstance
from vastai.serverless.client.client import CoroutineServerless


class AsyncClient(_BaseClient):
    """
    Asynchronous Vast.ai API client.

    api_key resolution order:
      1. Explicit api_key argument
      2. VAST_API_KEY environment variable
      3. $XDG_CONFIG_HOME/vastai/vast_api_key
      4. ~/.vast_api_key (legacy)
    """

    SSL_CERT_URL = "https://console.vast.ai/static/jvastai_root.cer"

    def __init__(
        self,
        api_key: object = _APIKEY_SENTINEL,
        vast_server: str = "https://console.vast.ai",
        connection_limit: int = 100,
    ):
        super().__init__(api_key, vast_server)
        self._connection_limit = connection_limit
        self._session: aiohttp.ClientSession | None = None
        self._ssl_context: ssl.SSLContext | None = None
        self._session_depth = 0

    async def get_ssl_context(self) -> ssl.SSLContext:
        """Download Vast.ai root cert and build SSL context (cached).

        The custom cert is added on top of the system default CAs, so this
        context works for both console.vast.ai and serverless worker connections.
        """
        if self._ssl_context is None:
            async with aiohttp.ClientSession() as s:
                async with s.get(self.SSL_CERT_URL) as resp:
                    if resp.status != 200:
                        raise Exception(f"Failed to fetch SSL cert: {resp.status}")
                    cert_bytes = await resp.read()

            tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".cer")
            tmpfile.write(cert_bytes)
            tmpfile.close()

            ctx = ssl.create_default_context()
            ctx.load_verify_locations(cafile=tmpfile.name)

            self._ssl_context = ctx
            os.unlink(tmpfile.name)

        return self._ssl_context

    async def _get_session(self, use_context=False) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(
                    limit=self._connection_limit,
                    ssl=await self.get_ssl_context(),
                )
            )
            self._session_depth += 1
            if not use_context:
                loop = asyncio.get_running_loop()
                original_close = loop.close

                def close():
                    loop.run_until_complete(self.close(force=True))
                    original_close()

                loop.close = close
        elif use_context:
            self._session_depth += 1  # If we already are expected to keep a connection, and we expect to call close before exit, still flag so that close doesn't actually close.
        return self._session

    def is_open(self):
        return self._session is not None and not self._session.closed

    async def close(self, force=False):
        if self._session and not self._session.closed:
            if self._session_depth > 0:
                self._session_depth -= 1
            if force or not self._session_depth:
                self._session_depth = 0
                await self._session.close()

    async def __aenter__(self):
        await self._get_session(use_context=True)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    # ── Search ──────────────────────────────────────────────────────────────

    async def search(
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
    ) -> list[AsyncOffer]:
        """Search available offers and return a list of AsyncOffer result wrappers."""
        payload = dict(query.query)
        for key, value in [
            ("type", type_),
            ("order", order),
            ("limit", limit),
            ("allocated_storage", allocated_storage),
            ("target_reliability", target_reliability),
            ("disable_bundling", disable_bundling),
            ("external", external),
            ("extra_ids", extra_ids),
            ("has_avx", has_avx),
            ("gpu_option", gpu_option),
            ("show_incompatible", show_incompatible),
            ("sort_option", sort_option),
            ("template_id", template_id),
        ]:
            if value is not None:
                payload[key] = value

        session = await self._get_session()
        async with session.post(
            self._url("/api/v0/bundles/"),
            json=payload,
            headers=self._headers(),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)

        return [AsyncOffer(Offer.from_dict(o), self) for o in data.get("offers", [])]

    # ── Create Instance ─────────────────────────────────────────────────────

    async def create_instance(
        self,
        offer_id: int,
        config: InstanceConfig,
    ) -> AsyncInstance:
        """Accept an offer and create an instance. Returns an AsyncInstance wrapper."""
        payload = config.to_dict()
        session = await self._get_session()
        async with session.put(
            self._url(f"/api/v0/asks/{offer_id}/"),
            json=payload,
            headers=self._headers(),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)

        if not data.get("success"):
            raise Exception(
                f"Failed to create instance: {data.get('error', '')} - {data.get('msg', '')}"
            )

        resp_data = CreateInstanceResponse.from_dict(data)
        # Fetch the newly created instance
        instances = await self.show_instances()
        for inst in instances:
            if inst.id == resp_data.new_contract:
                return inst
        # Fallback: return a minimal instance
        return AsyncInstance(Instance.from_dict({"id": resp_data.new_contract}), self)

    # ── Instances ───────────────────────────────────────────────────────────

    async def show_instances(self) -> list[AsyncInstance]:
        """Return all instances owned by the authenticated user."""
        session = await self._get_session()
        async with session.get(
            self._url("/api/v0/instances/"),
            params={"owner": "me"},
            headers=self._headers(),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)

        return [
            AsyncInstance(Instance.from_dict(i), self)
            for i in data.get("instances", [])
        ]

    async def destroy_instance(self, instance_or_id: Union[AsyncInstance, int]) -> None:
        """Destroy a running or stopped instance."""
        instance_id = (
            instance_or_id if isinstance(instance_or_id, int) else instance_or_id.id
        )
        session = await self._get_session()
        async with session.delete(
            self._url(f"/api/v0/instances/{instance_id}/"),
            headers=self._headers(),
        ) as resp:
            resp.raise_for_status()

    # ── Serverless factory ──────────────────────────────────────────────────

    def serverless(
        self,
        *,
        instance: str = "prod",
        autoscaler_url: Optional[str] = None,
        debug: bool = False,
        default_request_timeout: float = 600.0,
        max_poll_interval: float = 5.0,
    ) -> CoroutineServerless:
        """Create a CoroutineServerless that shares this client's aiohttp session and SSL context."""
        sl = CoroutineServerless(
            api_key=self._api_key,
            instance=instance,
            autoscaler_url=autoscaler_url,
            webserver_url=self._vast_server,
            debug=debug,
            connection_limit=self._connection_limit,
            default_request_timeout=default_request_timeout,
            max_poll_interval=max_poll_interval,
        )
        sl._transport_owner = self
        return sl
