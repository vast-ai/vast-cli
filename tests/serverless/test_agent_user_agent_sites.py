"""Serverless and standalone-entry requests to a Vast host carry the agent-tagged User-Agent (CLNT-3586).

Same method as tests/api/test_agent_user_agent_sites.py: the real code path sends to a local
echo server and the User-Agent that arrived is read; ``agent_case`` runs each test with no
agent detected and under CLAUDECODE=1.
"""

import contextlib
import os
import types
from unittest import mock

import aiohttp

from vastai.serverless.client.client import Serverless
from vastai.serverless.client.connection import _make_request
from vastai.serverless.client.endpoint import Endpoint
from vastai.serverless.client.managed import ManagedDeployment
from vastai.serverless.remote import serve_deployment
from vastai.utils import VERSION


def _expected(kind, suffix):
    return f"vastai-{kind}/{VERSION}{suffix}"


def _assert_untagged(user_agents):
    for ua in user_agents:
        assert ua is None or (not ua.startswith("vastai-") and "(via" not in ua), ua


async def _no_ssl():
    return None


def _serverless(echo_server):
    client = Serverless(api_key="k", autoscaler_url=echo_server.url, webserver_url=echo_server.url)
    client.get_ssl_context = _no_ssl
    return client


async def test_connection_make_request_carries_the_tag(echo_server, agent_case):
    session = aiohttp.ClientSession()
    client = types.SimpleNamespace(_get_session=mock.AsyncMock(return_value=session), get_ssl_context=_no_ssl)
    try:
        await _make_request(client=client, route="/api/v0/x/", api_key="k", url=echo_server.url, retries=1)
    finally:
        await session.close()
    assert echo_server.user_agents(path_contains="/api/v0/x/") == [_expected("sdk", agent_case)]


async def test_serverless_get_endpoint_workers_carries_the_tag(echo_server, agent_case):
    client = _serverless(echo_server)
    client._session = aiohttp.ClientSession()
    endpoint = mock.MagicMock(spec=Endpoint)
    endpoint.id = 1
    try:
        with contextlib.suppress(Exception):
            await client.get_endpoint_workers(endpoint)
    finally:
        await client._session.close()
    assert echo_server.user_agents(path_contains="get_endpoint_workers") == [_expected("sdk", agent_case)]


def test_managed_deployment_heartbeat_carries_the_tag(echo_server, agent_case):
    fake = types.SimpleNamespace(id=7, _client=types.SimpleNamespace(api_key="k", vast_web_url=echo_server.url))
    ManagedDeployment.sync_heartbeat(fake)
    assert echo_server.user_agents(path_contains="heartbeat") == [_expected("sdk", agent_case)]


def test_serve_deployment_download_url_request_carries_the_tag(echo_server, agent_case, monkeypatch):
    monkeypatch.setattr(serve_deployment, "VAST_API_URL", echo_server.url)
    assert serve_deployment.get_download_url("5", "k") == echo_server.url + "/blob"
    assert echo_server.user_agents(path_contains="download_url") == [_expected("cli", agent_case)]


async def test_serverless_ssl_root_certificate_download_carries_the_tag(echo_server, agent_case, monkeypatch):
    monkeypatch.setattr(Serverless, "SSL_CERT_URL", echo_server.url + "/static/jvastai_root.cer")
    client = Serverless(api_key="k", autoscaler_url=echo_server.url, webserver_url=echo_server.url)
    with mock.patch("ssl.create_default_context"):  # the echo body is not a certificate; stop at the fetch
        await client.get_ssl_context()
    assert echo_server.user_agents(path_contains="jvastai_root.cer") == [_expected("sdk", agent_case)]
    assert [h for r in echo_server.requests for h in r["headers"] if h.lower() == "authorization"] == []


# --- sites left unchanged ----------------------------------------------------


def test_presigned_blob_fetch_is_left_unchanged(echo_server, monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    path = serve_deployment.download_tarball(echo_server.url + "/blob")
    os.unlink(path)
    _assert_untagged(echo_server.user_agents(path_contains="/blob"))


async def test_presigned_upload_through_the_shared_session_is_left_unchanged(echo_server, monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDECODE", "1")
    client = _serverless(echo_server)
    upload = tmp_path / "deployment.tar.gz"
    upload.write_bytes(b"x")
    fake = types.SimpleNamespace(
        needs_upload=True,
        _client=client,
        _put_response=types.SimpleNamespace(upload_url=echo_server.url + "/s3-upload", upload_fields={"k": "v"}),
    )
    try:
        await ManagedDeployment.upload(fake, str(upload))
    finally:
        await client._session.close()
    _assert_untagged(echo_server.user_agents(path_contains="/s3-upload"))
