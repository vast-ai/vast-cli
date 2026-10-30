"""POST /api/load: open-loop requests following a rate profile."""
import asyncio
import collections
import json

import pytest

from vastai.serverless.ui import server as ui
from .fake_vast import AUTH, SECRETS

IMAGES = "/v1/images/generations"


async def run(client, profile, route=IMAGES, body=None, **options):
    resp = await client.post("/api/load", headers=AUTH, json={
        "endpoint": 7, "route": route, "body": body or {"prompt": "a fox"}, "profile": profile,
        **options})
    text = await resp.text()
    assert resp.status == 200, text
    return [json.loads(line) for line in text.splitlines() if line], text


def results(lines):
    return [r for line in lines if line["type"] == "tick" for r in line["results"]]


def test_profile_shape():
    profile = ui.read_profile([{"from": 0, "to": 10, "seconds": 10}, {"from": 4, "to": 4, "seconds": 5}])
    assert ui.rate_at(profile, 0) == 0 and ui.rate_at(profile, 5) == 5
    assert ui.rate_at(profile, 12) == 4 and ui.rate_at(profile, 15) is None
    assert ui.expected_requests(profile) == 50 + 20


def test_tag_body_marks_the_first_text_only():
    tag = ui.tag_body
    assert tag({"prompt": "p", "n": 2}, "[x] ") == {"prompt": "[x] p", "n": 2}
    chat = {"messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]}
    assert tag(chat, "[x] ")["messages"][0]["content"] == "[x] s"
    assert chat["messages"][0]["content"] == "s"  # the original is untouched
    batch = {"messages": [[{"role": "user", "content": "a"}], [{"role": "user", "content": "b"}]]}
    assert tag(batch, "[x] ")["messages"][0][0]["content"] == "[x] a"
    assert tag({"input": ["a", "b"]}, "[x] ")["input"] == ["[x] a", "b"]
    assert tag({"query": "q"}, "[x] ") == {"query": "q"}


@pytest.mark.parametrize("step", [0.05, 0.0625])  # 0.0625: as coarse as Windows' timer
async def test_even_arrivals_follow_the_rate(client, vast_api, logs, monkeypatch, step):
    """Even arrivals send what the profile asks for, however late the scheduler's steps run."""
    monkeypatch.setattr(ui, "LOAD_STEP", step)
    lines, text = await run(client, [{"from": 20, "to": 20, "seconds": 0.5}])
    start, done = lines[0], lines[-1]
    assert start["type"] == "start" and start["expected"] == 10
    assert done["type"] == "done" and done["sent"] == 10 and done["skipped"] == 0
    landed = results(lines)
    assert len(landed) == done["sent"] and all(r["ok"] for r in landed)
    prompts = [p["prompt"] for p in vast_api.state["payloads"]]
    assert len(set(prompts)) == len(prompts)  # each request made unique
    assert all(p.startswith(f"[{start['run']}-") and p.endswith("a fox") for p in prompts)
    assert all(SECRET not in text for SECRET in SECRETS) and all(s not in logs.getvalue() for s in SECRETS)


async def test_poisson_arrivals_and_identical_bodies(client, vast_api):
    lines, _ = await run(client, [{"from": 20, "to": 20, "seconds": 0.5}], arrivals="poisson", unique=False)
    assert lines[-1]["sent"] > 0
    assert {p["prompt"] for p in vast_api.state["payloads"]} == {"a fox"}


async def test_inflight_cap_skips_and_counts(client, vast_api, monkeypatch):
    monkeypatch.setattr(ui, "MAX_LOAD_INFLIGHT", 2)
    vast_api.state["image_delay"] = 0.4
    lines, _ = await run(client, [{"from": 20, "to": 20, "seconds": 0.5}])
    done = lines[-1]
    assert done["skipped"] > 0 and done["sent"] + done["skipped"] == 10
    assert max(line["inflight"] for line in lines if line["type"] == "tick") <= 2


async def test_worker_errors_are_counted_and_scrubbed(client, logs):
    lines, text = await run(client, [{"from": 10, "to": 10, "seconds": 0.3}], route="/v1/embeddings",
                            body={"input": ["x"]})
    failed = [r for r in results(lines) if not r["ok"]]
    assert failed and failed[0]["status"] == 422 and "[redacted]" in failed[0]["error"]
    assert all(s not in text for s in SECRETS)


async def test_page_going_away_stops_the_run(client, vast_api):
    vast_api.state["image_delay"] = 5
    resp = await client.post("/api/load", headers=AUTH, json={
        "endpoint": 7, "route": IMAGES, "body": {"prompt": "x"},
        "profile": [{"from": 5, "to": 5, "seconds": 60}]})
    await asyncio.wait_for(resp.content.readline(), 5)  # start
    await asyncio.wait_for(resp.content.readline(), 5)  # first tick: requests are in flight
    resp.close()
    for _ in range(150):
        if not ui._loads:
            break
        await asyncio.sleep(0.02)
    assert not ui._loads


async def test_a_load_run_cancels_its_requests_in_flight_when_the_page_goes():
    cancelled = []

    class Slow:
        async def request(self, *a, **kw):
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled.append(1)
                raise

    async def send(obj):
        if obj["type"] == "tick":
            raise ui.PageGone()
    c = ui.Call(7, IMAGES, {"prompt": "x"})
    with pytest.raises(ui.PageGone):
        await ui.run_load(send, Slow(), c, [(10.0, 10.0, 60.0)], False, unique=True)
    for _ in range(10):
        await asyncio.sleep(0)
    assert len(cancelled) >= 5  # about 10 were sent in the first second; none left running


def test_one_key_cannot_take_every_slot():
    held = collections.Counter()
    assert ui.take_slot(held, "a", 3, 2, "load runs", "running") is None
    assert ui.take_slot(held, "a", 3, 2, "load runs", "running") is None
    assert "You already have 2 load runs running" in ui.take_slot(held, "a", 3, 2, "load runs", "running")
    assert ui.take_slot(held, "b", 3, 2, "load runs", "running") is None  # another user still can
    assert "on this server" in ui.take_slot(held, "c", 3, 2, "load runs", "running")
    ui.give_slot(held, "a"), ui.give_slot(held, "a"), ui.give_slot(held, "b")
    assert not held


async def test_runs_starting_together_cannot_pass_the_cap(client, monkeypatch):
    monkeypatch.setattr(ui, "MAX_LOADS", 1)
    starts = [client.post("/api/load", headers=AUTH, json={
        "endpoint": 7, "route": IMAGES, "body": {"prompt": "x"},
        "profile": [{"from": 1, "to": 1, "seconds": 1}]}) for _ in range(3)]
    statuses = sorted([(await r.read(), r.status)[1] for r in await asyncio.gather(*starts)])
    assert statuses == [200, 503, 503]
    assert not ui._loads


async def test_a_failure_after_the_stream_starts_ends_it_cleanly(client, monkeypatch, logs):
    async def broken(send, *a, **kw):
        await send({"type": "start"})
        raise RuntimeError(f"broke near {SECRETS[0]}")
    monkeypatch.setattr(ui, "run_load", broken)
    lines, text = await asyncio.wait_for(run(client, [{"from": 1, "to": 1, "seconds": 1}]), 5)
    assert [line["type"] for line in lines] == ["start", "error"]
    assert lines[1]["error"] == f"RuntimeError: broke near {ui.REDACTED}"
    assert SECRETS[0] not in text + logs.getvalue()
    assert not ui._loads


def test_tagging_leaves_a_malformed_chat_batch_alone():
    body = {"messages": [["not a message"]]}
    assert ui.tag_body(body, "[t] ") == body


@pytest.mark.parametrize("profile", [
    None, [], [{"from": 1, "to": 1}], [{"from": -1, "to": 1, "seconds": 1}],
    [{"from": 1, "to": 99, "seconds": 1}], [{"from": 1, "to": 1, "seconds": 0}],
    [{"from": 1, "to": 1, "seconds": 1000}, {"from": 1, "to": 1, "seconds": 1000}],
])
async def test_bad_profiles(client, profile):
    resp = await client.post("/api/load", headers=AUTH, json={
        "endpoint": 7, "route": IMAGES, "body": {}, "profile": profile})
    assert resp.status == 400


async def test_limits(client, monkeypatch):
    profile = [{"from": 1, "to": 1, "seconds": 1}]
    resp = await client.post("/api/load", headers=AUTH, json={
        "endpoint": 7, "route": "/v1/chat/completions", "body": {"stream": True}, "profile": profile})
    assert resp.status == 400
    resp = await client.post("/api/load", headers=AUTH, json={
        "endpoint": 7, "route": IMAGES, "body": {}, "profile": profile, "arrivals": "burst"})
    assert resp.status == 400
    monkeypatch.setattr(ui, "_loads", collections.Counter({"others": ui.MAX_LOADS}))
    resp = await client.post("/api/load", headers=AUTH, json={
        "endpoint": 7, "route": IMAGES, "body": {}, "profile": profile})
    assert resp.status == 503


def test_the_profile_is_counted_by_its_area():
    profile = [(10.0, 30.0, 2.0), (30.0, 30.0, 1.0)]  # a ramp, then a hold
    assert ui.expected_by(profile, 1.0) == 15.0  # (10 + 20) / 2 over the first second
    assert ui.expected_by(profile, 99) == ui.expected_requests(profile) == 70.0


async def test_one_key_gets_only_its_share_of_load_runs(client, monkeypatch):
    """The per-key limit, through the handler: a second run on the same key is refused while
    the first holds its slot."""
    monkeypatch.setattr(ui, "MAX_LOADS_PER_KEY", 1)
    monkeypatch.setattr(ui, "_loads", collections.Counter({ui.key_hash(AUTH["Authorization"].split()[1]): 1}))
    resp = await client.post("/api/load", headers=AUTH, json={
        "endpoint": 7, "route": IMAGES, "body": {"prompt": "x"}, "profile": [{"from": 1, "to": 1, "seconds": 1}]})
    assert resp.status == 503 and "You already have 1 load runs running" in (await resp.json())["error"]
