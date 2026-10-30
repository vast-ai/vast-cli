"""Vast serverless UI: a local web page for testing endpoints that run pyworker (its
OpenAI-compatible worker, and ComfyUI), and an OpenAI-compatible proxy to them at /v1.
Started by `vastai run serverless-ui` (vastai/cli/commands/serverless_ui.py), which calls serve().

    client = OpenAI(base_url="http://127.0.0.1:8765/v1", api_key=os.environ["SERVERLESS_UI_TOKEN"])
    client.chat.completions.create(model="Qwen/Qwen3-8B", ...)   # model picks the endpoint

    client = OpenAI(base_url="http://127.0.0.1:8765/e/my-endpoint/v1", api_key=<the token>)
    # the path picks the endpoint (name or id); model is passed on, and filled in if missing

KEY HANDLING. The server's key is the CLI's (--api-key, VAST_API_KEY, or the saved key); it is
held in memory only.
The page may send its own key as `Authorization: Bearer <key>`, which wins over the
server's. The proxy uses the server's key, and a client's bearer token only when the server
has none (with a server key, the bearer is the access token). Either way each request builds
its own SDK client and closes it; nothing writes a key anywhere.

Anything that can reach the server can spend the server's key. So it binds to localhost by
default, refuses Host headers it was not told to answer to (DNS rebinding: a website whose
name now points here), and refuses requests whose Origin is not its own page (another
site's script posting here). Bound beyond localhost, it answers to the machine's own names
and addresses, plus any --allowed-host. Holding a key, or reachable by others, it has an
access token (--access-token, SERVERLESS_UI_TOKEN, or one made for the run; see serve()):
every request but the page's own load carries it, as X-Serverless-UI-Token or, on a proxy
with a server key, as the client's API key.

The SDK puts the key in query strings and request bodies, so upstream errors can echo it.
Every secret seen during a request (the user's key, any endpoint key) is recorded for that
request's context, and removed from every log line and response before it leaves the
process. Logs and error messages are also scrubbed of anything that looks like
`api_key=...` or `Bearer ...`; replies are not, so a model's code comes back as written.
"""
import asyncio
import base64
import collections
import contextlib
import contextvars
import copy
import errno
import hashlib
import json
import logging
import math
import os
import random
import re
import secrets
import ssl
import sys
import socket
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import aiohttp
from aiohttp import web
from vastai import Serverless
from vastai.api.client import server_url_default
from vastai.serverless.client.connection import _make_request
from vastai.serverless.client.endpoint import Endpoint

from vastai.serverless.ui import discovery

HERE = Path(__file__).parent
VAST_WEB_URL = server_url_default  # VAST_URL, else console.vast.ai, as for every vastai command
MAX_BODY = 96 * 1024 * 1024  # pyworker takes 64 MB of uploads a request, sent as base64
WEB_URL = web.AppKey("vast_web_url", str)
AUTOSCALER_URL = web.AppKey("autoscaler_url", str)
SERVER_KEY = web.AppKey("server_key", str)
ALLOWED_HOSTS = web.AppKey("allowed_hosts", frozenset)
MODELS = web.AppKey("models", dict)
PREFER = web.AppKey("prefer", tuple)
TRAFFIC = web.AppKey("traffic", object)
SHARE_TRAFFIC = web.AppKey("share_traffic", bool)
ACCESS_TOKEN = web.AppKey("access_token", str)
TIMEOUT = web.AppKey("request_timeout", float)
HANDLING = web.AppKey("handling", set)  # the tasks of requests being handled, ended on shutdown
TOKEN_HEADER = "X-Serverless-UI-Token"
OPEN_PATHS = frozenset({"/", "/api/server"})  # the page, and how it learns it needs the token
MIN_TOKEN = 16
LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
STREAMED = web.RequestKey("streamed", tuple)  # (response, fail) once a stream's headers are sent
MODELS_TTL = 60.0  # seconds a model -> endpoint map is reused
MODELS_FRESH = 5.0  # a forced refresh still reuses a map this new: /v1/models is polled
REDACTED = "[redacted]"
REQUEST_TIMEOUT = 600.0  # default seconds for a worker to start answering, waiting included
MAX_BURST = 64
STREAMABLE = {discovery.COMPLETIONS, discovery.CHAT}
CHAT_BATCH = "/v1/chat/completions/batch"
DEFAULT_COST = 100  # the SDK's default; the worker computes the real workload itself
DEFAULT_AUTOSCALER = "https://run.vast.ai"

# Worker watching. The autoscaler pushes each subscribed topic's full worker list about once
# a second over a websocket, so nothing here polls while the socket is up. Its REST worker
# paths allow one request per 0.5s per user, shared with the user's other tabs and the Vast
# console, so REST is used only while the socket is down: once per reconnect wait.
MAX_WATCHES = 200         # concurrent worker sockets this server will hold
MAX_WATCHES_PER_KEY = 10  # ... for one key, so one user can't take them all
STALE_AFTER = 20.0        # seconds without a push before reconnecting
RECONNECT_MAX = 30.0      # backoff cap, as the Vast console uses
_watches: collections.Counter = collections.Counter()  # key hash -> live views
WORKER_FIELDS = (
    "id", "status", "gpu_name", "num_gpus", "reqs_working", "cur_load", "new_load",
    "cur_load_rolling_avg", "cur_perf", "perf", "measured_perf", "dlperf", "reliability",
    "disk_usage", "started_at", "loaded_at", "ready_ever", "outdated", "available",
    "replaces_worker_id")
HOSTS_EVERY = 15.0  # seconds between instance lookups for one worker view
MAX_INSTANCE_PAGES = 20
# Load runs: open-loop arrivals following a rate profile. Every request costs money, so
# everything is capped, and requests beyond the in-flight cap are skipped and counted.
MAX_LOAD_RPS = 20.0
MAX_LOAD_SECONDS = 1800.0
MAX_LOAD_SEGMENTS = 20
MAX_LOAD_INFLIGHT = 256
MAX_LOADS = 20            # concurrent load runs on this server
MAX_LOADS_PER_KEY = 2     # ... for one key: each user spends their own credit
LOAD_STEP = 0.05          # scheduler resolution, seconds
_loads: collections.Counter = collections.Counter()  # key hash -> running load runs
# The settings the workers view shows, as the endpoint and its workergroups name them.
ENDPOINT_SCALING = ("cold_workers", "max_workers", "min_load", "min_cold_load", "target_util",
                    "cold_mult", "max_queue_time", "target_queue_time", "inactivity_timeout")
GROUP_SCALING = ("min_load", "target_util", "cold_mult", "cold_workers", "gpu_ram")

# Not under "vastai": that logger has its own handler and does not propagate to the root,
# where this server's scrubbing handler is.
log = logging.getLogger("serverless_ui")

# The page, read once: the CSP allows its one script by hash, so no other script runs, even
# if text from a worker or a template ended up in the page as markup.
PAGE = (HERE / "index.html").read_bytes()
PAGE_SCRIPT = re.search(rb"<script>(.*?)</script>", PAGE, re.S).group(1)
SCRIPT_HASH = base64.b64encode(hashlib.sha256(PAGE_SCRIPT).digest()).decode()

# Page JS may only fetch from this server. That limits what script could do with the key,
# and the page never builds HTML from strings, so none should run but its own.
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        f"default-src 'none'; script-src 'sha256-{SCRIPT_HASH}'; style-src 'unsafe-inline'; "
        "img-src 'self' data: blob:; media-src 'self' data: blob:; connect-src 'self'; "
        "form-action 'none'; frame-ancestors 'none'; base-uri 'none'"),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


# ---- Secrets: recorded per request, scrubbed from everything that leaves ----
_secrets: contextvars.ContextVar[tuple] = contextvars.ContextVar("secrets", default=())
_PATTERNS = [
    (re.compile(r"(api_key[\"']?\s*[=:]\s*[\"']?)[^\s&\"',}]+", re.I), r"\1" + REDACTED),
    (re.compile(r"(Bearer\s+)[^\s\"',}]+", re.I), r"\1" + REDACTED),
]


def remember_secret(value) -> None:
    """Scrub `value` from this request's logs and responses. Short values are ignored:
    replacing them would mangle ordinary text, and no Vast key is that short."""
    if isinstance(value, str) and len(value) >= 8 and value not in _secrets.get():
        _secrets.set(_secrets.get() + (value,))


def scrub_exact(text: str) -> str:
    for secret in _secrets.get():
        text = text.replace(secret, REDACTED)
    return text


def scrub(text: str, limit: int | None = None) -> str:
    """For logs and error messages: recorded secrets, and anything shaped like a key. A limit
    cuts the result after scrubbing, never before, so no part of a secret is left at the cut."""
    text = scrub_exact(text)
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text if limit is None or len(text) <= limit else text[:limit] + "…"


def scrub_json(value):
    """Recorded secrets out of every string in a JSON value, keys included. It works on
    decoded strings, so an escape is never cut in half, and leaves out the shape patterns,
    so a reply that writes `api_key="..."` in code comes back as the model wrote it."""
    if not _secrets.get():
        return value
    if isinstance(value, str):
        return scrub_exact(value)
    if isinstance(value, dict):
        return {scrub_json(k): scrub_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub_json(v) for v in value]
    return value


def failure(e: Exception) -> str:
    return scrub(f"{type(e).__name__}: {e}")


class ScrubFilter(logging.Filter):
    """Renders each record, traceback included, and scrubs it before any handler sees it."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if record.exc_info:
            message += "\n" + logging.Formatter().formatException(record.exc_info)
            record.exc_info = record.exc_text = None
        record.msg, record.args = scrub(message), None
        return True


def configure_logging(stream=sys.stderr) -> logging.Handler:
    """The only log handler. Never pass debug=True to the SDK: its debug handler skips this one."""
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(ScrubFilter())
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    # The SDK also logs under "vastai", whose own handler skips the root's: scrub there too.
    for other in logging.getLogger("vastai").handlers:
        other.addFilter(ScrubFilter())
    return handler


# ---- Vast SDK: one client per request ----
def vast_rejected(e: Exception) -> bool:
    """Vast answers a bad key with HTTP 404 auth_error; the SDK puts that in its message."""
    return "auth_error" in str(e)


class MissingKey(Exception):
    pass


def bearer(request: web.Request) -> str:
    scheme, _, key = request.headers.get("Authorization", "").partition(" ")
    key = key.strip()
    if scheme.lower() != "bearer" or not key or len(key) > 512 or not key.isprintable():
        return ""
    return key


def is_proxy(request: web.Request) -> bool:
    return request.path.startswith(("/v1/", "/e/"))


def api_key(request: web.Request) -> str:
    """The page's key wins over the server's; the proxy's order is the other way round."""
    server = request.app[SERVER_KEY]
    remember_secret(server)
    key = (server or bearer(request)) if is_proxy(request) else (bearer(request) or server)
    if not key:
        raise MissingKey()
    remember_secret(key)
    return key


_ssl_context: ssl.SSLContext | None = None


async def vast_ssl_context() -> ssl.SSLContext:
    """Vast's root CA, downloaded once per process; it holds nothing user-specific."""
    global _ssl_context
    if _ssl_context is None:
        _ssl_context = await Serverless(api_key="unused").get_ssl_context()
    return _ssl_context


@contextlib.asynccontextmanager
async def vast(request: web.Request):
    """An SDK client for this request's key, closed when the request is done. Each client
    has its own HTTP session, so no cookies or connections carry over between users."""
    client = Serverless(api_key=api_key(request), webserver_url=request.app[WEB_URL],
                        autoscaler_url=request.app[AUTOSCALER_URL])
    client._ssl_context = await vast_ssl_context()  # private attribute, in this same package
    async with client:
        yield client


# ---- Handlers ----
async def index(request):
    return web.Response(body=PAGE, content_type="text/html", charset="utf-8")


async def server_info(request):
    """Lets the page connect without asking for a key when the server has one, and ask for
    the access token when there is one."""
    return web.json_response({"has_key": bool(request.app[SERVER_KEY]),
                              "needs_token": bool(request.app[ACCESS_TOKEN])})


class BadRequest(Exception):
    pass


async def vast_get(client: Serverless, route: str, **params) -> dict:
    """GET a Vast console API route with this request's key. The SDK has no public call for
    workergroups or templates, so this uses its request function (private, in this same package)."""
    result = await _make_request(client=client, url=client.vast_web_url, route=route,
                                 api_key=client.api_key, params=params)
    if not result.get("ok"):
        raise RuntimeError(scrub(f"{route}: HTTP {result.get('status')} - {result.get('text', '')}", limit=600))
    return result.get("json") or {}


async def workergroups(client: Serverless, endpoint_id: int | None = None) -> list:
    """The account's workergroups, or one endpoint's. Each row echoes the account key, which
    is recorded here so it is scrubbed: list them only through this."""
    listed = (await vast_get(client, "/api/v0/workergroups/")).get("results", [])
    for g in listed:
        remember_secret(g.get("api_key"))
    return [g for g in listed if endpoint_id is None or g.get("endpoint_id") == endpoint_id]


def template_ref(group: dict) -> tuple | None:
    """How a workergroup names its template: ("hash_id", hash) or ("id", id), else None."""
    if group.get("template_hash"):
        return ("hash_id", group["template_hash"])
    if group.get("template_id") is not None:
        return ("id", group["template_id"])
    return None


async def template_for(client: Serverless, ref: tuple) -> dict | None:
    """A template by hash or id; None if the lookup finds nothing (e.g. another user's
    private template)."""
    field, value = ref
    found = await vast_get(client, "/api/v0/template/", select_filters=json.dumps({field: {"eq": value}}),
                           select_cols=json.dumps(["*"]))
    return (found.get("templates") or [None])[0]


async def templates_for(client: Serverless, groups: list) -> list:
    """(template, lookup error) for each group. Each distinct template is looked up once, and
    a failed lookup marks only its own groups, so one bad answer doesn't fail them all."""
    refs = list(dict.fromkeys(r for g in groups if (r := template_ref(g)) is not None))
    found = dict(zip(refs, await asyncio.gather(*(template_for(client, r) for r in refs),
                                                return_exceptions=True)))
    out = []
    for g in groups:
        result = found.get(template_ref(g))
        if isinstance(result, asyncio.CancelledError):
            raise result
        if isinstance(result, Exception):
            log.info("template lookup %s failed: %s", template_ref(g), failure(result))
            out.append((None, failure(result)))
        else:
            out.append((result, None))
    return out


def describe_group(group: dict, template: dict | None, lookup_error: str | None = None) -> dict:
    """Records the template's secrets too. Called by the request itself, not inside a gather:
    a task's copy of the context would forget them."""
    template_env = {**discovery.parse_docker_env((template or {}).get("env")),
                    **discovery.onstart_env((template or {}).get("onstart"))}
    group_env = discovery.launch_args_env(group.get("launch_args"))
    remember_secret((template or {}).get("docker_login_pass"))
    for value in discovery.secret_values({**template_env, **group_env}):
        remember_secret(value)
    looked_up = template_ref(group) is not None
    return {
        "id": group.get("id"),
        "template": template and {k: template.get(k) for k in ("id", "hash_id", "name", "image", "tag")},
        "template_missing": looked_up and not template and not lookup_error,
        "template_error": lookup_error,
        "has_launch_args": bool(group.get("launch_args")),
        # The template's image: the autoscaler ignores --image in launch_args.
        "detected": discovery.detect(discovery.merge_env(template_env, group_env),
                                     (template or {}).get("image")),
    }


async def endpoints(request):
    """The account's endpoints. Doubles as the key check: a bad key fails here."""
    async with vast(request) as client:
        found = await client.get_endpoints()
    for e in found:
        remember_secret(e.api_key)
    # Per-endpoint keys stay here; the page only gets what it shows.
    return web.json_response({"endpoints": [
        {"name": e.name, "id": e.id, "state": e.data.config.endpoint_state} for e in found]})


async def endpoint(request):
    """What one endpoint serves: backend, model and routes, read from each workergroup's
    template env plus any env in its launch_args. Only derived fields reach the page."""
    try:
        endpoint_id = int((await request.json())["id"])
    except (ValueError, TypeError, KeyError):
        raise BadRequest("Send {\"id\": <endpoint id>}.")
    async with vast(request) as client:
        data = await client.fetch_endpoint(endpoint_id)
        remember_secret(data.api_key)
        groups = await workergroups(client, endpoint_id)
        templates = await templates_for(client, groups)
    described = [describe_group(g, *t) for g, t in zip(groups, templates)]
    return web.json_response({
        "endpoint": {"id": data.id, "name": data.config.endpoint_name,
                     "state": data.config.endpoint_state},
        "workergroups": described,
        "summary": discovery.summarise(described),
    })


# ---- Calling an endpoint ----
class TimedOut(Exception):
    """No worker started answering within the request timeout."""


async def ask(endpoint: Endpoint, route: str, body: dict, cost: float, limit: float, stream: bool = False) -> dict:
    """One request through the SDK, within this server's request timeout: waiting for a worker
    (cold start, all busy) and the worker's answer starting, together. The SDK's own limit is
    for the wait only, and gives the worker call another ten minutes; this one is the whole of
    it. A stream, once started, runs to its end."""
    try:
        return await asyncio.wait_for(
            endpoint.request(route, body, cost=cost, stream=stream, timeout=limit), limit)
    except asyncio.TimeoutError:
        raise TimedOut(f"No worker answered within {limit:g}s (--request-timeout). The endpoint may be "
                       "starting a worker, or all of them busy.") from None


@dataclass
class Call:
    endpoint_id: int
    route: str
    body: dict

    @property
    def stream(self) -> bool:
        """Streams when the body asks for it, as the OpenAI API does."""
        return self.route in STREAMABLE and self.body.get("stream") is True

    @property
    def cost(self) -> float:
        """max_tokens, as pyworker counts the workload; a chat batch spends it per conversation."""
        tokens = self.body.get("max_tokens")
        if not (isinstance(tokens, (int, float)) and tokens > 0):
            return DEFAULT_COST
        conversations = self.body.get("messages")
        if self.route == CHAT_BATCH and isinstance(conversations, list) and conversations:
            return tokens * len(conversations)
        return tokens


async def read_call(request: web.Request) -> Call:
    """{"endpoint": <id>, "route": "/v1/...", "body": {...}}. Any known route is allowed,
    served or not, so a missing route can be tested too."""
    try:
        data = await request.json()
        call = Call(int(data["endpoint"]), data["route"], data["body"])
    except (ValueError, TypeError, KeyError):
        raise BadRequest('Send {"endpoint": <id>, "route": "/v1/...", "body": {...}}.')
    if call.route not in discovery.ALL_ROUTES:
        raise BadRequest(f"Unknown route {call.route!r}.")
    if not isinstance(call.body, dict):
        raise BadRequest("body must be a JSON object.")
    return call


async def open_endpoint(client: Serverless, endpoint_id: int) -> Endpoint:
    """Looked up by id on every call: endpoint keys are secrets, so none are kept between
    requests. Recorded before any request, so the SDK's background tasks, which copy this
    context when they start, scrub it too."""
    data = await client.fetch_endpoint(endpoint_id)
    remember_secret(data.api_key)
    return Endpoint(client=client, data=data)


def envelope(call: Call, result: dict, started: float) -> dict:
    """The page's view of one result. Only these fields leave: the SDK result also carries
    the worker's signed auth_data."""
    out = {
        "ok": bool(result.get("ok")), "status": result.get("status"), "route": call.route,
        "worker": result.get("url"), "seconds": round(time.perf_counter() - started, 3),
        "worker_seconds": result.get("latency") and round(result["latency"], 3),
        "content_type": result.get("content_type") or "",
    }
    response = result.get("response")
    if isinstance(response, (bytes, bytearray)):  # audio, video or an image, as sent
        out["media"] = {"type": out["content_type"] or "application/octet-stream",
                        "b64": base64.b64encode(response).decode()}
    elif response is None and result.get("text"):  # e.g. a transcription asked for as text
        out["response"] = result["text"]
    else:
        out["response"] = response
    if not out["ok"]:
        out["error"] = scrub(f"HTTP {out['status']}: {result.get('text') or ''}", limit=2000)
    return out


async def ndjson(request: web.Request) -> tuple:
    """A prepared NDJSON stream and a send(obj) that scrubs each line before it goes."""
    resp = web.StreamResponse(headers={
        "Content-Type": "application/x-ndjson", "Cache-Control": "no-store", **SECURITY_HEADERS})
    await resp.prepare(request)

    async def send(obj):
        await resp.write((json.dumps(scrub_json(obj)) + "\n").encode())

    async def fail(message: str):
        await send({"type": "error", "error": message})
    request[STREAMED] = (resp, fail)
    return resp, send


async def end_stream(request: web.Request, message: str):
    """A failure after a stream's headers have gone can't become a response of its own; it
    is written into the stream instead. None if no stream has started."""
    if (started := request.get(STREAMED)) is None:
        return None
    resp, fail = started
    with contextlib.suppress(Exception):  # the page may be gone too
        await fail(message)
    return resp


async def call(request):
    """One request through the SDK. A worker's HTTP error is a result (ok: false), not a
    failure of this call. A streamed body is relayed chunk by chunk as NDJSON."""
    c = await read_call(request)
    async with vast(request) as client:
        endpoint = await open_endpoint(client, c.endpoint_id)
        started = time.perf_counter()
        result = await ask(endpoint, c.route, c.body, c.cost, request.app[TIMEOUT], c.stream)
        if not (c.stream and result.get("ok")):
            return web.json_response(envelope(c, result, started))
        return await relay(request, c, result, started)


async def relay(request, c: Call, result: dict, started: float):
    """start, then a chunk line per SSE event, then done with timings."""
    resp, send = await ndjson(request)
    send = page_writer(send)
    head = envelope(c, {**result, "response": None}, started)
    first = usage = None
    chunks = 0
    try:
        await send({"type": "start", **{k: head[k] for k in ("status", "route", "worker")}})
        try:
            async for chunk in result["response"]:
                first = first or time.perf_counter()
                chunks += 1
                usage = (chunk.get("usage") if isinstance(chunk, dict) else None) or usage
                await send({"type": "chunk", "data": chunk})
        except PageGone:
            raise
        except Exception as e:  # the worker's stream, not the page
            log.warning("stream from %s broke: %s: %s", c.route, type(e).__name__, e)
            await send({"type": "error", "error": failure(e)})
        end = time.perf_counter()
        done = {"type": "done", "seconds": round(end - started, 3), "chunks": chunks,
                "ttft": first and round(first - started, 3), "usage": usage}
        tokens = (usage or {}).get("completion_tokens")
        if tokens and first and end > first:
            done["tokens_per_second"] = round(tokens / (end - first), 1)
        await send(done)
        await resp.write_eof()
    except PageGone:
        pass  # the page went away: nothing left to tell it
    return resp


async def burst(request):
    """n copies of one request at once, each result streamed back as it lands. The fan-out
    is here because browsers allow only ~6 connections per host."""
    c = await read_call(request)
    try:
        n = int(request.query.get("n", "8"))
    except ValueError:
        raise BadRequest("n must be a whole number.")
    if not 1 <= n <= MAX_BURST:
        raise BadRequest(f"n must be 1 to {MAX_BURST}.")
    if c.stream:
        raise BadRequest("A burst does not stream; turn streaming off.")
    async with vast(request) as client:
        endpoint = await open_endpoint(client, c.endpoint_id)
        resp, send = await ndjson(request)
        send = page_writer(send)

        async def one(i):
            started = time.perf_counter()
            try:
                result = await ask(endpoint, c.route, dict(c.body), c.cost, request.app[TIMEOUT])
                return {"index": i, **envelope(c, result, started)}
            except Exception as e:
                return {"index": i, "ok": False, "seconds": round(time.perf_counter() - started, 3),
                        "error": failure(e)}

        tasks = [asyncio.create_task(one(i)) for i in range(n)]
        try:
            for done in asyncio.as_completed(tasks):
                await send(await done)
            await resp.write_eof()
        except PageGone:
            pass
        finally:  # every request costs money: none outlives the page (see serve's handler_cancellation)
            for task in tasks:
                task.cancel()
    return resp


# ---- Watching workers ----
class PageGone(Exception):
    """The page closed its stream. Kept apart from aiohttp.ClientError, which a write to a
    closed page also raises, so it is never mistaken for the Vast socket failing."""


def page_writer(send):
    async def to_page(obj):
        try:
            await send(obj)
        except (ConnectionResetError, aiohttp.ClientConnectionResetError) as e:
            raise PageGone() from e
    return to_page


def workers_view(workers) -> list:
    return [{k: w.get(k) for k in WORKER_FIELDS if k in w}
            for w in (workers if isinstance(workers, list) else []) if isinstance(w, dict)]


def take_slot(held: collections.Counter, who: str, total: int, per_key: int, what: str,
              state: str) -> str | None:
    """Takes one of `held`'s slots for `who`, or says why not. Called before the first await,
    so requests arriving together can't all pass."""
    if sum(held.values()) >= total:
        return f"Too many {what} {state} on this server; try again later."
    if held[who] >= per_key:
        return f"You already have {per_key} {what} {state}; stop one first."
    held[who] += 1
    return None


def give_slot(held: collections.Counter, who: str):
    held[who] -= 1
    if held[who] <= 0:
        del held[who]


async def watch(request):
    """Live workers for one endpoint, as NDJSON: config once, then status changes and a
    workers line per push (the endpoint's, and each workergroup's). Runs until the page
    disconnects."""
    try:
        endpoint_id = int((await request.json())["endpoint"])
    except (ValueError, TypeError, KeyError):
        raise BadRequest('Send {"endpoint": <id>}.')
    key = api_key(request)
    who = key_hash(key)
    if refused := take_slot(_watches, who, MAX_WATCHES, MAX_WATCHES_PER_KEY, "worker views", "open"):
        return web.json_response({"error": refused}, status=503)
    try:
        async with vast(request) as client:
            data = await client.fetch_endpoint(endpoint_id)
            remember_secret(data.api_key)
            groups = await workergroups(client, endpoint_id)
            autoscaler = client.autoscaler_url
        resp, send = await ndjson(request)
        send = page_writer(send)
        await send({"type": "config",
                    "endpoint": {k: getattr(data.config, k, None) for k in ENDPOINT_SCALING},
                    "workergroups": [{"id": g["id"], **{k: g.get(k) for k in GROUP_SCALING}}
                                     for g in groups]})
        topics = [("endpoint", endpoint_id)] + [("autogroup", g["id"]) for g in groups]
        await follow(send, key, autoscaler, topics, endpoint_id, lambda ids: worker_hosts(request, ids))
    except PageGone:
        pass
    finally:
        give_slot(_watches, who)
    return resp


async def worker_hosts(request, ids: set) -> dict:
    """{"ip:port": worker id} for these workers. A worker is an instance (pyworker reports
    CONTAINER_ID as its id), and a reply names only the worker's URL, so the instance's public
    address and mapped ports tie the two together. Nothing else of the instance leaves here."""
    listed, params = [], {"select_filters": json.dumps({"id": {"in": sorted(ids)}}),
                          "order_by": json.dumps([{"col": "id", "dir": "asc"}]), "limit": 25}
    async with vast(request) as client:
        for _ in range(MAX_INSTANCE_PAGES):  # v1 pages its results, as the CLI reads them
            page = await vast_get(client, "/api/v1/instances/", **params)
            listed += page.get("instances") or []
            if not page.get("next_token"):
                break
            params["after_token"] = page["next_token"]
    hosts = {}
    for inst in listed if isinstance(listed, list) else []:
        if not isinstance(inst, dict) or inst.get("id") not in ids:
            continue
        ip = str(inst.get("public_ipaddr") or "").strip()
        for maps in (inst.get("ports") or {}).values():
            for m in maps if isinstance(maps, list) else []:
                if ip and isinstance(m, dict) and m.get("HostPort"):
                    hosts[f"{ip}:{m['HostPort']}"] = inst["id"]
    return hosts


def _topic(push: dict) -> str:
    return "endpoint" if push.get("type") == "endpoint_workers" else "workergroup"


async def follow(send, key: str, autoscaler: str, topics: list, endpoint_id: int, lookup=None):
    """Holds the autoscaler's worker socket, reconnecting with backoff. While it is down,
    one REST read per wait keeps the page current without crowding the rate limit.
    When workers appear that have no address yet, `lookup` finds them, at most once per
    HOSTS_EVERY, so the page can say which worker served each reply."""
    placed: set = set()
    looked = -HOSTS_EVERY

    async def place(workers: list):
        nonlocal looked
        ids = {w.get("id") for w in workers if isinstance(w, dict)} - placed - {None}
        if not ids or lookup is None or time.monotonic() - looked < HOSTS_EVERY:
            return
        looked = time.monotonic()
        try:
            hosts = await lookup(ids)
        except Exception as e:  # the view works without names; say why they are missing
            await send({"type": "warning", "detail": f"Could not look up worker addresses: {scrub(str(e))}"})
            return
        placed.update(hosts.values())
        know_workers(hosts)
        # Stopped and starting workers have no address, which is normal: they are simply
        # looked up again, at most once per HOSTS_EVERY, while they appear without one.
        if hosts:
            await send({"type": "hosts", "hosts": hosts})

    base = (autoscaler or DEFAULT_AUTOSCALER).rstrip("/")
    ws_url = re.sub(r"^http", "ws", base) + "/ws/workers/"
    connector = aiohttp.TCPConnector(ssl=await vast_ssl_context())
    async with aiohttp.ClientSession(connector=connector) as session:
        attempt = 0
        while True:
            await send({"type": "status", "state": "connecting"})
            try:
                # The socket takes the key as a query parameter; it is scrubbed from errors.
                async with session.ws_connect(ws_url, params={"api_key": key}, heartbeat=30,
                                              timeout=aiohttp.ClientWSTimeout(ws_close=5)) as ws:
                    for kind, id_ in topics:
                        await ws.send_json({"action": "subscribe", "type": kind, "id": id_})
                    live = False
                    while True:
                        msg = await ws.receive(timeout=STALE_AFTER)
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            reason = f"socket closed ({ws.close_code})"
                            break
                        push = json.loads(msg.data)
                        if not isinstance(push, dict):
                            continue
                        if "workers" in push:
                            if not live:
                                live, attempt = True, 0
                                await send({"type": "status", "state": "live"})
                            await send({"type": "workers", "topic": _topic(push), "id": push.get("id"),
                                        "timestamp": push.get("timestamp"),
                                        "active_update": push.get("active_update"),
                                        "workers": workers_view(push["workers"])})
                            await place(push["workers"])
                        elif "error" in push:
                            await send({"type": "warning", "detail": str(push["error"])})
            except asyncio.TimeoutError:
                reason = f"no update for {STALE_AFTER:.0f}s"
            except (aiohttp.ClientError, ValueError) as e:
                reason = failure(e)
            attempt += 1
            delay = min(RECONNECT_MAX, 2 ** attempt) + random.random()
            await send({"type": "status", "state": "reconnecting", "detail": reason,
                        "retry_in": round(delay, 1)})
            await poll_workers(session, send, base, key, endpoint_id)
            await asyncio.sleep(delay)


async def poll_workers(session, send, base: str, key: str, endpoint_id: int):
    """One REST read of the endpoint's workers, for while the socket is down."""
    try:
        async with session.post(f"{base}/get_endpoint_workers/",
                                json={"id": endpoint_id, "api_key": key},
                                headers={"Authorization": f"Bearer {key}"},
                                timeout=aiohttp.ClientTimeout(total=10)) as r:
            body = await r.json(content_type=None) if r.status == 200 else None
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        return
    if isinstance(body, list):
        await send({"type": "workers", "topic": "endpoint", "id": endpoint_id, "polled": True,
                    "timestamp": time.time(), "workers": workers_view(body)})


# ---- Load runs ----
def read_profile(raw) -> list:
    """[{"from": rps, "to": rps, "seconds": s}, ...]: linear ramps, run in order."""
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_LOAD_SEGMENTS:
        raise BadRequest(f"profile must be a list of 1 to {MAX_LOAD_SEGMENTS} segments.")
    profile = []
    for seg in raw:
        try:
            a, b, secs = float(seg["from"]), float(seg["to"]), float(seg["seconds"])
        except (TypeError, KeyError, ValueError):
            raise BadRequest('Each segment is {"from": rps, "to": rps, "seconds": s}.')
        if not (0 <= a <= MAX_LOAD_RPS and 0 <= b <= MAX_LOAD_RPS):
            raise BadRequest(f"Rates must be 0 to {MAX_LOAD_RPS:g} requests/s.")
        if not 0 < secs <= MAX_LOAD_SECONDS:
            raise BadRequest("Each segment needs a positive duration.")
        profile.append((a, b, secs))
    if sum(p[2] for p in profile) > MAX_LOAD_SECONDS:
        raise BadRequest(f"A run is at most {MAX_LOAD_SECONDS / 60:g} minutes.")
    return profile


def rate_at(profile: list, t: float):
    """The target rate t seconds in, or None once the profile is over."""
    for a, b, secs in profile:
        if t < secs:
            return a + (b - a) * t / secs
        t -= secs
    return None


def expected_requests(profile: list) -> float:
    return sum((a + b) / 2 * secs for a, b, secs in profile)


def expected_by(profile: list, t: float) -> float:
    """The requests the profile asks for in its first t seconds: the area under its rate."""
    total = 0.0
    for a, b, secs in profile:
        span = min(t, secs)
        if span <= 0:
            break
        total += (a + (a + (b - a) * span / secs)) / 2 * span
        t -= secs
    return total


def poisson(mean: float) -> int:
    """Knuth's method; the means here are small (rate × LOAD_STEP)."""
    limit, k, p = math.exp(-mean), 0, 1.0
    while True:
        p *= random.random()
        if p <= limit:
            return k
        k += 1


def tag_body(body: dict, tag: str) -> dict:
    """A copy whose prompt starts with tag, so no two requests share a cached prefix. Only
    the first text field found is changed: prompt, the first message, or input."""
    body = copy.deepcopy(body)
    if isinstance(body.get("prompt"), str):
        body["prompt"] = tag + body["prompt"]
    elif isinstance(body.get("messages"), list) and body["messages"]:
        first = body["messages"][0]
        if isinstance(first, dict) and isinstance(first.get("content"), str):
            first["content"] = tag + first["content"]
        elif (isinstance(first, list) and first and isinstance(first[0], dict)
              and isinstance(first[0].get("content"), str)):
            first[0]["content"] = tag + first[0]["content"]  # chat batch: a list of conversations
    elif isinstance(body.get("input"), str):
        body["input"] = tag + body["input"]
    elif isinstance(body.get("input"), list) and body["input"] and isinstance(body["input"][0], str):
        body["input"][0] = tag + body["input"][0]
    return body


async def load(request):
    """Requests at a rate that follows a profile, sent on schedule whether or not earlier
    ones have answered, so queueing and scaling show. NDJSON: start, then a tick a second
    (target rate, in flight, the results that landed), then done. Responses are not relayed,
    only their timings. Stops, cancelling what is in flight, when the page goes away."""
    c = await read_call(request)
    data = await request.json()
    profile = read_profile(data.get("profile"))
    arrivals = data.get("arrivals", "even")
    if arrivals not in ("even", "poisson"):
        raise BadRequest('arrivals is "even" or "poisson".')
    if c.stream:
        raise BadRequest("A load run does not stream; turn streaming off.")
    who = key_hash(api_key(request))
    if refused := take_slot(_loads, who, MAX_LOADS, MAX_LOADS_PER_KEY, "load runs", "running"):
        return web.json_response({"error": refused}, status=503)
    try:
        async with vast(request) as client:
            endpoint = await open_endpoint(client, c.endpoint_id)
            resp, send = await ndjson(request)
            await run_load(page_writer(send), endpoint, c, profile, arrivals == "poisson",
                           unique=data.get("unique", True) is not False, limit=request.app[TIMEOUT])
    except PageGone:
        pass
    finally:
        give_slot(_loads, who)
    return resp


async def run_load(send, endpoint: Endpoint, c: Call, profile: list, poisson_arrivals: bool,
                   unique: bool, limit: float = REQUEST_TIMEOUT):
    loop = asyncio.get_running_loop()
    run_id = secrets.token_hex(3)
    tasks: set = set()
    landed: list = []
    counts = {"sent": 0, "skipped": 0}
    started = loop.time()

    async def one(i: int, sent_at: float, body: dict):
        t0 = time.perf_counter()
        line = {"index": i, "sent_at": round(sent_at, 3)}
        try:
            result = await ask(endpoint, c.route, body, c.cost, limit)
            line.update(ok=bool(result.get("ok")), status=result.get("status"),
                        worker=result.get("url"))
            if not line["ok"]:
                line["error"] = scrub(f"HTTP {line['status']}: {result.get('text') or ''}", limit=200)
        except Exception as e:
            line.update(ok=False, error=failure(e)[:300])
        line["seconds"] = round(time.perf_counter() - t0, 3)
        line["done_at"] = round(loop.time() - started, 3)
        landed.append(line)

    async def tick(t: float, rate):
        batch = landed[:]
        landed.clear()
        await send({"type": "tick", "t": round(t, 2), "target_rps": rate and round(rate, 3),
                    "inflight": len(tasks), **counts, "results": batch})

    await send({"type": "start", "seconds": sum(p[2] for p in profile),
                "expected": round(expected_requests(profile)), "run": run_id})
    try:
        last, next_tick = started, started + 1.0
        while True:
            now = loop.time()
            t = now - started
            rate = rate_at(profile, t)  # None once the profile is over
            if poisson_arrivals:
                due = poisson(rate * (now - last)) if rate is not None else 0
            else:
                # Even: whatever the profile has asked for by now, so a timer step that runs
                # late (the last one included) loses nothing.
                owed = expected_by(profile, t)
                due = (round(owed) if rate is None else math.floor(owed + 1e-9)) - counts["sent"] - counts["skipped"]
            last = now
            for _ in range(due):
                if len(tasks) >= MAX_LOAD_INFLIGHT:
                    counts["skipped"] += 1
                    continue
                i = counts["sent"]
                body = tag_body(c.body, f"[{run_id}-{i}] ") if unique else copy.deepcopy(c.body)
                task = asyncio.create_task(one(i, t, body))
                tasks.add(task)
                task.add_done_callback(tasks.discard)
                counts["sent"] += 1
            if rate is None:
                break
            if now >= next_tick:
                await tick(t, rate)
                next_tick += 1.0
            await asyncio.sleep(LOAD_STEP)
        # The profile is over: let what is in flight finish, still reporting each second.
        while tasks:
            await asyncio.wait(set(tasks), timeout=1.0)
            await tick(loop.time() - started, None)
        await tick(loop.time() - started, None)
        await send({"type": "done", **counts})
    finally:
        for task in tasks:
            task.cancel()


# ---- Proxy traffic: what the page shows of requests through the proxy ----
TRAFFIC_KEEP = 200     # recent requests kept for pages that open later
TRAFFIC_PING = 15.0    # seconds between keepalives, which also notice a page that has gone
PREVIEW = 160          # characters of prompt and reply shown


class Traffic:
    """Each proxied request as a snapshot, published on every change (routing, worker
    known, done). Snapshots carry a hash of the key that made them; a page sees its own
    key's, and the server key's when the server shares it (on localhost, or with
    --share-traffic): beyond localhost, those are other people's prompts. The hash never
    leaves here."""

    def __init__(self):
        self.recent: collections.OrderedDict = collections.OrderedDict()
        self.listeners: set = set()
        self.seq = 0

    def start(self, who: str, **fields) -> dict:
        self.seq += 1
        row = {"type": "request", "id": self.seq, "at": time.time(), "state": "routing", **fields}
        row["_who"] = who
        self.publish(row)
        return row

    def publish(self, row: dict):
        self.recent[row["id"]] = row
        self.recent.move_to_end(row["id"])
        while len(self.recent) > TRAFFIC_KEEP:
            self.recent.popitem(last=False)
        for who, queue in list(self.listeners):
            if row["_who"] in who and not queue.full():
                queue.put_nowait(public(row))


def public(row: dict) -> dict:
    return {k: v for k, v in row.items() if not k.startswith("_")}


def text_of(content) -> str:
    """A message's text, whether a string or OpenAI's list of parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return ""


def workflow_prompt(workflow) -> str:
    """A ComfyUI workflow's prompt: the first text that feeds a sampler's positive input, else
    the first text input of any node."""
    if not isinstance(workflow, dict):
        return ""
    texts = {nid: n["inputs"].get("text") or n["inputs"].get("prompt") for nid, n in workflow.items()
             if isinstance(n, dict) and isinstance(n.get("inputs"), dict)
             and isinstance(n["inputs"].get("text") or n["inputs"].get("prompt"), str)}
    for n in workflow.values():
        positive = (n.get("inputs") or {}).get("positive") if isinstance(n, dict) else None
        if isinstance(positive, list) and positive and str(positive[0]) in texts:
            return texts[str(positive[0])]
    return next(iter(texts.values()), "")


def prompt_preview(body: dict) -> str:
    """The part a person would recognise: the last user message, the prompt or the input."""
    if isinstance(body.get("input"), dict) and "workflow_json" in body["input"]:  # ComfyUI
        return workflow_prompt(body["input"]["workflow_json"])
    messages = body.get("messages")
    if isinstance(messages, list) and messages:
        if isinstance(messages[0], list):  # chat batch: a list of conversations
            return f"{len(messages)} conversations: " + prompt_preview({"messages": messages[0]})
        users = [m for m in messages if isinstance(m, dict) and m.get("role") == "user"]
        return text_of((users or messages)[-1].get("content") if isinstance((users or messages)[-1], dict) else "")
    for field in ("prompt", "input", "text", "query"):
        value = body.get(field)
        if isinstance(value, str):
            return value
        if isinstance(value, list) and value and isinstance(value[0], str):
            return f"{len(value)} items: {value[0]}"
    return ""


def reply_preview(result: dict) -> str:
    response = result.get("response")
    if isinstance(response, (bytes, bytearray)):
        return f"{result.get('content_type') or 'binary'}, {len(response) // 1024} KB"
    if isinstance(response, dict) and isinstance(response.get("output"), list):  # ComfyUI
        kinds = [o.get("mimetype") or o.get("filename", "?") for o in response["output"] if isinstance(o, dict)]
        return f"{response.get('status', '')}: {len(kinds)} output(s) {', '.join(kinds)}".strip()
    if isinstance(response, dict):
        choice = (response.get("choices") or [None])[0]
        if isinstance(choice, dict):
            return text_of((choice.get("message") or {}).get("content")) or str(choice.get("text") or "")
        if isinstance(response.get("data"), list):
            return f"{len(response['data'])} result(s)"
    return str(result.get("text") or "")


def clip(text: str) -> str:
    return scrub(" ".join(str(text).split()), limit=PREVIEW)


def preview(make, value) -> str:
    """A clipped preview for the traffic view, or "" if the value has a shape it can't read:
    the view only watches, so it must never fail the request it describes."""
    try:
        return clip(make(value))
    except Exception:
        return ""


def worker_address(url: str) -> str:
    """ip:port from a worker's URL."""
    return re.sub(r"^https?://", "", url or "").split("/")[0]


def key_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def traffic(request):
    """NDJSON: recent proxied requests, then each change as it happens. All endpoints, or
    {"endpoint": <id>} for one."""
    try:
        endpoint_id = (await request.json()).get("endpoint")
        endpoint_id = None if endpoint_id is None else int(endpoint_id)
    except (ValueError, TypeError, AttributeError):
        raise BadRequest('Send {} or {"endpoint": <id>}.')
    server = request.app[SERVER_KEY]
    who = {key_hash(api_key(request))} | ({key_hash(server)} if server else set())
    withheld = bool(server) and not request.app[SHARE_TRAFFIC]
    if withheld:
        who.discard(key_hash(server))
    who = frozenset(who)
    log_ = request.app[TRAFFIC]
    shown = lambda r: r["_who"] in who and endpoint_id in (None, r.get("endpoint_id"))  # noqa: E731
    queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
    resp, send = await ndjson(request)
    send = page_writer(send)
    entry = (who, queue)
    log_.listeners.add(entry)
    try:
        await send({"type": "history", "requests": [public(r) for r in log_.recent.values() if shown(r)],
                    "withheld": withheld})
        while True:
            try:
                row = await asyncio.wait_for(queue.get(), TRAFFIC_PING)
            except asyncio.TimeoutError:
                await send({"type": "ping"})
                continue
            if endpoint_id in (None, row.get("endpoint_id")):
                await send(row)
    except PageGone:
        pass
    finally:
        log_.listeners.discard(entry)
    return resp


# ---- OpenAI-compatible proxy ----
def openai_error(status: int, message: str, kind: str = "proxy_error", code: str | None = None):
    return web.json_response({"error": {"message": message, "type": kind, "param": None, "code": code}},
                             status=status)


async def model_index(client: Serverless) -> list:
    """Every endpoint with the model its workergroups serve, read as discovery reads it."""
    found = await client.get_endpoints()
    for e in found:
        remember_secret(e.api_key)
    listed = await workergroups(client)
    templates = await templates_for(client, listed)
    described = [(g, describe_group(g, *t)) for g, t in zip(listed, templates)]
    index = []
    for e in found:
        summary = discovery.summarise([d for g, d in described if g.get("endpoint_id") == e.id])
        index.append({"id": e.id, "name": e.name, "state": e.data.config.endpoint_state,
                      "model": summary["model"], "family": summary["family"],
                      "backend": summary["backend"], "created": int(e.data.created_at or 0)})
    return index


async def models_for(request, client: Serverless, fresh: bool = False) -> list:
    """The model index, reused for MODELS_TTL per key, or MODELS_FRESH when fresh is asked
    for. Keyed by a hash, so the cache holds no key; it holds only names and ids."""
    cache = request.app[MODELS]
    who = key_hash(api_key(request))
    at, index = cache.get(who, (0.0, None))
    if index is None or time.monotonic() - at > (MODELS_FRESH if fresh else MODELS_TTL):
        index = await model_index(client)
        cache[who] = (time.monotonic(), index)
    return index


def named(index: list, which: str) -> dict | None:
    """The endpoint called `which`, by name or id."""
    return next((e for e in index if e["name"] == which or str(e["id"]) == which), None)


def pick_endpoint(index: list, model, prefer: tuple = ()) -> tuple:
    """(entry, None) or (None, error response). `model` is a served model or an endpoint name;
    when several endpoints serve it, the first of `prefer` among them wins."""
    by_model = [e for e in index if e["model"] and e["model"] == model]
    matches = by_model or [e for e in index if e["name"] == model]
    if len(matches) == 1:
        return matches[0], None
    for which in prefer:
        if (chosen := named(matches, which)) is not None:
            return chosen, None
    if matches:
        names = ", ".join(e["name"] for e in matches)
        return None, openai_error(400, f"{len(matches)} endpoints serve {model!r} ({names}). Call "
                                  "/e/<endpoint>/v1, set model to an endpoint name, or start the "
                                  "server with --prefer <endpoint>.", "invalid_request_error",
                                  "ambiguous_model")
    known = sorted({e["model"] for e in index if e["model"]} | {e["name"] for e in index})
    return None, openai_error(404, f"No endpoint serves model {model!r}. Known: {', '.join(known) or 'none'}.",
                              "invalid_request_error", "model_not_found")


async def proxy_models(request):
    """Every endpoint's model, or just the one endpoint's under /e/<endpoint>/v1."""
    which = request.match_info.get("endpoint")
    try:
        async with vast(request) as client:
            index = await models_for(request, client, fresh=True)
    except MissingKey:
        return no_key()
    if which is not None:
        entry = named(index, which)
        if entry is None:
            return endpoint_not_found(which, index)
        index = [entry]
    return web.json_response({"object": "list", "data": [
        # owned_by as the worker's own /v1/models says it ("vllm", "sglang", ...), and created
        # as the endpoint's: both are required by the OpenAI spec.
        {"id": e["model"], "object": "model", "created": e["created"], "owned_by": e["backend"] or "unknown",
         "endpoint": e["name"], "endpoint_state": e["state"]} for e in index if e["model"]]})


def endpoint_not_found(which: str, index: list):
    names = ", ".join(e["name"] for e in index) or "none"
    return openai_error(404, f"No endpoint named {which!r}. Endpoints: {names}.",
                        "invalid_request_error", "endpoint_not_found")


def no_key():
    return openai_error(401, "No Vast API key: start the server with VAST_API_KEY set or "
                        "--api-key, or send the key as the bearer token.", "authentication_error")


KNOWN_WORKERS: dict = {}  # "ip:port" -> worker id, from any lookup; addresses only, newest last
KNOWN_WORKERS_MAX = 1000
_learned_at: dict = {}    # endpoint id -> when its workers were last looked up
_background: set = set()


def know_workers(hosts: dict):
    """Records worker addresses, dropping the longest unseen past KNOWN_WORKERS_MAX."""
    for where, worker_id in hosts.items():
        KNOWN_WORKERS.pop(where, None)
        KNOWN_WORKERS[where] = worker_id
    while len(KNOWN_WORKERS) > KNOWN_WORKERS_MAX:
        del KNOWN_WORKERS[next(iter(KNOWN_WORKERS))]


def learn_workers(request, endpoint_id: int):
    """Looks up an endpoint's worker addresses in the background, at most once per
    HOSTS_EVERY, so the reply isn't held up; later replies carry the worker id."""
    if time.monotonic() - _learned_at.get(endpoint_id, -HOSTS_EVERY) < HOSTS_EVERY:
        return
    _learned_at[endpoint_id] = time.monotonic()

    async def run():
        try:
            async with vast(request) as client:  # its own client: the request's is closed by then
                endpoint = await open_endpoint(client, endpoint_id)
                ids = {w.id for w in await endpoint.get_workers()}
            know_workers(await worker_hosts(request, ids))
        except Exception as e:
            log.info("worker lookup for endpoint %s failed: %s: %s", endpoint_id, type(e).__name__, e)
    task = asyncio.create_task(run())
    _background.add(task)
    task.add_done_callback(_background.discard)


def worker_headers(entry: dict, result: dict) -> dict:
    """Which endpoint and worker served this, on every proxied response."""
    url = result.get("url") or ""
    where = worker_address(url)
    out = {"X-Vast-Endpoint": str(entry["name"]), "X-Vast-Worker": where}
    if where in KNOWN_WORKERS:
        out["X-Vast-Worker-Id"] = str(KNOWN_WORKERS[where])
    return out


async def proxy(request):
    """POST /v1/<route>: the body goes, unchanged, to the endpoint serving body["model"].
    POST /e/<endpoint>/v1/<route>: to that endpoint, whatever the model."""
    which = request.match_info.get("endpoint")
    route = "/v1/" + request.match_info["route"] if "route" in request.match_info else discovery.COMFY_ROUTE
    if route not in discovery.ALL_ROUTES:
        return openai_error(404, f"{route} is not a pyworker route.", "invalid_request_error",
                            "unknown_route")
    if request.content_type == "multipart/form-data":
        try:
            body = await form_body(request)
        except web.HTTPRequestEntityTooLarge:
            return openai_error(413, f"The upload is over {MAX_BODY // 2**20} MB in all.",
                                "invalid_request_error", "too_large")
        except (ValueError, aiohttp.http_exceptions.HttpProcessingError) as e:
            return openai_error(400, f"Malformed multipart upload: {failure(e)}", "invalid_request_error")
    elif request.content_type != "application/json":
        return openai_error(415, "Send JSON, or multipart/form-data for file uploads.",
                            "invalid_request_error")
    else:
        try:
            body = await request.json()
        except ValueError:
            return openai_error(400, "The body is not valid JSON.", "invalid_request_error")
    if not isinstance(body, dict):
        return openai_error(400, "The body must be a JSON object.", "invalid_request_error")
    if which is None and not body.get("model"):
        return openai_error(400, "Set model to a served model or an endpoint name, or call "
                            "/e/<endpoint>/v1.", "invalid_request_error")
    row = None
    started = time.perf_counter()
    try:
        async with vast(request) as client:
            entry, error = await choose(request, client, which, body.get("model"))
            if error is not None:
                return error
            if entry["model"] and route != discovery.COMFY_ROUTE and (
                    (which is not None and not body.get("model"))  # /e/<endpoint>: filled in if missing
                    or (which is None and body.get("model") == entry["name"] != entry["model"])):
                # vLLM and SGLang check the name: a missing one is filled in, and on /v1 an
                # endpoint's name (which picked it) becomes its model. A model is never replaced.
                body = {**body, "model": entry["model"]}
            c = Call(entry["id"], route, body)
            row = request.app[TRAFFIC].start(
                key_hash(api_key(request)), endpoint=entry["name"],
                endpoint_id=entry["id"], route=route, model=body.get("model"), stream=c.stream,
                prompt=preview(prompt_preview, body), pinned=which is not None)
            endpoint = await open_endpoint(client, entry["id"])
            result = await ask(endpoint, route, body, c.cost, request.app[TIMEOUT], c.stream)
            headers = worker_headers(entry, result)
            if headers["X-Vast-Worker"] and "X-Vast-Worker-Id" not in headers:
                learn_workers(request, entry["id"])
            seen = {"worker": result.get("url"), "status": result.get("status")}
            if not result.get("ok"):
                failed = worker_error(result, headers)
                update(request, row, started, state="failed", **seen,
                       error=clip(json.loads(failed.text)["error"].get("message") or ""))
                return failed
            if c.stream:
                update(request, row, started, state="streaming", **seen)
                return await relay_sse(request, result, headers, row, started)
            update(request, row, started, state="done", **seen, reply=preview(reply_preview, result),
                   tokens=((result.get("response") or {}).get("usage") or {}).get("completion_tokens")
                   if isinstance(result.get("response"), dict) else None)
            return reply(result, headers)
    except MissingKey:
        return no_key()
    except asyncio.CancelledError:  # the client went away: so does its request (handler_cancellation)
        if row is not None:
            update(request, row, started, state="cancelled")
        raise
    except TimedOut as e:
        if row is not None:
            update(request, row, started, state="failed", error=clip(str(e)))
        return openai_error(504, str(e), "timeout")
    except Exception as e:
        rejected = vast_rejected(e)
        if row is not None:  # every way out closes the row the traffic view shows
            update(request, row, started, state="failed",
                   error="Vast rejected this API key." if rejected else clip(failure(e)))
        if rejected:
            return openai_error(401, "Vast rejected this API key.", "authentication_error")
        log.warning("proxy %s failed: %s: %s", route, type(e).__name__, e)
        streamed = await end_stream(request, failure(e))
        return streamed if streamed is not None else openai_error(502, failure(e))


def update(request, row: dict, started: float, **fields):
    row.update(fields, seconds=round(time.perf_counter() - started, 3))
    if row.get("worker"):  # the id, once a lookup has placed the worker
        row["worker_id"] = KNOWN_WORKERS.get(worker_address(row["worker"]))
    request.app[TRAFFIC].publish(row)


# A file part's field in pyworker's JSON, and the field that carries its name.
FILE_FIELDS = {"file": ("file", "filename"), "image": ("image", "filename"), "image[]": ("image", "filename")}


async def form_body(request) -> dict:
    """An OpenAI client's multipart upload as the JSON pyworker takes: each file as base64
    with its name beside it (file + filename, image + filename, mask + mask_filename,
    <field> + <field>_filename), other fields as sent. A repeated field becomes a list."""
    body: dict = {}

    def add(key, value):
        if key in body:
            body[key] = (body[key] if isinstance(body[key], list) else [body[key]]) + [value]
        else:
            body[key] = value

    # aiohttp limits each part to MAX_BODY but not their sum, so the sum is counted here, as
    # it is read: too large stops before the rest is held in memory.
    total = 0

    async def read(part) -> bytes:
        nonlocal total
        chunks = []
        while chunk := await part.read_chunk():
            total += len(chunk)
            if total > MAX_BODY:
                raise web.HTTPRequestEntityTooLarge(max_size=MAX_BODY, actual_size=total)
            chunks.append(chunk)
        return b"".join(chunks)

    async for part in await request.multipart():
        if not part.name:
            raise ValueError("every part needs a field name")
        if part.filename is not None:
            field, name_field = FILE_FIELDS.get(part.name, (part.name, f"{part.name}_filename"))
            add(field, base64.b64encode(await read(part)).decode())
            add(name_field, part.filename)
        else:
            add(part.name, (await read(part)).decode(part.get_charset("utf-8"), "replace"))
    return body


async def choose(request, client: Serverless, which: str | None, model) -> tuple:
    """(entry, None) or (None, error): by path if given, else by model. A miss looks again,
    once, in case the endpoint is new."""
    for fresh in (False, True):
        index = await models_for(request, client, fresh=fresh)
        if which is not None:
            entry = named(index, which)
            error = None if entry else endpoint_not_found(which, index)
        else:
            entry, error = pick_endpoint(index, model, request.app[PREFER])
        if error is None or error.status != 404:
            return entry, error
    return entry, error


def worker_error(result: dict, headers: dict):
    """The worker's own error, with its status. vLLM and SGLang already answer in OpenAI's
    shape; anything else (the SDK wraps non-JSON as {"error": text}) is put in it."""
    status = result.get("status") or 502
    body = result.get("response")
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        resp = web.json_response(body, status=status)
    else:
        # {"error": text} from the SDK, or any other JSON (FastAPI's {"detail": ...}, say).
        text = ((body.get("error") if isinstance(body, dict) else None) or result.get("text")
                or (json.dumps(body) if body is not None else ""))
        resp = openai_error(status, scrub(f"Worker answered HTTP {status}: {text}", limit=2000),
                            "worker_error")
    resp.headers.update(headers)
    return resp


# What a worker's reply may be served as from this origin. Anything else (HTML, SVG, script)
# goes as a download, so a worker can't put a page on this server's origin.
SERVED_TYPES = re.compile(r"(audio|video)/[\w.+-]+|image/(?!svg)[\w.+-]+|application/(json|octet-stream)")
TEXT_TYPES = re.compile(r"text/(plain|vtt|srt|csv)")


def reply(result: dict, headers: dict):
    response = result.get("response")
    status = result.get("status") or 200
    kind = (result.get("content_type") or "").split(";")[0].strip().lower()
    if isinstance(response, (bytes, bytearray)):  # audio, video or an image, as the worker sent it
        if not SERVED_TYPES.fullmatch(kind):
            kind = "application/octet-stream"
            headers = {**headers, "Content-Disposition": "attachment"}
        return web.Response(body=bytes(response), status=status, headers=headers, content_type=kind)
    if isinstance(response, str) or response is None and result.get("text"):  # e.g. text transcriptions
        return web.Response(text=response if isinstance(response, str) else result["text"],
                            status=status, headers=headers,
                            content_type=kind if TEXT_TYPES.fullmatch(kind) else "text/plain")
    return web.json_response(response, status=status, headers=headers)


async def relay_sse(request, result: dict, headers: dict, row: dict, started: float):
    """Server-sent events, as OpenAI streams them. The SDK hands over parsed chunks and drops
    the closing [DONE], so each chunk is written back as an event and [DONE] added. The
    traffic row gets time to first token, then the text and token count at the end."""
    resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache",
                                       **headers, **SECURITY_HEADERS})
    await resp.prepare(request)

    async def fail(message: str):
        error = {"error": {"message": message, "type": "proxy_error"}}
        await resp.write(f"data: {json.dumps(scrub_json(error))}\n\ndata: [DONE]\n\n".encode())
    request[STREAMED] = (resp, fail)

    async def write(data: bytes):  # to the client: its failures are the client leaving
        try:
            await resp.write(data)
        except (ConnectionResetError, aiohttp.ClientConnectionResetError) as e:
            raise PageGone() from e
    text, usage, chunks = "", None, 0
    try:
        async for chunk in result["response"]:
            chunks += 1
            if chunks == 1:
                update(request, row, started, ttft=round(time.perf_counter() - started, 3))
            choice = (chunk.get("choices") or [None])[0] if isinstance(chunk, dict) else None
            if isinstance(choice, dict) and len(text) <= PREVIEW:
                text += (choice.get("delta") or {}).get("content") or choice.get("text") or ""
            usage = (chunk.get("usage") if isinstance(chunk, dict) else None) or usage
            await write(f"data: {json.dumps(scrub_json(chunk))}\n\n".encode())
    except PageGone:
        update(request, row, started, state="cancelled", reply=clip(text), chunks=chunks)
        return resp
    except Exception as e:  # the worker's stream, a reset included
        log.warning("proxied stream broke: %s: %s", type(e).__name__, e)
        update(request, row, started, state="failed", reply=clip(text), chunks=chunks,
               error=clip(failure(e)))
        await fail(failure(e))
        await resp.write_eof()
        return resp
    update(request, row, started, state="done", reply=clip(text), chunks=chunks,
           tokens=(usage or {}).get("completion_tokens"))
    await resp.write(b"data: [DONE]\n\n")
    await resp.write_eof()
    return resp


def host_name(host: str) -> str:
    """The name in a Host header: no port or IPv6 brackets, lower case."""
    try:
        return urllib.parse.urlsplit("//" + host).hostname or ""
    except ValueError:
        return ""


def same_site(request) -> str | None:
    """Why a request is refused, or None. The Host must be a name this server was told it
    has: after DNS rebinding a browser sends the attacker's name, and its Origin matches.
    Browsers send Origin on cross-site posts, and only this server's page should reach it
    from a browser; clients like curl send none."""
    host = request.host or ""
    if host_name(host) not in request.app[ALLOWED_HOSTS]:
        return (f"Host {host!r} is not a name this server answers to; start it with "
                f"--allowed-host {host_name(host) or 'NAME'} to accept it.")
    origin = request.headers.get("Origin")
    if origin and re.sub(r"^https?://", "", origin) != host:
        return f"Requests from {origin} are not accepted."
    return None


def unlocked(request) -> bool:
    """With an access token set, a request carries it unless it only loads the page: as
    X-Serverless-UI-Token, or on the proxy as the bearer token, which is where OpenAI clients put
    their api_key. Without a server key the bearer is the caller's own Vast key, so then the
    token comes only in the header."""
    token = request.app[ACCESS_TOKEN]
    if not token or (request.method in ("GET", "HEAD") and request.path in OPEN_PATHS):
        return True
    remember_secret(token)
    as_bearer = is_proxy(request) and bool(request.app[SERVER_KEY])
    given = request.headers.get(TOKEN_HEADER, "") or (bearer(request) if as_bearer else "")
    return secrets.compare_digest(given.encode(), token.encode())


def locked_out(request) -> web.Response:
    message = "This server needs its access token"
    if is_proxy(request):
        how = "as the API key" if request.app[SERVER_KEY] else f"in the {TOKEN_HEADER} header"
        resp = openai_error(401, f"{message}: send it {how}.", "authentication_error")
    else:
        resp = web.json_response({"error": f"{message}.", "token": True}, status=401)
    resp.headers.update(SECURITY_HEADERS)
    return resp


@web.middleware
async def guard(request, handler):
    """Turns failures into scrubbed JSON and adds security headers to every response.

    Secrets are recorded from a clean slate and forgotten when the request ends, even if
    aiohttp serves the next keep-alive request in the same context."""
    token = _secrets.set(())
    task = asyncio.current_task()
    request.app[HANDLING].add(task)
    try:
        if refused := same_site(request):
            return web.json_response({"error": refused}, status=403, headers=SECURITY_HEADERS)
        if not unlocked(request):
            return locked_out(request)
        try:
            resp = await handler(request)
        except MissingKey:
            resp = web.json_response({"error": "Enter your Vast API key."}, status=401)
        except BadRequest as e:
            resp = web.json_response({"error": str(e)}, status=400)
        except web.HTTPException as e:
            resp = web.json_response({"error": e.reason}, status=e.status)
        except TimedOut as e:
            if (streamed := await end_stream(request, str(e))) is not None:
                return streamed
            resp = web.json_response({"error": str(e)}, status=504)
        except Exception as e:
            rejected = vast_rejected(e)
            message = "Vast rejected this API key." if rejected else failure(e)
            if not rejected:
                log.warning("%s %s failed: %s: %s", request.method, request.path, type(e).__name__, e)
            if (streamed := await end_stream(request, message)) is not None:
                return streamed
            resp = web.json_response({"error": message}, status=401 if rejected else 502)
        if resp.prepared:  # a stream: its headers are sent and each line was scrubbed
            return resp
        # Upstream text can echo a secret anywhere in a body, so every string is scrubbed.
        if isinstance(resp, web.Response) and resp.body is not None:
            if resp.content_type == "application/json":
                try:
                    resp.text = json.dumps(scrub_json(json.loads(resp.text)))
                except ValueError:
                    resp.text = scrub_exact(resp.text)
            elif resp.content_type.startswith("text/"):
                resp.text = scrub_exact(resp.text)
        if request.path.startswith("/api/") or is_proxy(request):
            resp.headers["Cache-Control"] = "no-store"
        resp.headers.update(SECURITY_HEADERS)
        return resp
    finally:
        _secrets.reset(token)
        request.app[HANDLING].discard(task)


async def end_requests(app: web.Application):
    """On shutdown, before aiohttp waits for requests still being handled: end them, as a
    client going away would. The page's worker and traffic streams never end on their own, so
    otherwise Ctrl+C waits out the whole grace period, and a request finishing just as it
    runs out trips aiohttp (InvalidStateError)."""
    for task in list(app[HANDLING]):
        task.cancel()
    if app[HANDLING]:
        await asyncio.wait(list(app[HANDLING]), timeout=3)


def make_app(vast_web_url: str = VAST_WEB_URL, autoscaler_url: str = "", api_key: str = "",
             allowed_hosts=LOOPBACK, prefer: tuple = (), share_traffic: bool = True,
             access_token: str = "", request_timeout: float = REQUEST_TIMEOUT) -> web.Application:
    """autoscaler_url: empty for the SDK's default (https://run.vast.ai). allowed_hosts: the
    Host names accepted; localhost's unless the server is bound elsewhere. share_traffic: show
    the server key's proxy traffic to every page. access_token: required on every request
    but the page's own load, when set. request_timeout: seconds a request may wait for a worker
    to start answering, waiting for one included (see ask())."""
    app = web.Application(client_max_size=MAX_BODY, middlewares=[guard])
    app[WEB_URL] = vast_web_url
    app[AUTOSCALER_URL] = autoscaler_url
    app[SERVER_KEY] = api_key
    app[ALLOWED_HOSTS] = frozenset(h.lower() for h in allowed_hosts)
    app[MODELS] = {}
    app[PREFER] = tuple(prefer)
    app[TRAFFIC] = Traffic()
    app[SHARE_TRAFFIC] = share_traffic
    app[ACCESS_TOKEN] = access_token
    app[TIMEOUT] = float(request_timeout)
    app[HANDLING] = set()
    app.on_shutdown.append(end_requests)
    app.add_routes([web.get("/v1/models", proxy_models), web.post("/v1/{route:.+}", proxy),
                    web.get("/e/{endpoint}/v1/models", proxy_models),
                    web.post("/e/{endpoint}/v1/{route:.+}", proxy),
                    web.post("/e/{endpoint}/generate/sync", proxy),
                    web.get("/api/server", server_info)])
    app.add_routes([web.get("/", index), web.post("/api/endpoints", endpoints),
                    web.post("/api/endpoint", endpoint), web.post("/api/call", call),
                    web.post("/api/burst", burst), web.post("/api/watch", watch),
                    web.post("/api/load", load), web.post("/api/traffic", traffic)])
    return app


def serve(api_key: str = "", key_source: str = "none", host: str = "127.0.0.1", port: int = 8765,
          allowed_hosts=(), access_token: str = "", token_source: str = "SERVERLESS_UI_TOKEN",
          share_traffic: bool = False, prefer=(), vast_web_url: str = VAST_WEB_URL,
          request_timeout: float = REQUEST_TIMEOUT):
    """Checks the settings, says where it listens once it does, and serves until interrupted.
    key_source and token_source name where the key and token came from; never the values.

    A server holding a key, or reachable by others, always has an access token: localhost is
    open to every user and process on the machine, and a proxy in front of it may rewrite Host.
    Without one given, it makes one for this run and prints a link that carries it, in the
    URL's fragment, which browsers never send."""
    if os.environ.get("VAST_DEBUG_WORKER_URL"):
        # The SDK would skip routing and send every user's requests, with their endpoint
        # keys, to this one URL.
        sys.exit("VAST_DEBUG_WORKER_URL is set; refusing to start.")
    key = (api_key or "").strip()
    token = (access_token or "").strip()
    allowed = {h.lower() for h in allowed_hosts}
    local = host in LOOPBACK
    # Reachable by others: bound beyond localhost, or told to answer to another name, which is
    # what a reverse proxy or tunnel in front of localhost needs.
    shared = not local or bool(allowed - LOOPBACK)
    if token and len(token) < MIN_TOKEN:
        sys.exit(f"The access token is too short: use at least {MIN_TOKEN} characters, such as "
                 "the output of `openssl rand -hex 16`.")
    generated = not token and bool(key or shared)
    if generated:
        token = secrets.token_urlsafe(24)
    hosts = LOOPBACK | allowed | (set() if local else bind_names(host))
    # Bound to every address, show one that can be opened: a name over an address.
    shown = host if host not in ("0.0.0.0", "::", "") else (
        min(hosts - LOOPBACK, key=lambda h: (h[0].isdigit() or ":" in h, h), default="127.0.0.1"))
    base = f"http://{'[' + shown + ']' if ':' in shown else shown}:{port}"

    def started(_message):  # aiohttp calls this once the port is bound
        page = f"{base}/#token={token}" if generated else base
        print(f"Serverless UI -> {page}\nOpenAI-compatible proxy -> {base}/v1 (by model), "
              f"{base}/e/<endpoint>/v1 (one endpoint)", flush=True)
        print(f"Key: {key_source if key else 'none'}"
              + ("" if key else " (the page asks for one; proxy clients must send theirs)"), flush=True)
        if not local:
            print(f"Accepting Host: {', '.join(sorted(hosts))}", flush=True)
        if generated:
            print(f"Access token: made for this run, in the link above. Programs send it "
                  f"{'as their API key' if key else 'in the ' + TOKEN_HEADER + ' header'}:\n"
                  f"  export SERVERLESS_UI_TOKEN={token}\n"
                  "Set SERVERLESS_UI_TOKEN before starting to keep one across runs.", flush=True)
        elif token:
            print(f"Access token: from {token_source}; every caller sends it.", flush=True)
        if shared:
            print("This is plain HTTP: the token, any key a caller sends, and every prompt and reply "
                  "cross the network unencrypted. Share it through an SSH tunnel or a TLS proxy.",
                  flush=True)
        if prefer:
            print(f"Prefer: {', '.join(prefer)}", flush=True)
        if key and shared and not share_traffic:
            print("Proxy traffic made with the server's key is not shown to pages; "
                  "--share-traffic shows it.", flush=True)
        print("Ctrl+C to stop.", flush=True)

    configure_logging()
    # No headers, referrer or user agent in the access log; the key never travels in a URL.
    try:
        # handler_cancellation: a client that goes away (gave up, timed out, retried) takes its
        # request with it, rather than leaving it to wait for a worker and run unread.
        web.run_app(make_app(vast_web_url, api_key=key, allowed_hosts=hosts, prefer=tuple(prefer),
                             share_traffic=not shared or share_traffic, access_token=token,
                             request_timeout=request_timeout),
                    host=host, port=port, print=started, access_log_format='%a "%r" %s %b %Tfs',
                    handler_cancellation=True, shutdown_timeout=5)
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            sys.exit(f"Port {port} on {host} is in use. Pass --port N (or set SERVERLESS_UI_PORT).")
        sys.exit(f"Could not listen on {host}:{port}: {e.strerror or e}")


def bind_names(host: str) -> set:
    """The Host names a server bound to `host` can be reached by: the address itself (unless
    it is every address), the machine's names, and the addresses those resolve to."""
    names = set() if host in ("0.0.0.0", "::", "") else {host.lower()}
    for name in {socket.gethostname(), socket.getfqdn()}:
        names.add(name.lower())
        with contextlib.suppress(OSError):
            names |= {info[4][0].split("%")[0] for info in socket.getaddrinfo(name, None)}
    with contextlib.suppress(OSError), socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("192.0.2.1", 9))  # picks the outgoing interface; a UDP connect sends nothing
        names.add(s.getsockname()[0])
    return names

