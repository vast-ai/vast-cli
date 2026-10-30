"""POST /api/call and /api/burst through the SDK, against the fake autoscaler and worker."""
import asyncio
import base64
import json

from vastai.serverless.ui import server as ui

from .fake_vast import AUTH, SERVED_MODEL, WAV, assert_clean

CHAT = "/v1/chat/completions"
CHAT_BODY = {"model": SERVED_MODEL, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 32}


async def post(client, path, route, body, endpoint=7, **params):
    return await client.post(path, params=params, headers=AUTH,
                             json={"endpoint": endpoint, "route": route, "body": body})


def lines(text):
    return [json.loads(line) for line in text.splitlines() if line]


async def test_json_call(client, vast_api, logs):
    resp = await post(client, "/api/call", CHAT, CHAT_BODY)
    assert resp.status == 200
    text = await resp.text()
    env = json.loads(text)
    assert env["ok"] and env["status"] == 200 and env["route"] == CHAT
    assert env["response"]["choices"][0]["message"]["content"] == "echo: hi"
    assert env["worker"].startswith("http://127.0.0.1")
    assert env["seconds"] >= 0 and "auth_data" not in env
    assert vast_api.state["payloads"] == [CHAT_BODY]  # sent unchanged
    assert vast_api.state["routed"] == [{"cost": 32}]  # max_tokens is the routing cost
    assert_clean(text, logs.getvalue())


async def test_stream_is_relayed_as_ndjson(client, logs):
    resp = await post(client, "/api/call", CHAT, {**CHAT_BODY, "stream": True})
    assert resp.headers["Content-Type"].startswith("application/x-ndjson")
    assert resp.headers["Cache-Control"] == "no-store"
    assert "connect-src 'self'" in resp.headers["Content-Security-Policy"]
    text = await resp.text()
    events = lines(text)
    assert [e["type"] for e in events] == ["start", "chunk", "chunk", "chunk", "done"]
    words = [e["data"]["choices"][0]["delta"]["content"] for e in events[1:3]]
    assert words == ["Hello", " there"]
    done = events[-1]
    assert done["chunks"] == 3 and done["usage"] == {"completion_tokens": 2}
    assert done["ttft"] is not None and done["tokens_per_second"] > 0
    assert_clean(text, logs.getvalue())


async def test_media_is_returned_as_base64(client):
    env = await (await post(client, "/api/call", "/v1/audio/speech", {"input": "hi"})).json()
    assert env["media"]["type"] == "audio/wav"
    assert base64.b64decode(env["media"]["b64"]) == WAV
    assert "response" not in env


async def test_worker_error_is_a_result_and_scrubbed(client, logs):
    resp = await post(client, "/api/call", "/v1/embeddings", {"input": ["x"]})
    assert resp.status == 200
    text = await resp.text()
    env = json.loads(text)
    assert env["ok"] is False and env["status"] == 422
    assert env["error"].startswith("HTTP 422: bad request to") and "[redacted]" in env["error"]
    assert_clean(text, logs.getvalue())


async def test_stream_flag_ignored_where_the_route_cannot_stream(client):
    env = await (await post(client, "/api/call", "/v1/images/generations",
                            {"prompt": "x", "stream": True})).json()
    assert env["ok"] and env["response"]["data"][0]["b64_json"]


async def test_bad_calls(client):
    for payload in ({}, {"endpoint": 7, "route": CHAT}, {"endpoint": "x", "route": CHAT, "body": {}},
                    {"endpoint": 7, "route": CHAT, "body": []},
                    {"endpoint": 7, "route": "/v1/models", "body": {}}):
        resp = await client.post("/api/call", json=payload, headers=AUTH)
        assert resp.status == 400, payload
    assert (await client.post("/api/call", json={"endpoint": 7, "route": CHAT, "body": {}})).status == 401
    assert (await post(client, "/api/call", CHAT, CHAT_BODY, endpoint=12345)).status == 502


async def test_burst(client, vast_api, logs):
    vast_api.state["image_delay"] = 0.05
    resp = await post(client, "/api/burst", "/v1/images/generations", {"prompt": "x"}, n=5)
    assert resp.status == 200
    text = await resp.text()
    results = lines(text)
    assert sorted(r["index"] for r in results) == [0, 1, 2, 3, 4]
    assert all(r["ok"] for r in results) and len(vast_api.state["payloads"]) == 5
    assert_clean(text, logs.getvalue())


async def test_burst_limits(client):
    for n in ("0", "65", "x"):
        assert (await post(client, "/api/burst", CHAT, CHAT_BODY, n=n)).status == 400
    assert (await post(client, "/api/burst", CHAT, {**CHAT_BODY, "stream": True}, n=2)).status == 400


async def test_a_burst_stops_what_is_left_when_the_page_goes(client, monkeypatch):
    cancelled, started = [], []

    async def request(self, route, body, **kw):
        started.append(1)
        if len(started) == 1:  # the first lands soon, and its line can't be delivered
            await asyncio.sleep(0.2)
            return {"ok": True, "status": 200, "response": {}}
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.append(1)
            raise
    monkeypatch.setattr(ui.Endpoint, "request", request)
    resp = await post(client, "/api/burst", "/v1/images/generations", {"prompt": "x"}, n=4)
    resp.close()
    for _ in range(100):
        if len(cancelled) == 3:
            break
        await asyncio.sleep(0.02)
    assert len(cancelled) == 3


async def test_routing_cost_follows_max_tokens_like_pyworker(client, vast_api):
    await post(client, "/api/call", CHAT, {"messages": [{"role": "user", "content": "x"}]})
    batch = {"max_tokens": 64, "messages": [[{"role": "user", "content": "a"}],
                                            [{"role": "user", "content": "b"}]]}
    await post(client, "/api/call", "/v1/chat/completions/batch", batch)
    assert [r["cost"] for r in vast_api.state["routed"]] == [100, 128]  # default; per conversation
