"""A fake console.vast.ai, autoscaler and worker, echoing secrets back wherever the real
ones could.

Endpoint 7 has workergroup 90, whose template sets a vLLM model and also carries an
HF_TOKEN and a docker password. Every workergroup row echoes the account key, as the real
API does. /route/ hands out this same server as the worker, with signed auth_data the page
must never see. Tests change `state` to try other shapes.
"""
import asyncio
import base64
import json
import re

from aiohttp import web

KEY = "SENTINEL0123456789abcdef0123456789abcdef"
ENDPOINT_KEY = "EPKEY-fedcba9876543210fedcba9876543210"
HF_TOKEN = "hf_SENTINELtoken0123456789abcdef"
DOCKER_PASS = "dockerpass-SENTINEL-0123456789"
WORKER_SIGNATURE = "SIGNATURE-SENTINEL-0123456789abcdef"
SECRETS = (KEY, ENDPOINT_KEY, HF_TOKEN, DOCKER_PASS, WORKER_SIGNATURE)
SERVED_MODEL = "Qwen/Qwen3-8B"  # what the fake worker serves, as VLLM_MODEL in TEMPLATE


def assert_clean(*texts):
    """None of the secrets above appear in these responses or logs."""
    for text in texts:
        for secret in SECRETS:
            assert secret not in text, secret
WAV = b"RIFF\x24\x00\x00\x00WAVEfmt fake audio"
AUTH = {"Authorization": f"Bearer {KEY}"}

TEMPLATE_HASH = "a" * 32
TEMPLATE = {
    "id": 501, "hash_id": TEMPLATE_HASH, "name": "vLLM Qwen3", "image": "vastai/vllm",
    "tag": "v0.11", "docker_login_pass": DOCKER_PASS,
    "env": (f"-p 8000:8000 -e BACKEND=vllm -e VLLM_MODEL=Qwen/Qwen3-8B -e HF_TOKEN={HF_TOKEN} "
            "-e OPENAI_ROUTES=/v1/chat/completions,/v1/embeddings "
            "-e BENCHMARK_ROUTE=/v1/chat/completions"),
}


# A ComfyUI template as the Z-Image one is written: no BACKEND (the image bakes it), and the
# workflows and sample inputs exported in onstart.
COMFY_HASH = "c" * 32
COMFY_TEMPLATE = {
    "id": 502, "hash_id": COMFY_HASH, "name": "Z-Image ComfyUI", "image": "vastai/comfy",
    "tag": "v0.43.0-cuda-13.2-py312", "env": "-p 18288:18288",
    "onstart": ('export PROVISIONING_COMFYUI_WORKFLOWS="https://raw.githubusercontent.com/Comfy-Org/'
                'workflow_templates/refs/heads/main/templates/image_z_image.json"\n'
                'export PROVISIONING_DOWNLOADS="https://x/input/fighter_jet.png|${WORKSPACE}/ComfyUI/input/'
                f'fighter_jet.png"\nexport HF_TOKEN={HF_TOKEN}\nexport SERVERLESS=true\nentrypoint.sh'),
}
# An API-format workflow as convert-workflows.sh leaves it on a worker, cut down: a positive
# and a negative prompt (told apart by the sampler input they feed), a seed, a size and an
# input image.
Z_IMAGE = {
    "3": {"class_type": "KSampler", "inputs": {"seed": "__RANDOM_INT__", "steps": 8, "cfg": 1,
          "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0], "model": ["4", 0]}},
    "4": {"class_type": "UNETLoader", "inputs": {"unet_name": "z_image_turbo.safetensors"}},
    "5": {"class_type": "EmptySD3LatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "a lighthouse at dusk", "clip": ["4", 0]}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry", "clip": ["4", 0]}},
    "8": {"class_type": "LoadImage", "inputs": {"image": "fighter_jet.png"}},
    "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "z-image", "images": ["3", 0]}},
}
PNG = bytes.fromhex("89504e470d0a1a0a") + b"comfy output"


def initial_state() -> dict:
    return {
        "mode": "ok",
        "endpoints": [7],  # 8 (workergroup 91) is listed only when a test adds it
        "templates": [dict(TEMPLATE), dict(COMFY_TEMPLATE)],
        "workergroups": [
            {"id": 90, "endpoint_id": 7, "template_hash": TEMPLATE_HASH, "template_id": None,
             "launch_args": None},
            {"id": 91, "endpoint_id": 8, "template_hash": None, "template_id": 999,
             "launch_args": None},
            {"id": 92, "endpoint_id": 9, "template_hash": COMFY_HASH, "template_id": None,
             "launch_args": None},
        ],
    }


NAMES = {7: "flux-demo", 8: "flux-b", 9: "comfy-demo"}


def decode(value: str) -> bytes:
    """base64, or a data: URI, as pyworker accepts both."""
    return base64.b64decode(value.split(",", 1)[1] if value.startswith("data:") else value)


def said(content) -> str:
    """A message as the fake model reads it: text, and what each attached part is."""
    if isinstance(content, str):
        return content
    out = []
    for part in content:
        kind = part.get("type")
        if kind == "text":
            out.append(part["text"])
        else:
            data = part.get(kind, {})
            url = data.get("url") or data.get("data") or ""
            mime = url[5:url.index(";")] if url.startswith("data:") else data.get("format", "?")
            out.append(f"[{kind} {mime} {len(decode(url))} bytes]")
    return " ".join(out)


def _endpoint(id_):
    return {"id": id_, "endpoint_name": NAMES[id_], "api_key": ENDPOINT_KEY, "user_id": 1,
            "created_at": 0.0, "endpoint_state": "active"}


def make_app(state: dict) -> web.Application:
    def upstream_failure(request):
        if state["mode"] == "bad-key":  # what console.vast.ai really sends
            return web.json_response(
                {"success": False, "error": "auth_error", "msg": "Invalid user key"}, status=404)
        if state["mode"] == "reject":
            leak = f"bad key at {request.url} with {request.headers.get('Authorization')}"
            return web.Response(status=401, text=leak)
        return None

    async def endptjobs(request):
        return upstream_failure(request) or web.json_response({"results": [_endpoint(i) for i in state["endpoints"]]})

    async def endptjob(request):
        if failed := upstream_failure(request):
            return failed
        id_ = int(request.match_info["id"])
        if id_ not in state["endpoints"]:
            return web.json_response({"success": False, "msg": "Not found"}, status=404)
        return web.json_response({"success": True, "result": _endpoint(id_)})

    async def workergroups(request):
        if failed := upstream_failure(request):
            return failed
        return web.json_response({"success": True, "results": [
            {**g, "api_key": KEY} for g in state["workergroups"]]})

    async def template(request):
        state["template_calls"] = state.get("template_calls", 0) + 1
        if state["mode"] == "template-leak":
            return web.Response(status=403, text=f"template lookup failed for {request.url}")
        where = json.loads(request.query["select_filters"])
        field, value = next(iter(where.items()))
        match = [t for t in state["templates"] if t.get(field) == value["eq"]]
        return web.json_response({"success": True, "templates": match})

    async def instances(request):
        """Worker 1001 is this server (it is the worker /route/ hands out); 1000 is elsewhere,
        and 5555 is not a worker. Instances carry secrets the page must never see."""
        if failed := upstream_failure(request):
            return failed
        state["instance_lookups"] = state.get("instance_lookups", 0) + 1
        def inst(id_, port):
            return {"id": id_, "public_ipaddr": "127.0.0.1\n", "extra_env": [["HF_TOKEN", HF_TOKEN]],
                    "ports": {"8000/tcp": [{"HostIp": "0.0.0.0", "HostPort": str(port)}]}}
        # Like /api/v1/instances/: filtered by select_filters, one row per page to test paging.
        wanted = set(json.loads(request.query["select_filters"])["id"]["in"])
        if state.get("instances_hidden"):
            wanted = set()
        rows = [r for r in (inst(1000, 1), inst(1001, request.url.port), inst(5555, 2)) if r["id"] in wanted]
        start = int(request.query.get("after_token", 0))
        more = start + 1 < len(rows)
        return web.json_response({"instances": rows[start:start + 1],
                                  **({"next_token": str(start + 1)} if more else {})})

    async def route(request):
        body = await request.json()
        state.setdefault("routed", []).append({"cost": body.get("cost")})
        state.setdefault("routed_to", []).append(body.get("endpoint"))
        return web.json_response({"url": str(request.url.origin()), "request_idx": 1,
                                  "signature": WORKER_SIGNATURE, "endpoint": body["endpoint"]})

    async def chat(request):
        payload = (await request.json())["payload"]
        state.setdefault("payloads", []).append(payload)
        served = re.search(r"VLLM_MODEL=(\S+)", state["templates"][0]["env"]).group(1)
        if payload.get("model", served) != served:  # as vLLM: only the model its template serves
            return web.json_response({"object": "error", "type": "NotFoundError", "code": 404,
                                      "message": f"The model `{payload['model']}` does not exist."}, status=404)
        try:  # a slow worker; one whose caller goes away sees its request cancelled
            await asyncio.sleep(state.get("chat_delay", 0))
        except asyncio.CancelledError:
            state["chat_cancelled"] = state.get("chat_cancelled", 0) + 1
            raise
        # "reasoning": like vLLM with a reasoning parser; "some" thinks then answers,
        # "all" spends max_tokens thinking and never answers.
        reasoning = state.get("reasoning")
        thought = "Let me think." if reasoning else None
        if not payload.get("stream"):
            content = None if reasoning == "all" else f"echo: {said(payload['messages'][-1]['content'])}"
            return web.json_response({"choices": [{"message": {
                "role": "assistant", "content": content, "reasoning_content": thought},
                "finish_reason": "length" if reasoning == "all" else "stop"}]})
        resp = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
        await resp.prepare(request)
        deltas = [{"reasoning_content": w} for w in ("Let me", " think.")] if reasoning else []
        if state.get("stream_echo"):  # the reply, written back in one chunk
            deltas += [{"content": f"echo: {said(payload['messages'][-1]['content'])}"}]
        elif reasoning != "all":
            deltas += [{"content": w} for w in ("Hello", " there")]
        for i, delta in enumerate(deltas):
            last = i == len(deltas) - 1
            chunk = {"choices": [{"delta": delta, "finish_reason": ("length" if reasoning == "all" else "stop")
                                  if last else None}]}
            await resp.write(f"data: {json.dumps(chunk)}\n\n".encode())
            await asyncio.sleep(0.01)
        usage = {"choices": [], "usage": {"completion_tokens": 2}}
        await resp.write(f"data: {json.dumps(usage)}\n\ndata: [DONE]\n\n".encode())
        return resp

    async def speech(request):
        return web.Response(body=WAV, content_type="audio/wav")

    async def images(request):
        payload = (await request.json())["payload"]
        state.setdefault("payloads", []).append(payload)
        await asyncio.sleep(state.get("image_delay", 0))
        return web.json_response({"data": [{"b64_json": "aW1hZ2U="}] * int(payload.get("n", 1))})

    async def transcribe(request):
        """Like pyworker: a base64 (or data: URI) file and its filename; text if asked."""
        payload = (await request.json())["payload"]
        state.setdefault("payloads", []).append(payload)
        heard = f"heard {payload.get('filename')} ({len(decode(payload['file']))} bytes)"
        if payload.get("response_format") == "text":
            return web.Response(text=heard, content_type="text/plain")
        return web.json_response({"text": heard})

    async def edit(request):
        payload = (await request.json())["payload"]
        state.setdefault("payloads", []).append(payload)
        images = payload["image"] if isinstance(payload["image"], list) else [payload["image"]]
        sizes = [len(decode(i)) for i in images]
        return web.json_response({"data": [{"b64_json": "aW1hZ2U="}], "edited": sizes})

    async def video(request):
        payload = (await request.json())["payload"]
        state.setdefault("payloads", []).append(payload)
        ref = payload.get("input_reference")
        return web.Response(body=b"fake mp4" + (b" from %d bytes" % len(decode(ref)) if ref else b""),
                            content_type="video/mp4")

    async def comfy(request):
        """The ComfyUI API wrapper's /generate/sync: a whole workflow in, outputs inline as
        base64 only when asked for, with its timings."""
        payload = (await request.json())["payload"]
        state.setdefault("payloads", []).append(payload)
        inp = payload.get("input") or {}
        if not isinstance(inp.get("workflow_json"), dict) or not inp["workflow_json"]:
            return web.json_response({"detail": "workflow_json or modifier required"}, status=422)
        out = {"filename": "z-image_00001_.png", "local_path": "/workspace/ComfyUI/output/z-image_00001_.png"}
        if inp.get("return_outputs_as_base64"):
            out.update(data=base64.b64encode(PNG).decode(), mimetype="image/png")
        return web.json_response({"id": inp.get("request_id") or "req-1", "status": "completed",
                                  "message": "Request completed", "comfyui_response": {"p1": {}},
                                  "output": [out], "timings": {"queued": 0.1, "generation": 1.2, "total": 1.4}})

    async def leaky_error(request):  # a worker error that echoes the query string
        return web.Response(status=422, text=f"bad request to {request.url}")

    async def embeddings(request):
        """The 422 above, unless a test asks for vectors."""
        if not state.get("embeddings_ok"):
            return await leaky_error(request)
        payload = (await request.json())["payload"]
        return web.json_response({"data": [{"index": i, "embedding": [0.6, 0.8] + [0.0] * 6}
                                           for i, _ in enumerate(payload["input"])],
                                  "usage": {"prompt_tokens": 7}})

    async def rerank(request):  # vLLM's shape; the best match is the last document
        docs = (await request.json())["payload"]["documents"]
        return web.json_response({"results": [{"index": i, "relevance_score": (i + 1) / len(docs),
                                               "document": {"text": d}} for i, d in enumerate(docs)]})

    async def score(request):
        items = (await request.json())["payload"]["items"]
        return web.json_response({"data": [{"index": i, "score": 0.5 / (i + 1)} for i in range(len(items))]})

    async def speech_batch(request):
        items = (await request.json())["payload"]["items"]
        wav = base64.b64encode(WAV).decode()
        return web.json_response({"results": [
            {"index": i, "status": "success", "audio_data": wav, "media_type": "audio/wav"} if i else
            {"index": i, "status": "error", "error": "voice not found"} for i in range(len(items))]})

    def workers(n):
        # Every worker carries a field it must not pass on, to test the whitelist.
        return [{"id": 1000 + i, "status": "running" if i else "model_loading", "gpu_name": "RTX 5090",
                 "num_gpus": 1, "reqs_working": i, "cur_load": 10.0 * i, "perf": 50.0,
                 "started_at": 1.0, "loaded_at": 0.0, "api_key": ENDPOINT_KEY} for i in range(n)]

    async def worker_socket(request):
        state["ws_connects"] = state.get("ws_connects", 0) + 1
        if state["mode"] == "ws-down" or request.query.get("api_key") != KEY:
            return web.Response(status=503, text=f"unavailable: {request.url}")
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        allowed = {("endpoint", 7), ("autogroup", 90), ("endpoint", 9), ("autogroup", 92)}
        topics = []

        async def push():
            while state["mode"] != "ws-silent":
                for kind, id_ in list(topics):
                    await ws.send_json({"type": "endpoint_workers" if kind == "endpoint" else
                                        "autogroup_workers", "id": id_, "timestamp": 1.0,
                                        "workers": workers(2 if kind == "endpoint" else 1),
                                        **({"active_update": False} if kind == "autogroup" else {})})
                await asyncio.sleep(0.02)

        pusher = asyncio.create_task(push())
        try:
            async for msg in ws:
                sub = json.loads(msg.data)
                topic = (sub["type"], sub["id"])
                if topic in allowed:
                    topics.append(topic)
                    await ws.send_json({"status": "subscribed", "topic": f"{sub['type']}:{sub['id']}"})
                else:
                    await ws.send_json({"error": f"not authorized for {sub['type']}:{sub['id']}"})
        finally:
            pusher.cancel()
        return ws

    async def endpoint_workers(request):
        state["rest_polls"] = state.get("rest_polls", 0) + 1
        return web.json_response(workers(3))

    app = web.Application()
    app.router.add_get("/ws/workers/", worker_socket)
    app.router.add_post("/get_endpoint_workers/", endpoint_workers)
    app.router.add_post("/route/", route)
    app.router.add_post("/v1/chat/completions", chat)
    app.router.add_post("/v1/audio/speech", speech)
    app.router.add_post("/v1/images/generations", images)
    app.router.add_post("/v1/embeddings", embeddings)
    app.router.add_post("/generate/sync", comfy)
    app.router.add_post("/v1/rerank", rerank)
    app.router.add_post("/v1/score", score)
    app.router.add_post("/v1/audio/speech/batch", speech_batch)
    app.router.add_post("/v1/audio/generate", speech)
    app.router.add_post("/v1/audio/transcriptions", transcribe)
    app.router.add_post("/v1/audio/translations", transcribe)
    app.router.add_post("/v1/images/edits", edit)
    app.router.add_post("/v1/videos/sync", video)
    app.router.add_get("/api/v0/endptjobs/", endptjobs)
    app.router.add_get("/api/v0/endptjobs/{id}/", endptjob)
    app.router.add_get("/api/v0/workergroups/", workergroups)
    app.router.add_get("/api/v0/template/", template)
    app.router.add_get("/api/v1/instances/", instances)
    return app
