"""The API key must never be stored, logged or returned.

A fake Vast API echoes the key back in every way it can: in the URL, in the Authorization
header, and in exception text. These tests check that it never reaches a response, a log
line or a file.
"""
import base64
import builtins
import hashlib
import io
import json
import logging
import os
import re
import shutil
import socket
import subprocess
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from vastai.serverless.ui import server as ui
from .fake_vast import AUTH, DOCKER_PASS, HF_TOKEN, KEY, assert_clean

MODEL = "Qwen/Qwen3-8B"
OTHER_KEY = "some-other-key-0123456789"
OTHER = {"Authorization": f"Bearer {OTHER_KEY}"}

PROJECT = Path(ui.__file__).parent


async def test_missing_key_is_rejected_before_any_vast_call(client, monkeypatch):
    def no_client(*a, **kw):
        raise AssertionError("an SDK client was built without a key")
    monkeypatch.setattr(ui, "Serverless", no_client)
    for headers in ({}, {"Authorization": "Bearer "}, {"Authorization": f"Basic {KEY}"}):
        resp = await client.post("/api/endpoints", headers=headers)
        assert resp.status == 401
        assert_clean(await resp.text())


async def test_endpoint_list_omits_endpoint_keys(client, logs):
    resp = await client.post("/api/endpoints", headers=AUTH)
    assert resp.status == 200
    body = await resp.json()
    assert body == {"endpoints": [{"name": "flux-demo", "id": 7, "state": "active"}]}
    assert_clean(await resp.text(), logs.getvalue())


async def test_bad_key_is_a_401(client, vast_api):
    vast_api.state["mode"] = "bad-key"
    resp = await client.post("/api/endpoints", headers=AUTH)
    assert resp.status == 401
    assert await resp.json() == {"error": "Vast rejected this API key."}


async def test_upstream_error_echoing_the_key_is_scrubbed(client, vast_api, logs):
    vast_api.state["mode"] = "reject"
    resp = await client.post("/api/endpoints", headers=AUTH)
    assert resp.status == 502
    text = await resp.text()
    assert "HTTP 401" in text and ui.REDACTED in text
    assert_clean(text, logs.getvalue())
    assert "HTTP 401" in logs.getvalue()  # the failure is logged, just without the key


async def test_exception_text_and_traceback_are_scrubbed(client, monkeypatch, logs):
    async def boom(self):
        raise RuntimeError(f"connect to https://x/?api_key={KEY}&y=1 failed; key {KEY}")
    monkeypatch.setattr(ui.Serverless, "get_endpoints", boom)
    resp = await client.post("/api/endpoints", headers=AUTH)
    assert resp.status == 502
    try:
        raise ValueError(f"traceback carrying {KEY}")
    except ValueError:
        ui.remember_secret(KEY)
        logging.getLogger("x").exception("logged with exc_info")
    assert_clean(await resp.text(), logs.getvalue())


async def test_secrets_are_forgotten_after_the_request():
    async def handler(request):
        ui.remember_secret("a-secret-value-123")
        return web.json_response({})
    request = make_mocked_request("POST", "/api/x", headers={"Host": "127.0.0.1:8765"}, app=ui.make_app())
    await ui.guard(request, handler)
    assert ui._secrets.get() == ()


async def test_the_pages_key_wins_over_the_servers_and_the_proxys_does_not(aiohttp_client, vast_api,
                                                                          monkeypatch):
    used, real = [], ui.Serverless

    def spy(*a, **kw):
        used.append(kw.get("api_key"))
        return real(*a, **kw)
    monkeypatch.setattr(ui, "Serverless", spy)
    base = str(vast_api.make_url("")).rstrip("/")
    keyed = await aiohttp_client(ui.make_app(base, autoscaler_url=base, api_key=KEY))
    assert (await keyed.post("/api/endpoints", headers=OTHER)).status == 200
    assert used == [OTHER_KEY]
    used.clear()
    await keyed.post("/v1/chat/completions", json={"model": MODEL, "messages": [{"role": "user", "content": "hi"}]},
                     headers=OTHER)
    assert used and set(used) == {KEY}


# Code a model writes: shaped like keys, with the quotes and escapes JSON has to carry.
CODE = 'curl -H "Authorization: Bearer $VAST_API_KEY" https://x; OpenAI(api_key="sk-123"); k = os.environ["K"]'


async def test_replies_come_back_as_written_except_for_real_secrets(aiohttp_client, vast_api, client):
    base = str(vast_api.make_url("")).rstrip("/")
    proxy = await aiohttp_client(ui.make_app(base, autoscaler_url=base, api_key=KEY))
    messages = [{"role": "user", "content": f"{CODE} {KEY}"}]
    expected = f"echo: {CODE} {ui.REDACTED}"
    resp = await proxy.post("/v1/chat/completions", json={"model": MODEL, "messages": messages})
    assert (await resp.json())["choices"][0]["message"]["content"] == expected  # valid JSON, unaltered
    vast_api.state["stream_echo"] = True
    resp = await proxy.post("/v1/chat/completions", json={"model": MODEL, "messages": messages, "stream": True})
    events = [line[6:] for line in (await resp.text()).splitlines() if line.startswith("data: ")]
    assert events[-1] == "[DONE]"
    chunks = [json.loads(e) for e in events[:-1]]
    assert "".join(c["choices"][0]["delta"].get("content") or "" for c in chunks if c["choices"]) == expected
    # The page's calls, plain and streamed (NDJSON).
    resp = await client.post("/api/call", headers=AUTH, json={
        "endpoint": 7, "route": "/v1/chat/completions", "body": {"messages": messages}})
    assert (await resp.json())["response"]["choices"][0]["message"]["content"] == expected
    resp = await client.post("/api/call", headers=AUTH, json={
        "endpoint": 7, "route": "/v1/chat/completions", "body": {"messages": messages, "stream": True}})
    lines = [json.loads(line) for line in (await resp.text()).splitlines()]
    assert "".join(l["data"]["choices"][0]["delta"].get("content") or "" for l in lines
                   if l["type"] == "chunk" and l["data"]["choices"]) == expected


async def test_template_secrets_are_scrubbed_though_looked_up_in_parallel(client, monkeypatch, logs):
    """Templates are fetched in a gather; their secrets must still reach the request's scrubber."""
    real = ui.discovery.summarise

    def leaky(groups):
        logging.getLogger("x").warning("summarising with %s and %s", DOCKER_PASS, HF_TOKEN)
        return real(groups)
    monkeypatch.setattr(ui.discovery, "summarise", leaky)
    resp = await client.post("/api/endpoint", json={"id": 7}, headers=AUTH)
    assert resp.status == 200
    assert "summarising with" in logs.getvalue()
    assert DOCKER_PASS not in logs.getvalue() and HF_TOKEN not in logs.getvalue()


def test_scrub_catches_unrecorded_keys_by_shape():
    text = "GET /x?api_key=abc123secret&n=1 Authorization: Bearer tok_987654 'api_key': 'zzz999'"
    assert ui.scrub(text) == ("GET /x?api_key=[redacted]&n=1 Authorization: Bearer [redacted]"
                                   " 'api_key': '[redacted]'")


async def test_security_headers(client):
    page = await client.get("/")
    assert "connect-src 'self'" in page.headers["Content-Security-Policy"]
    assert "form-action 'none'" in page.headers["Content-Security-Policy"]
    # Only the page's own script runs: allowed by its hash, not by 'unsafe-inline'.
    script = re.search(r"<script>(.*?)</script>", await page.text(), re.S).group(1)
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    assert f"script-src 'sha256-{digest}';" in page.headers["Content-Security-Policy"]
    api = await client.post("/api/endpoints", headers=AUTH)
    assert api.headers["Cache-Control"] == "no-store"
    assert api.headers["Referrer-Policy"] == "no-referrer"


async def test_nothing_written_to_disk(client, monkeypatch, vast_api):
    """No file is opened for writing while requests run, failed ones included."""
    written = []
    real_open, real_os_open = builtins.open, os.open

    def spy_open(file, mode="r", *a, **kw):
        if any(c in mode for c in "wax+"):
            written.append(file)
        return real_open(file, mode, *a, **kw)

    def spy_os_open(path, flags, *a, **kw):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
            written.append(path)
        return real_os_open(path, flags, *a, **kw)
    monkeypatch.setattr(builtins, "open", spy_open)
    monkeypatch.setattr(os, "open", spy_os_open)
    assert (await client.post("/api/endpoints", headers=AUTH)).status == 200
    assert (await client.post("/api/endpoint", json={"id": 7}, headers=AUTH)).status == 200
    vast_api.state["mode"] = "reject"
    await client.post("/api/endpoints", headers=AUTH)
    assert written == []


def test_page_never_persists_the_key():
    page = (PROJECT / "index.html").read_text(encoding="utf-8")
    for banned in ("sessionStorage", "indexedDB", "document.cookie", "innerHTML", "location.search"):
        assert banned not in page, banned
    # localStorage holds the access token and nothing else; the token is not a Vast key
    uses = [line for line in page.splitlines() if "localStorage." in line]
    assert uses and all("TOKEN_STORE" in line for line in uses), uses
    # The URL's fragment is read for the access token the server's link carries, and only that
    uses = [line for line in page.splitlines() if "location.hash" in line]
    assert uses and all('get("token")' in line for line in uses), uses
    key_input = re.search(r'<input id="key"[^>]*>', page).group(0)
    assert "name=" not in key_input


def test_the_sdks_own_log_handler_is_scrubbed_too():
    """vastai's logger has its own handler, which records under it reach instead of the root's."""
    stream = io.StringIO()
    own = logging.StreamHandler(stream)
    vastai_log = logging.getLogger("vastai")
    vastai_log.addHandler(own)
    root_handler = ui.configure_logging(io.StringIO())
    try:
        ui.remember_secret(KEY)
        logging.getLogger("vastai.serverless.client.session").warning("closing with %s", KEY)
        assert "closing with" in stream.getvalue() and KEY not in stream.getvalue()
    finally:
        vastai_log.removeHandler(own)
        logging.getLogger().removeHandler(root_handler)


async def test_a_text_reply_echoing_a_secret_is_scrubbed():
    """Proxied text replies (transcriptions, response_format=text) rely on the guard's text branch."""
    async def handler(request):
        ui.remember_secret(KEY)
        return web.Response(text=f"heard {KEY}", content_type="text/plain")
    request = make_mocked_request("POST", "/v1/audio/translations",
                                  headers={"Host": "127.0.0.1:8765"}, app=ui.make_app())
    resp = await ui.guard(request, handler)
    assert KEY not in resp.text and ui.REDACTED in resp.text


def test_bind_names_for_every_address_holds_the_machines_names_not_the_wildcard(monkeypatch):
    monkeypatch.setattr(socket, "gethostname", lambda: "Box")
    monkeypatch.setattr(socket, "getfqdn", lambda: "box.lan")
    monkeypatch.setattr(socket, "getaddrinfo", lambda name, port: [(0, 0, 0, "", ("192.168.1.5", 0))])
    names = ui.bind_names("0.0.0.0")
    assert {"box", "box.lan", "192.168.1.5"} <= names
    assert "0.0.0.0" not in names and "" not in names
    assert "10.0.0.7" in ui.bind_names("10.0.0.7")


def test_the_pages_requests_carry_its_sites_cookies():
    """A sign-in proxy in front knows its users by a cookie: requests that omit credentials never
    get past it. This server ignores cookies; the key travels in a header."""
    page = (PROJECT / "index.html").read_text(encoding="utf-8")
    assert 'credentials: "omit"' not in page and 'credentials: "same-origin"' in page


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_the_pages_script_parses(tmp_path):
    """Nothing else in CI runs the page: a syntax error in its one script would leave it dead."""
    script = tmp_path / "page.js"
    script.write_bytes(ui.PAGE_SCRIPT)
    out = subprocess.run(["node", "--check", str(script)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr


def test_worker_errors_lose_keys_never_seen_and_secrets_are_scrubbed_before_cutting():
    """A worker can echo a key this server never recorded: its shape still gives it away. And
    text is scrubbed before it is cut, so a secret spanning the cut leaves no prefix behind."""
    shaped = ui.worker_error({"status": 400, "text": "bad request: api_key=unrecorded123"}, {})
    assert "unrecorded123" not in shaped.text and ui.REDACTED in shaped.text
    ui.remember_secret(KEY)
    long = ui.worker_error({"status": 400, "text": "x" * 1990 + KEY}, {})  # KEY straddles the cut
    assert KEY[:8] not in long.text
