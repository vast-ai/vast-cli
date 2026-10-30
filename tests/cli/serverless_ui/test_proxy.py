"""/v1: the OpenAI-compatible proxy, driven by the real openai client."""
import asyncio
import json
from unittest import mock

import openai
import pytest
from aiohttp.test_utils import make_mocked_request
from openai import AsyncOpenAI

from vastai.serverless.ui import server as ui
from .fake_vast import KEY, SERVED_MODEL, WAV, assert_clean

CHAT = [{"role": "user", "content": "hi"}]
MODEL = SERVED_MODEL  # what endpoint 7's template serves
_clients: list = []


@pytest.fixture
async def proxy(aiohttp_client, vast_api):
    base = str(vast_api.make_url("")).rstrip("/")
    return await aiohttp_client(ui.make_app(base, autoscaler_url=base, api_key=KEY))


@pytest.fixture(autouse=True)
async def close_clients():
    """Each client's connection pool closes with its test, not after its event loop has gone."""
    yield
    while _clients:
        await _clients.pop().close()


def client_at(server, path: str = "/v1", api_key: str = "unused") -> AsyncOpenAI:
    """An OpenAI client for this server. The placeholder key is what users set: with a server
    key, the client's is ignored."""
    client = AsyncOpenAI(base_url=str(server.make_url(path)), api_key=api_key, max_retries=0)
    _clients.append(client)
    return client


def oai(proxy, path: str = "/v1") -> AsyncOpenAI:
    return client_at(proxy, path)


async def test_models_lists_what_each_endpoint_serves(proxy):
    models = await oai(proxy).models.list()
    assert [(m.id, m.endpoint) for m in models.data] == [(MODEL, "flux-demo")]
    assert models.data[0].owned_by == "vllm" and models.data[0].created == 0  # the fake's created_at


async def test_chat(proxy, vast_api, logs):
    raw = await oai(proxy).chat.completions.with_raw_response.create(
        model=MODEL, messages=CHAT, max_tokens=16)
    assert raw.parse().choices[0].message.content == "echo: hi"
    assert raw.headers["x-vast-endpoint"] == "flux-demo"
    assert raw.headers["x-vast-worker"] == f"127.0.0.1:{vast_api.port}"
    assert vast_api.state["payloads"][-1]["max_tokens"] == 16  # body sent as given
    assert vast_api.state["routed"][-1] == {"cost": 16}
    assert_clean(raw.http_response.text, logs.getvalue())


async def test_streamed_chat_is_server_sent_events(proxy, logs):
    stream = await oai(proxy).chat.completions.create(
        model=MODEL, messages=CHAT, stream=True, stream_options={"include_usage": True})
    words, usage = [], None
    async for chunk in stream:
        if chunk.choices:
            words.append(chunk.choices[0].delta.content)
        usage = chunk.usage or usage
    assert "".join(words) == "Hello there" and usage.completion_tokens == 2
    assert_clean(logs.getvalue())


async def test_endpoint_name_also_picks_the_endpoint(proxy):
    reply = await oai(proxy).chat.completions.create(model="flux-demo", messages=CHAT)
    assert reply.choices[0].message.content == "echo: hi"


async def test_model_lookups_are_shared_and_reused(proxy, vast_api):
    """OpenAI front ends poll /v1/models; each distinct template is looked up once per index,
    and an index is rebuilt at most every MODELS_FRESH seconds."""
    groups = vast_api.state["workergroups"]
    groups += [{**groups[0], "id": 100 + i} for i in range(5)]  # five more groups, same template
    for _ in range(3):
        assert (await proxy.get("/v1/models")).status == 200
    distinct = len({g["template_hash"] or g["template_id"] for g in groups})
    assert vast_api.state["template_calls"] == distinct


async def test_an_endpoint_name_as_model_routes_and_becomes_its_model(proxy, vast_api):
    """/v1 picks an endpoint by its served model or its name. The worker (vLLM) accepts only the
    model it serves, so a name that picked the endpoint is replaced by that endpoint's model."""
    reply = await oai(proxy).chat.completions.create(model="flux-demo", messages=CHAT)
    assert reply.choices[0].message.content == "echo: hi"
    assert vast_api.state["payloads"][-1]["model"] == MODEL
    with pytest.raises(openai.NotFoundError):  # a model is never replaced on the /e/ path
        await oai(proxy, "/e/flux-demo/v1").chat.completions.create(model="flux-demo", messages=CHAT)


async def test_unknown_model_is_openai_shaped_404(proxy):
    with pytest.raises(openai.NotFoundError) as e:
        await oai(proxy).chat.completions.create(model="nope", messages=CHAT)
    assert e.value.code == "model_not_found" and MODEL in e.value.message


async def test_worker_errors_keep_their_status_and_are_scrubbed(proxy, logs):
    with pytest.raises(openai.UnprocessableEntityError) as e:
        await oai(proxy).embeddings.create(model=MODEL, input="x")
    assert e.value.response.headers["x-vast-worker"]
    assert "[redacted]" in e.value.message
    assert_clean(e.value.response.text, logs.getvalue())


async def test_media_comes_back_as_sent(proxy):
    resp = await proxy.post("/v1/audio/speech", json={"model": MODEL, "input": "hi"})
    assert resp.status == 200 and resp.content_type == "audio/wav"
    assert await resp.read() == WAV and resp.headers["X-Vast-Worker"]


async def test_worker_id_is_learned_in_the_background(proxy):
    first = await oai(proxy).chat.completions.with_raw_response.create(model=MODEL, messages=CHAT)
    assert "x-vast-worker-id" not in first.headers  # not held up by the lookup
    for _ in range(100):
        if ui.KNOWN_WORKERS:
            break
        await asyncio.sleep(0.02)
    second = await oai(proxy).chat.completions.with_raw_response.create(model=MODEL, messages=CHAT)
    assert second.headers["x-vast-worker-id"] == "1001"


async def test_key_order(aiohttp_client, vast_api, proxy):
    base = str(vast_api.make_url("")).rstrip("/")
    keyless = await aiohttp_client(ui.make_app(base, autoscaler_url=base))
    body = {"model": MODEL, "messages": CHAT}
    resp = await keyless.post("/v1/chat/completions", json=body)
    assert resp.status == 401 and (await resp.json())["error"]["type"] == "authentication_error"
    # With no server key, the client's bearer token is the key.
    resp = await keyless.post("/v1/chat/completions", json=body, headers={"Authorization": f"Bearer {KEY}"})
    assert resp.status == 200
    # The page connects with the server's key, and says whether there is one.
    assert (await (await proxy.get("/api/server")).json()) == {"has_key": True, "needs_token": False}
    assert (await keyless.get("/api/server")).status == 200
    assert (await proxy.post("/api/endpoints")).status == 200
    assert (await keyless.post("/api/endpoints")).status == 401


async def test_other_sites_and_foreign_hosts_are_refused(proxy):
    body = {"model": MODEL, "messages": CHAT}
    resp = await proxy.post("/v1/chat/completions", json=body, headers={"Origin": "https://evil.example"})
    assert resp.status == 403
    resp = await proxy.post("/api/endpoints", headers={"Origin": "https://evil.example"})
    assert resp.status == 403
    # DNS rebinding: evil.example resolving to 127.0.0.1 still arrives with its own Host.
    resp = await proxy.post("/v1/chat/completions", json=body, headers={"Host": "evil.example:8765"})
    assert resp.status == 403
    own = f"http://{proxy.host}:{proxy.port}"
    assert (await proxy.post("/api/endpoints", headers={"Origin": own})).status == 200


async def test_a_server_bound_beyond_localhost_answers_only_to_its_names(aiohttp_client, vast_api):
    base = str(vast_api.make_url("")).rstrip("/")
    lan = await aiohttp_client(ui.make_app(base, autoscaler_url=base, api_key=KEY,
                                                allowed_hosts=ui.LOOPBACK | {"console.lan"}))
    page = {"Host": "console.lan:8765", "Origin": "http://console.lan:8765"}
    assert (await lan.post("/api/endpoints", headers=page)).status == 200
    behind_tls = {"Host": "console.lan", "Origin": "https://console.lan"}  # a TLS proxy in front
    assert (await lan.post("/api/endpoints", headers=behind_tls)).status == 200
    # After DNS rebinding, Origin and Host both carry the attacker's name, so they match.
    rebound = {"Host": "evil.example:8765", "Origin": "http://evil.example:8765"}
    for path in ("/api/endpoints", "/v1/chat/completions"):
        resp = await lan.post(path, headers=rebound, json={"model": MODEL, "messages": CHAT})
        assert resp.status == 403 and "--allowed-host evil.example" in await resp.text()
    assert (await lan.get("/api/server", headers={"Host": "[::1]"})).status == 200  # IPv6, no port


async def test_bad_requests(proxy):
    resp = await proxy.post("/v1/nope", json={"model": MODEL})
    assert resp.status == 404
    resp = await proxy.post("/v1/chat/completions", data="x", headers={"Content-Type": "text/plain"})
    assert resp.status == 415
    resp = await proxy.post("/v1/chat/completions", json={"messages": CHAT})
    assert resp.status == 400


@pytest.fixture
def two_serve_it(vast_api):
    """Endpoint 8 (flux-b) serves the same model as endpoint 7 (flux-demo)."""
    vast_api.state["endpoints"] = [7, 8]
    vast_api.state["workergroups"][1]["template_hash"] = vast_api.state["workergroups"][0]["template_hash"]


async def prefer_app(aiohttp_client, vast_api, prefer=()):
    base = str(vast_api.make_url("")).rstrip("/")
    return await aiohttp_client(ui.make_app(base, autoscaler_url=base, api_key=KEY, prefer=prefer))


def at(proxy, endpoint) -> AsyncOpenAI:
    return client_at(proxy, f"/e/{endpoint}/v1")


async def test_the_path_picks_the_endpoint_by_name_or_id(proxy, vast_api, two_serve_it):
    for which in ("flux-b", "8"):
        raw = await at(proxy, which).chat.completions.with_raw_response.create(model=MODEL, messages=CHAT)
        assert raw.headers["x-vast-endpoint"] == "flux-b"
    models = await at(proxy, "flux-b").models.list()
    assert [(m.id, m.endpoint) for m in models.data] == [(MODEL, "flux-b")]


async def test_the_path_fills_in_a_missing_model_and_never_replaces_one(proxy, vast_api):
    resp = await proxy.post("/e/flux-demo/v1/chat/completions", json={"messages": CHAT, "model": None})
    assert resp.status == 200 and vast_api.state["payloads"][-1]["model"] == MODEL
    resp = await proxy.post("/e/flux-demo/v1/chat/completions", json={"messages": CHAT, "model": "served-as"})
    assert vast_api.state["payloads"][-1]["model"] == "served-as"


async def test_unknown_endpoint_in_the_path(proxy):
    resp = await proxy.post("/e/nope/v1/chat/completions", json={"messages": CHAT})
    assert resp.status == 404 and (await resp.json())["error"]["code"] == "endpoint_not_found"
    assert (await proxy.get("/e/nope/v1/models")).status == 404
    # Refused like any other request from another site.
    resp = await proxy.post("/e/flux-demo/v1/chat/completions", json={"messages": CHAT},
                            headers={"Origin": "https://evil.example"})
    assert resp.status == 403


async def test_two_endpoints_one_model_needs_a_choice(proxy, two_serve_it):
    with pytest.raises(openai.BadRequestError) as e:
        await oai(proxy).chat.completions.create(model=MODEL, messages=CHAT)
    assert e.value.code == "ambiguous_model" and "--prefer" in e.value.message


async def test_prefer_breaks_the_tie_in_order(aiohttp_client, vast_api, two_serve_it):
    proxy = await prefer_app(aiohttp_client, vast_api, prefer=("gone", "8", "flux-demo"))
    raw = await oai(proxy).chat.completions.with_raw_response.create(model=MODEL, messages=CHAT)
    assert raw.headers["x-vast-endpoint"] == "flux-b"  # "gone" serves nothing; 8 is next
    # A path still wins over the preference.
    raw = await at(proxy, "flux-demo").chat.completions.with_raw_response.create(model=MODEL, messages=CHAT)
    assert raw.headers["x-vast-endpoint"] == "flux-demo"
    assert vast_api.state["routed_to"] == ["flux-b", "flux-demo"]  # where the SDK really sent them


async def traffic_lines(proxy, done, key_headers=None, limit=50, subscribed=None):
    """Lines of /api/traffic for endpoint 7 until done(lines) holds. subscribed (an Event) is
    set once the history line has come: the page is watching from then on."""
    resp = await proxy.post("/api/traffic", json={"endpoint": 7}, headers=key_headers or {})
    assert resp.status == 200, await resp.text()
    lines, raw = [], []
    for _ in range(limit):
        line = await asyncio.wait_for(resp.content.readline(), 5)
        raw.append(line.decode())
        lines.append(json.loads(line))
        if subscribed is not None:
            subscribed.set()
        if done(lines):
            break
    resp.close()
    return lines, "".join(raw)


def finished(n):
    return lambda lines: sum(l.get("state") in ("done", "failed") for l in lines) >= n


async def test_proxied_requests_are_shown_live(proxy, vast_api, logs):
    subscribed = asyncio.Event()
    watching = asyncio.create_task(traffic_lines(proxy, finished(3), subscribed=subscribed))
    await asyncio.wait_for(subscribed.wait(), 5)  # the page is watching before the requests start
    client = oai(proxy)
    await client.chat.completions.create(model=MODEL, messages=[{"role": "system", "content": "be brief"}] + CHAT,
                                         max_tokens=16)
    stream = await client.chat.completions.create(model=MODEL, messages=CHAT, stream=True,
                                                  stream_options={"include_usage": True})
    async for _ in stream:
        pass
    with pytest.raises(openai.UnprocessableEntityError):
        await client.embeddings.create(model=MODEL, input="x")
    lines, raw = await watching
    assert lines[0] == {"type": "history", "requests": [], "withheld": False}
    final = {}
    for line in lines[1:]:
        final[line["id"]] = line  # each change is a whole snapshot
    plain, streamed, broken = final.values()
    worker = f"http://127.0.0.1:{vast_api.port}"
    assert plain["state"] == "done" and plain["prompt"] == "hi" and plain["reply"] == "echo: hi"
    assert plain["endpoint"] == "flux-demo" and plain["worker"] == worker and plain["status"] == 200
    assert streamed["state"] == "done" and streamed["reply"] == "Hello there" and streamed["tokens"] == 2
    assert streamed["ttft"] is not None and streamed["chunks"] == 3
    assert broken["state"] == "failed" and broken["status"] == 422 and "[redacted]" in broken["error"]
    states = [l["state"] for l in lines[1:] if l["id"] == streamed["id"]]
    assert states[0] == "routing" and "streaming" in states and states[-1] == "done"
    assert all("_who" not in l for l in lines)
    assert_clean(raw, logs.getvalue())


async def test_history_and_who_sees_it(proxy, aiohttp_client, vast_api):
    await oai(proxy).chat.completions.create(model=MODEL, messages=CHAT)
    lines, _ = await traffic_lines(proxy, lambda ls: True)  # the server's key
    assert [r["reply"] for r in lines[0]["requests"]] == ["echo: hi"]
    other = {"Authorization": "Bearer some-other-key-0123456789"}
    lines, _ = await traffic_lines(proxy, lambda ls: True, other)
    assert len(lines[0]["requests"]) == 1  # the server's key's traffic: anyone here can use it
    # Without a server key, each client's key is its own, and its traffic stays its own.
    base = str(vast_api.make_url("")).rstrip("/")
    keyless = await aiohttp_client(ui.make_app(base, autoscaler_url=base))
    resp = await keyless.post("/v1/chat/completions", json={"model": MODEL, "messages": CHAT},
                              headers={"Authorization": f"Bearer {KEY}"})
    assert resp.status == 200
    lines, _ = await traffic_lines(keyless, lambda ls: True, {"Authorization": f"Bearer {KEY}"})
    assert len(lines[0]["requests"]) == 1
    lines, _ = await traffic_lines(keyless, lambda ls: True, other)
    assert lines[0]["requests"] == []


async def test_a_shared_server_never_shows_its_keys_traffic(aiohttp_client, vast_api):
    """Bound beyond localhost, the server key's traffic is other people's prompts: not in the
    history, and not live. Live is checked by order, not time: the listener's queue is first in,
    first out, so a leaked row would arrive before the one published after it."""
    base = str(vast_api.make_url("")).rstrip("/")
    shared = await aiohttp_client(ui.make_app(base, autoscaler_url=base, api_key=KEY, share_traffic=False))
    await oai(shared).chat.completions.create(model=MODEL, messages=CHAT)  # made with the server's key
    lines, _ = await traffic_lines(shared, lambda ls: True)
    assert lines[0] == {"type": "history", "requests": [], "withheld": True}
    mine = {"Authorization": "Bearer some-other-key-0123456789"}
    resp = await shared.post("/api/traffic", json={}, headers=mine)
    assert json.loads(await asyncio.wait_for(resp.content.readline(), 5))["type"] == "history"
    traffic = shared.app[ui.TRAFFIC]
    traffic.start(ui.key_hash(KEY), endpoint_id=7, prompt="someone else's prompt")
    sentinel = traffic.start(ui.key_hash("some-other-key-0123456789"), endpoint_id=7, prompt="mine")
    line = json.loads(await asyncio.wait_for(resp.content.readline(), 5))
    resp.close()
    assert line["id"] == sentinel["id"] and line["prompt"] == "mine"


def test_known_workers_keep_the_most_recently_seen(monkeypatch):
    monkeypatch.setattr(ui, "KNOWN_WORKERS", {})
    monkeypatch.setattr(ui, "KNOWN_WORKERS_MAX", 3)
    ui.know_workers({"a:1": 1, "b:1": 2, "c:1": 3})
    ui.know_workers({"a:1": 1})  # seen again
    ui.know_workers({"d:1": 4})
    assert ui.KNOWN_WORKERS == {"c:1": 3, "a:1": 1, "d:1": 4}


async def test_live_traffic_stays_with_the_key_that_made_it(aiohttp_client, vast_api, monkeypatch):
    monkeypatch.setattr(ui, "TRAFFIC_PING", 0.05)
    base = str(vast_api.make_url("")).rstrip("/")
    keyless = await aiohttp_client(ui.make_app(base, autoscaler_url=base))
    other = {"Authorization": "Bearer some-other-key-0123456789"}
    watch = await keyless.post("/api/traffic", json={}, headers=other)
    assert json.loads(await watch.content.readline()) == {"type": "history", "requests": [], "withheld": False}
    resp = await keyless.post("/v1/chat/completions", json={"model": MODEL, "messages": CHAT},
                              headers={"Authorization": f"Bearer {KEY}"})
    assert resp.status == 200
    seen = [json.loads(await asyncio.wait_for(watch.content.readline(), 5)) for _ in range(5)]
    watch.close()
    assert [line["type"] for line in seen] == ["ping"] * 5, seen


def test_worker_errors_keep_the_workers_message():
    detail = ui.worker_error({"status": 422, "response": {"detail": "field required"}}, {})
    assert detail.status == 422 and "field required" in json.loads(detail.text)["error"]["message"]
    bare = ui.worker_error({"status": 400, "response": {"error": {"type": "x"}}}, {})
    assert bare.status == 400  # OpenAI-shaped, though without a message: passed on as it is


def test_replies_are_served_only_as_safe_types():
    page = ui.reply({"response": b"<script>x</script>", "content_type": "text/html"}, {})
    assert page.content_type == "application/octet-stream" and page.headers["Content-Disposition"] == "attachment"
    svg = ui.reply({"response": b"<svg/>", "content_type": "image/svg+xml"}, {})
    assert svg.content_type == "application/octet-stream"
    audio = ui.reply({"response": WAV, "content_type": "audio/wav"}, {})
    assert audio.content_type == "audio/wav" and "Content-Disposition" not in audio.headers
    text = ui.reply({"response": "<b>hi</b>", "content_type": "text/html"}, {})
    assert text.content_type == "text/plain"
    vtt = ui.reply({"response": "WEBVTT", "content_type": "text/vtt; charset=utf-8"}, {})
    assert vtt.content_type == "text/vtt"


async def test_all_endpoints_and_worker_ids(proxy, vast_api):
    await oai(proxy).chat.completions.create(model=MODEL, messages=CHAT)
    for _ in range(100):  # the first request starts the worker lookup
        if ui.KNOWN_WORKERS:
            break
        await asyncio.sleep(0.02)
    await oai(proxy).chat.completions.create(model=MODEL, messages=CHAT)
    resp = await proxy.post("/api/traffic", json={})  # no endpoint: all of them
    history = __import__("json").loads(await asyncio.wait_for(resp.content.readline(), 5))
    resp.close()
    first, second = history["requests"]
    assert first["endpoint"] == second["endpoint"] == "flux-demo"
    assert first.get("worker_id") is None and second["worker_id"] == 1001


async def test_a_page_that_goes_away_stops_listening(proxy, monkeypatch):
    monkeypatch.setattr(ui, "TRAFFIC_PING", 0.05)  # the keepalive is what notices
    await traffic_lines(proxy, lambda ls: True)
    listeners = proxy.app[ui.TRAFFIC].listeners
    for _ in range(100):
        if not listeners:
            break
        await asyncio.sleep(0.02)
    assert not listeners


async def test_transcription_upload_from_the_openai_client(proxy, vast_api, logs):
    audio = WAV * 100
    text = await oai(proxy).audio.transcriptions.create(model=MODEL, file=("talk.wav", audio, "audio/wav"),
                                                        language="en")
    assert text.text == f"heard talk.wav ({len(audio)} bytes)"  # the file arrived intact
    sent = vast_api.state["payloads"][-1]
    assert sent["filename"] == "talk.wav" and sent["language"] == "en" and sent["model"] == MODEL
    assert_clean(logs.getvalue())


async def test_text_replies_come_back_as_text(proxy):
    text = await oai(proxy).audio.translations.create(model=MODEL, file=("a.wav", WAV, "audio/wav"),
                                                      response_format="text")
    assert text.strip() == f"heard a.wav ({len(WAV)} bytes)"


async def test_image_edit_with_several_images(proxy, vast_api):
    images = [("a.png", b"\x89PNG one"), ("b.png", b"\x89PNG three")]
    raw = await oai(proxy).images.with_raw_response.edit(model=MODEL, image=images, prompt="snow")
    assert raw.http_response.json()["edited"] == [8, 10]
    assert vast_api.state["payloads"][-1]["filename"] == ["a.png", "b.png"]
    assert raw.headers["x-vast-worker"]


async def test_other_upload_fields_keep_their_names(proxy, vast_api):
    import aiohttp
    form = aiohttp.FormData()
    form.add_field("model", MODEL)
    form.add_field("prompt", "a kite")
    form.add_field("input_reference", b"\x89PNG ref", filename="ref.png", content_type="image/png")
    resp = await proxy.post("/v1/videos/sync", data=form)
    assert resp.status == 200 and resp.content_type == "video/mp4"
    assert await resp.read() == b"fake mp4 from 8 bytes"
    assert vast_api.state["payloads"][-1]["input_reference_filename"] == "ref.png"


async def test_an_access_token_guards_everything_but_the_page(aiohttp_client, vast_api, logs):
    token = "ui-token-0123456789-abcd"
    base = str(vast_api.make_url("")).rstrip("/")
    shared = await aiohttp_client(ui.make_app(base, autoscaler_url=base, api_key=KEY, access_token=token))
    assert (await shared.get("/")).status == 200
    assert (await (await shared.get("/api/server")).json()) == {"has_key": True, "needs_token": True}
    for headers in ({}, {"X-Serverless-UI-Token": "wrong-token-0123456789"}, {"Authorization": f"Bearer {token}"}):
        resp = await shared.post("/api/endpoints", headers=headers)  # the page's bearer is a Vast key, not this
        assert resp.status == 401 and (await resp.json())["token"] is True, headers
    assert (await shared.post("/api/endpoints", headers={"X-Serverless-UI-Token": token})).status == 200
    # OpenAI clients send it as their API key
    reply = await client_at(shared, api_key=token).chat.completions.create(model=MODEL, messages=CHAT)
    assert reply.choices[0].message.content == "echo: hi"
    with pytest.raises(openai.AuthenticationError, match="access token"):
        await oai(shared).chat.completions.create(model=MODEL, messages=CHAT)
    assert (await shared.get("/v1/models", headers={"X-Serverless-UI-Token": token})).status == 200
    assert token not in logs.getvalue()


async def test_uploads_are_limited_in_total_not_just_per_part(proxy, monkeypatch):
    """aiohttp caps each part at the body limit; parts under it must not add up past it."""
    monkeypatch.setattr(ui, "MAX_BODY", 1000)
    with pytest.raises(openai.APIStatusError) as refused:
        await oai(proxy).audio.transcriptions.create(
            model=MODEL, file=("a.wav", b"x" * 600, "audio/wav"), prompt="y" * 600)
    assert refused.value.status_code == 413 and "upload" in str(refused.value)


async def test_a_key_rejected_mid_request_closes_its_traffic_row(proxy, vast_api):
    """The model index is cached, so the key can be refused after the row has started."""
    await oai(proxy).chat.completions.create(model=MODEL, messages=CHAT)  # caches the index
    vast_api.state["mode"] = "bad-key"
    with pytest.raises(openai.AuthenticationError):
        await oai(proxy).chat.completions.create(model=MODEL, messages=CHAT)
    rows = list(proxy.app[ui.TRAFFIC].recent.values())
    assert rows[-1]["state"] == "failed" and "rejected" in rows[-1]["error"]


@pytest.mark.parametrize("data", [
    b"garbage",                                                               # no boundary
    b"--x\r\nnot a part",                                                      # a broken header
    b"--x\r\nContent-Disposition: form-data\r\n\r\nabc\r\n--x--\r\n",          # a part with no name
])
async def test_a_malformed_upload_is_the_callers_error(proxy, data):
    resp = await asyncio.wait_for(proxy.post(
        "/e/flux-demo/v1/audio/transcriptions", data=data,
        headers={"Content-Type": "multipart/form-data; boundary=x"}), 5)
    assert resp.status == 400 and (await resp.json())["error"]["type"] == "invalid_request_error"


async def test_proxy_replies_are_not_cached(proxy):
    resp = await proxy.post("/v1/chat/completions", json={"model": MODEL, "messages": CHAT})
    assert resp.status == 200 and resp.headers["Cache-Control"] == "no-store"


async def test_without_a_server_key_the_token_comes_in_its_header(aiohttp_client, vast_api):
    """Callers' bearer is then their own Vast key, so the token can't travel there."""
    token = "ui-token-0123456789-abcd"
    base = str(vast_api.make_url("")).rstrip("/")
    keyless = await aiohttp_client(ui.make_app(base, autoscaler_url=base, access_token=token))
    own_key = {"Authorization": f"Bearer {KEY}"}
    body = {"model": MODEL, "messages": CHAT}
    refused = await keyless.post("/v1/chat/completions", json=body, headers=own_key)
    assert refused.status == 401 and "X-Serverless-UI-Token header" in (await refused.json())["error"]["message"]
    as_bearer = await keyless.post("/v1/chat/completions", json=body, headers={"Authorization": f"Bearer {token}"})
    assert as_bearer.status == 401
    ok = await keyless.post("/v1/chat/completions", json=body, headers={**own_key, "X-Serverless-UI-Token": token})
    assert ok.status == 200


async def test_a_worker_stream_that_breaks_is_a_failure_not_the_client_leaving():
    """A reset from the worker's side ends the client's stream with an error and marks the
    traffic row failed; only a failed write to the client counts as it leaving."""
    async def chunks():
        yield {"choices": [{"delta": {"content": "Hel"}}]}
        raise ConnectionResetError("the worker went away")
    client = mock.Mock()  # the connection to the client: what it was sent
    client.write, client.write_headers, client.write_eof, client.drain = (
        mock.AsyncMock(), mock.AsyncMock(), mock.AsyncMock(), mock.AsyncMock())
    request = make_mocked_request("POST", "/v1/chat/completions", app=ui.make_app(), writer=client)
    row = request.app[ui.TRAFFIC].start("who", route="/v1/chat/completions")
    await ui.relay_sse(request, {"response": chunks()}, {}, row, 0.0)
    assert row["state"] == "failed" and "the worker went away" in row["error"]
    sent = b"".join(bytes(c.args[0]) for c in client.write.call_args_list).decode()
    assert '"Hel"' in sent and "the worker went away" in sent and sent.endswith("data: [DONE]\n\n")


def test_the_traffic_view_never_fails_a_request_it_describes():
    """Previews read the bodies and replies of any worker: an odd shape gives an empty preview,
    not an exception after the worker has answered (and been paid)."""
    assert ui.preview(ui.reply_preview, {"response": {"output": [{"filename": None}]}}) == ""
    odd = {"messages": [{"role": "user", "content": [{"type": "text", "text": None}]}]}
    assert ui.preview(ui.prompt_preview, odd) == ""
    assert ui.preview(ui.prompt_preview, {"messages": CHAT}) == "hi"


async def test_a_prefix_or_extension_of_the_token_is_refused(aiohttp_client, vast_api):
    token = "ui-token-0123456789-abcd"
    base = str(vast_api.make_url("")).rstrip("/")
    app = await aiohttp_client(ui.make_app(base, autoscaler_url=base, api_key=KEY, access_token=token))
    for given in (token[:-1], token[:1], token + "x", token.upper()):
        resp = await app.post("/api/endpoints", headers={"X-Serverless-UI-Token": given})
        assert resp.status == 401, given
    assert (await app.post("/api/endpoints", headers={"X-Serverless-UI-Token": token})).status == 200


async def test_a_page_on_another_local_port_is_refused(proxy):
    """Another web app on this machine is another origin, though the host is the same."""
    resp = await proxy.post("/api/endpoints", headers={"Origin": "http://127.0.0.1:1"})
    assert resp.status == 403


async def test_a_request_no_worker_answers_in_time_is_a_504(aiohttp_client, vast_api, logs):
    """--request-timeout covers waiting for a worker and its answer starting, together."""
    base = str(vast_api.make_url("")).rstrip("/")
    quick = await aiohttp_client(ui.make_app(base, autoscaler_url=base, api_key=KEY, request_timeout=0.3))
    vast_api.state["chat_delay"] = 5
    with pytest.raises(openai.APIStatusError) as late:
        await client_at(quick).chat.completions.create(model=MODEL, messages=CHAT)
    assert late.value.status_code == 504 and "within 0.3s (--request-timeout)" in str(late.value)
    [row] = quick.app[ui.TRAFFIC].recent.values()
    assert row["state"] == "failed" and "within 0.3s" in row["error"]
    page = await quick.post("/api/call", json={"endpoint": 7, "route": "/v1/chat/completions",
                                               "body": {"model": MODEL, "messages": CHAT}})
    assert page.status == 504 and "--request-timeout" in (await page.json())["error"]


async def test_a_client_that_goes_away_takes_its_request_with_it(proxy, vast_api):
    """The client gave up (timed out, retried, closed): the request is cancelled all the way to
    the worker, rather than waiting on and running unread. The traffic view says so."""
    vast_api.state["chat_delay"] = 30
    asking = asyncio.create_task(proxy.post("/v1/chat/completions", json={"model": MODEL, "messages": CHAT}))
    for _ in range(100):  # until the worker has it
        await asyncio.sleep(0.02)
        if vast_api.state.get("payloads"):
            break
    asking.cancel()
    for _ in range(100):
        await asyncio.sleep(0.02)
        rows = list(proxy.app[ui.TRAFFIC].recent.values())
        if vast_api.state.get("chat_cancelled") and rows and rows[-1]["state"] == "cancelled":
            break
    assert vast_api.state.get("chat_cancelled") == 1
    assert rows[-1]["state"] == "cancelled"
