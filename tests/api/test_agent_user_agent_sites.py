"""Every request the CLI and SDK send to a Vast host carries the agent-tagged User-Agent (CLNT-3586).

Each test sends through the real code path to a local echo server and reads the User-Agent
that arrived. ``agent_case`` runs every test twice: with every agent variable removed (the
header must be exactly today's plain one) and under CLAUDECODE=1 (the suffix must be there).
The serverless paths are in tests/serverless/test_agent_user_agent_sites.py.
"""

import contextlib
import types
from unittest import mock

import pytest

from vastai.api import endpoints as endpoints_api
from vastai.api import instances as instances_api
from vastai.api.client import VastClient
from vastai.async_.client import AsyncClient
from vastai.data.instance import InstanceConfig
from vastai.data.query import Query
from vastai.sync.client import SyncClient
from vastai.utils import VERSION


def _expected(kind, suffix):
    return f"vastai-{kind}/{VERSION}{suffix}"


def _assert_untagged(user_agents):
    """A site left unchanged: it must not send a Vast User-Agent or an agent tag, agent or not."""
    for ua in user_agents:
        assert ua is None or (not ua.startswith("vastai-") and "(via" not in ua), ua


# --- the shared API client -------------------------------------------------


@pytest.mark.parametrize("kind", ["cli", "sdk"])
def test_vast_client_requests_carry_the_tag(echo_server, agent_case, kind):
    client = VastClient(api_key="k", server_url=echo_server.url, client_type=kind)
    client.get("/api/v0/x/")
    client.post("/api/v0/x/", json_data={})
    client.put("/api/v0/x/", json_data={})
    client.delete("/api/v0/x/")
    uas = echo_server.user_agents()
    assert len(uas) == 4
    assert set(uas) == {_expected(kind, agent_case)}


@pytest.mark.parametrize(
    "call",
    [
        lambda c: endpoints_api.get_endpt_logs(c, id=1),
        lambda c: endpoints_api.get_wrkgrp_logs(c, id=1),
        lambda c: endpoints_api.get_endpoint_workers(c, id=1),
        lambda c: endpoints_api.update_workers(c, id=1),
    ],
    ids=["get_endpt_logs", "get_wrkgrp_logs", "get_endpoint_workers", "update_workers"],
)
@pytest.mark.parametrize("kind", ["cli", "sdk"])
def test_endpoint_functions_send_the_tag(echo_server, agent_case, call, kind):
    client = VastClient(api_key="k", server_url=echo_server.url, client_type=kind)
    call(client)
    assert echo_server.user_agents() == [_expected(kind, agent_case)]


# --- the SDK clients -------------------------------------------------------


def test_sync_client_four_sites_carry_the_tag(echo_server, agent_case):
    client = SyncClient(api_key="k", vast_server=echo_server.url)
    with contextlib.suppress(Exception):
        client.search(Query({}))
    with contextlib.suppress(Exception):
        client.create_instance(1, InstanceConfig(image="x"))
    with contextlib.suppress(Exception):
        client.show_instances()
    with contextlib.suppress(Exception):
        client.destroy_instance(1)
    for method in ("POST", "PUT", "GET", "DELETE"):
        assert set(echo_server.user_agents(method=method)) == {_expected("sdk", agent_case)}, method


async def test_async_client_sites_carry_the_tag(echo_server, agent_case):
    client = AsyncClient(api_key="k", vast_server=echo_server.url)
    client._ssl_context = None

    async def no_ssl():
        return None

    client.get_ssl_context = no_ssl
    try:
        with contextlib.suppress(Exception):
            await client.search(Query({}))
        with contextlib.suppress(Exception):
            await client.create_instance(1, InstanceConfig(image="x"))
        with contextlib.suppress(Exception):
            await client.show_instances()
        with contextlib.suppress(Exception):
            await client.destroy_instance(1)
    finally:
        await client.close(force=True)
    for method in ("POST", "PUT", "GET", "DELETE"):
        assert set(echo_server.user_agents(method=method)) == {_expected("sdk", agent_case)}, method


async def test_async_ssl_root_certificate_download_carries_the_tag(echo_server, agent_case, monkeypatch):
    monkeypatch.setattr(AsyncClient, "SSL_CERT_URL", echo_server.url + "/static/jvastai_root.cer")
    client = AsyncClient(api_key="k", vast_server=echo_server.url)
    with mock.patch("ssl.create_default_context"):  # the echo body is not a certificate; stop at the fetch
        await client.get_ssl_context()
    assert echo_server.user_agents(path_contains="jvastai_root.cer") == [_expected("sdk", agent_case)]
    assert [h for r in echo_server.requests for h in r["headers"] if h.lower() == "authorization"] == []


# --- the CLI's own requests ------------------------------------------------


def test_gpu_names_and_gpu_types_fetches_carry_the_tag(echo_server, agent_case, monkeypatch, tmp_path):
    from vastai.cli import util

    monkeypatch.setattr(util, "server_url_default", echo_server.url)
    monkeypatch.setattr(util, "CACHE_FILE", str(tmp_path / "names.json"))
    monkeypatch.setattr(util, "GPU_TYPES_CACHE_FILE", str(tmp_path / "types.json"))
    util._get_gpu_names()
    util._get_gpu_types()
    assert echo_server.user_agents(path_contains="gpu_names") == [_expected("cli", agent_case)]
    assert echo_server.user_agents(path_contains="gpu_types") == [_expected("cli", agent_case)]


# --- sites left unchanged: they send what they send today, tagged or not ---


def test_self_update_manifest_fetch_is_left_unchanged(echo_server, monkeypatch):
    from vastai.cli import selfupdate

    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("VASTAI_MANIFEST_URL", echo_server.url + "/manifest.env")
    with contextlib.suppress(Exception):
        selfupdate.fetch_manifest()
    _assert_untagged(echo_server.user_agents(path_contains="manifest"))


def test_instance_result_polling_is_left_unchanged(echo_server, monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    instances_api._poll_result_url(echo_server.url + "/result", retries=1, delay=0)
    _assert_untagged(echo_server.user_agents(path_contains="/result"))


def test_execute_command_result_polling_is_left_unchanged(echo_server, monkeypatch):
    from vastai.cli.commands import misc

    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setattr(misc, "get_client", lambda args: None)
    monkeypatch.setattr(misc.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        misc.instances_api, "execute",
        lambda client, id, command: {"success": True, "result_url": echo_server.url + "/result", "writeable_path": "/w"},
    )
    args = types.SimpleNamespace(id=1, COMMAND="ls", explain=False, schedule=None)
    misc.execute(args)
    _assert_untagged(echo_server.user_agents(path_contains="/result"))
