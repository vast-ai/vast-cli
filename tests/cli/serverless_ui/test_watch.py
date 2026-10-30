"""POST /api/watch: the autoscaler's worker socket relayed to the page."""
import asyncio
import collections
import json

import pytest

from vastai.serverless.ui import server as ui
from .fake_vast import AUTH, assert_clean


@pytest.fixture(autouse=True)
def quick(monkeypatch):
    monkeypatch.setattr(ui, "RECONNECT_MAX", 0.01)
    monkeypatch.setattr(ui.random, "random", lambda: 0.0)


async def watch_until(client, done, limit=200):
    """Lines from a watch until done(lines) holds; then the page goes away."""
    resp = await client.post("/api/watch", json={"endpoint": 7}, headers=AUTH)
    assert resp.status == 200, await resp.text()
    raw, lines = [], []
    for _ in range(limit):
        line = await asyncio.wait_for(resp.content.readline(), 5)
        raw.append(line.decode())
        lines.append(json.loads(line))
        if done(lines):
            break
    resp.close()
    return lines, "".join(raw)


def have_both(lines):
    topics = {(l["topic"], l["id"]) for l in lines if l["type"] == "workers"}
    return {("endpoint", 7), ("workergroup", 90)} <= topics


async def test_live_workers_for_endpoint_and_workergroups(client, logs):
    lines, raw = await watch_until(client, have_both)
    config = lines[0]
    assert config["type"] == "config"
    assert set(config["endpoint"]) == set(ui.ENDPOINT_SCALING)
    assert [g["id"] for g in config["workergroups"]] == [90]
    assert {"type": "status", "state": "live"} in lines
    pushed = [l for l in lines if l["type"] == "workers"]
    endpoint = next(l for l in pushed if l["topic"] == "endpoint")
    assert [w["status"] for w in endpoint["workers"]] == ["model_loading", "running"]
    assert all("api_key" not in w for l in pushed for w in l["workers"])  # whitelisted
    assert_clean(raw, logs.getvalue())


async def test_watch_ends_when_the_page_goes_away(client):
    await watch_until(client, have_both)
    for _ in range(100):
        if not ui._watches:
            break
        await asyncio.sleep(0.02)
    assert not ui._watches


async def test_unauthorized_topic_is_a_warning(client, vast_api):
    vast_api.state["workergroups"].append(
        {"id": 93, "endpoint_id": 7, "template_hash": None, "template_id": None, "launch_args": None})
    lines, _ = await watch_until(client, lambda ls: any(l["type"] == "warning" for l in ls) and have_both(ls))
    assert any("not authorized for autogroup:93" in l["detail"] for l in lines if l["type"] == "warning")


async def test_socket_down_falls_back_to_one_rest_read_per_wait(client, vast_api, logs):
    vast_api.state["mode"] = "ws-down"
    polled = lambda ls: sum(1 for l in ls if l.get("polled")) >= 2  # noqa: E731
    lines, raw = await watch_until(client, polled)
    reconnecting = [l for l in lines if l.get("state") == "reconnecting"]
    assert reconnecting and "[redacted]" in reconnecting[0]["detail"]  # the URL carries the key
    polls = [l for l in lines if l.get("polled")]
    assert len(polls[0]["workers"]) == 3 and "api_key" not in polls[0]["workers"][0]
    assert vast_api.state["rest_polls"] <= vast_api.state["ws_connects"]  # never more than one per attempt
    assert_clean(raw, logs.getvalue())


async def test_silent_socket_reconnects(client, vast_api, monkeypatch):
    monkeypatch.setattr(ui, "STALE_AFTER", 0.1)
    vast_api.state["mode"] = "ws-silent"
    lines, _ = await watch_until(client, lambda ls: any(l.get("state") == "reconnecting" for l in ls))
    assert "no update" in next(l for l in lines if l.get("state") == "reconnecting")["detail"]


async def test_limits_and_bad_requests(client, monkeypatch):
    assert (await client.post("/api/watch", json={}, headers=AUTH)).status == 400
    assert (await client.post("/api/watch", json={"endpoint": 7})).status == 401
    monkeypatch.setattr(ui, "_watches", collections.Counter({"others": ui.MAX_WATCHES}))
    assert (await client.post("/api/watch", json={"endpoint": 7}, headers=AUTH)).status == 503


async def test_worker_addresses_are_looked_up_once_and_only_addresses_leave(client, vast_api, logs):
    def hosts_then_more_pushes(lines):
        at = next((i for i, l in enumerate(lines) if l["type"] == "hosts"), None)
        return at is not None and sum(l["type"] == "workers" for l in lines[at:]) >= 10
    lines, raw = await watch_until(client, hosts_then_more_pushes)
    found = [l for l in lines if l["type"] == "hosts"]
    port = vast_api.port
    assert found == [{"type": "hosts", "hosts": {f"127.0.0.1:{port}": 1001, "127.0.0.1:1": 1000}}]
    assert vast_api.state["instance_lookups"] == 2  # one lookup over two pages, then all placed
    assert_clean(raw, logs.getvalue())


async def test_failed_address_lookup_is_a_warning_and_rate_limited(client, vast_api, monkeypatch):
    calls = []
    async def counting(request, ids):
        calls.append(ids)
        raise RuntimeError("instances unavailable")
    monkeypatch.setattr(ui, "worker_hosts", counting)
    lines, _ = await watch_until(client, lambda ls: sum(l["type"] == "workers" for l in ls) >= 10)
    assert len(calls) == 1  # once per HOSTS_EVERY however many pushes arrive
    assert any(l["type"] == "warning" and "worker addresses" in l["detail"] for l in lines)


async def test_workers_without_an_address_are_looked_up_again_quietly(client, vast_api, monkeypatch):
    monkeypatch.setattr(ui, "HOSTS_EVERY", 0.05)
    vast_api.state["instances_hidden"] = True  # stopped or starting: no address, which is normal
    def placed_after_reappearing(lines):
        if sum(l["type"] == "workers" for l in lines) == 5:
            vast_api.state["instances_hidden"] = False
        return any(l["type"] == "hosts" for l in lines)
    lines, _ = await watch_until(client, placed_after_reappearing)
    assert not any(l["type"] == "warning" for l in lines)
    assert vast_api.state["instance_lookups"] > 1


async def test_one_key_gets_only_its_share_of_worker_views(client, monkeypatch):
    monkeypatch.setattr(ui, "MAX_WATCHES_PER_KEY", 1)
    monkeypatch.setattr(ui, "_watches", collections.Counter({ui.key_hash(AUTH["Authorization"].split()[1]): 1}))
    resp = await client.post("/api/watch", json={"endpoint": 7}, headers=AUTH)
    assert resp.status == 503 and "You already have 1 worker views open" in (await resp.json())["error"]
