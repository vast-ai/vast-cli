from __future__ import annotations

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from aiohttp import web

from vastai.serverless.client.connection import WorkerUrlRejected, _make_request, _require_public_worker_url
from vastai.serverless.client.endpoint import Endpoint, RouteResponse

ACCEPTED = ["http://1.2.3.4:8000", "https://99.18.87.11:443", "http://8.8.8.8:65535"]

REJECTED = [
    None, "", "1.2.3.4:8000", "ftp://1.2.3.4:21", "http://example.com:8000", "http://1.2.3.4",
    "http://1.2.3.4:0", "http://1.2.3.4:65536", "http://1.2.3.4:8000/", "http://1.2.3.4:8000/v1",
    "http://1.2.3.4:8000#", "http://1.2.3.4:8000?a=b", "http://u@1.2.3.4:8000", "http://[2001:db8::1]:8000",
    "http://010.0.0.1:80", "http://2130706433:80", "http://１.２.３.４:80",
    "http://0.0.0.0:80", "http://10.0.0.1:80", "http://100.64.0.1:80", "http://127.0.0.1:80",
    "http://169.254.169.254:80", "http://169.254.170.2:80", "http://172.16.0.1:80", "http://192.168.1.1:80",
    "http://198.18.0.1:80", "http://224.0.0.1:80", "http://255.255.255.255:80",
]


@pytest.mark.parametrize("url", ACCEPTED)
def test_accepts_public_ipv4_url(url) -> None:
    _require_public_worker_url(url)


@pytest.mark.parametrize("url", REJECTED)
def test_rejects_anything_but_public_ipv4_url(url) -> None:
    with pytest.raises(WorkerUrlRejected):
        _require_public_worker_url(url)


class _Client:
    def __init__(self, session):
        self._session = session

    async def _get_session(self):
        return self._session

    async def get_ssl_context(self):
        return None


@pytest.mark.parametrize("allow_redirects,status,target_hit", [(False, 302, False), (True, 200, True)])
async def test_redirects_are_followed_only_when_allowed(allow_redirects, status, target_hit) -> None:
    hits = []

    async def redirect(_request):
        raise web.HTTPFound("/target")

    async def target(_request):
        hits.append(True)
        return web.json_response({"secret": 1})

    app = web.Application()
    app.router.add_post("/r", redirect)
    app.router.add_get("/target", target)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    url = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
    try:
        async with aiohttp.ClientSession() as session:
            result = await _make_request(client=_Client(session), url=url, route="/r", api_key="k",
                                         method="POST", retries=1, allow_redirects=allow_redirects)
    finally:
        await runner.cleanup()

    assert result["status"] == status
    assert bool(hits) == target_hit


async def test_rejected_worker_url_fails_after_one_route_without_calling_worker(
    client_with_session, make_serverless_endpoint
) -> None:
    client = client_with_session
    ep = make_serverless_endpoint(client)
    route_mock = AsyncMock(return_value=RouteResponse({"request_idx": 1, "url": "http://169.254.170.2:80#"}))
    make_req = AsyncMock(return_value={"ok": True, "json": {}})

    with (
        patch.object(Endpoint, "_route", route_mock),
        patch("vastai.serverless.client.client._make_request", make_req),
    ):
        fut = client.queue_endpoint_request(endpoint=ep, worker_route="/v1/chat/completions", worker_payload={})
        with pytest.raises(WorkerUrlRejected):
            await fut

    assert route_mock.call_count == 1
    make_req.assert_not_called()
