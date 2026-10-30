"""Exercise every route of real endpoints through a running serverless UI, and the proxy.

    python tests/cli/serverless_ui/live_check.py [--server http://127.0.0.1:8766] [--prefix qs-] [--out DIR]

Not run by pytest: it calls real endpoints, which need running workers. Point it at a serverless UI
started with the key that owns the endpoints (VAST_API_KEY). For each endpoint whose name
starts with --prefix it checks what discovery reads, sends a realistic request to each route
the endpoint serves, checks the reply is the right kind, and saves media to --out so it can
be looked at and listened to. Then it repeats the main calls through the proxy with the
openai client, as a user's code would.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import urllib.request
from openai import OpenAI

# pyworker's speech benchmark sample (10.7 s of English), from a checkout: $PYWORKER, else ../pyworker
SPEECH_WAV = Path(os.environ.get("PYWORKER", "../pyworker")) / "workers/openai/benchmark_speech.wav"
LONG = 900  # seconds: a video or a song can take minutes
TOKEN = os.environ.get("SERVERLESS_UI_TOKEN", "")  # a shared server's access token
TOKEN_HEADER = {"X-Serverless-UI-Token": TOKEN} if TOKEN else {}


def media(out: Path):
    """A colour-bar PNG and a 2-second test-pattern MP4, made with ffmpeg."""
    png, mp4 = out / "input.png", out / "input.mp4"
    for args, path in ((["-f", "lavfi", "-i", "smptebars=size=512x512", "-frames:v", "1"], png),
                       (["-f", "lavfi", "-i", "testsrc=size=320x240:rate=8", "-t", "2", "-pix_fmt", "yuv420p"], mp4)):
        if not path.exists():
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args, str(path)], check=True)
    return png.read_bytes(), mp4.read_bytes(), SPEECH_WAV.read_bytes()


def data_uri(kind: str, raw: bytes) -> str:
    return f"data:{kind};base64,{base64.b64encode(raw).decode()}"


def bodies(png: bytes, mp4: bytes, wav: bytes) -> dict:
    """route -> [(label, body)]: what a person would try first."""
    chat = lambda content, **kw: {"messages": [{"role": "user", "content": content}], "max_tokens": 256, **kw}  # noqa: E731
    return {
        "/v1/completions": [("text", {"prompt": "The capital of France is", "max_tokens": 16})],
        "/v1/chat/completions": [
            ("text", chat("In one sentence, what is a GPU?")),
            ("image", chat([{"type": "text", "text": "What colours are in this image? One sentence."},
                            {"type": "image_url", "image_url": {"url": data_uri("image/png", png)}}])),
            ("audio", chat([{"type": "text", "text": "What is said in this audio? One sentence."},
                            {"type": "audio_url", "audio_url": {"url": data_uri("audio/wav", wav)}}])),
            ("video", chat([{"type": "text", "text": "Describe this video in one sentence."},
                            {"type": "video_url", "video_url": {"url": data_uri("video/mp4", mp4)}}])),
        ],
        "/v1/chat/completions/batch": [("batch", {"messages": [[{"role": "user", "content": "Name a planet."}],
                                                                [{"role": "user", "content": "Name an ocean."}]],
                                                   "max_tokens": 32})],
        "/v1/embeddings": [("texts", {"input": ["A quick update on the project.", "The weather is fine."]})],
        "/v1/rerank": [("rerank", {"query": "How do I reset my password?",
                                    "documents": ["Use the Forgot login link and follow the email.",
                                                  "Our office is closed on public holidays."]})],
        "/v1/score": [("score", {"queries": "How do I reset my password?",
                                 "items": ["Use the Forgot login link and follow the email.",
                                           "Our office is closed on public holidays."]})],
        "/v1/audio/transcriptions": [("speech", {"file": data_uri("audio/wav", wav), "filename": "speech.wav"})],
        "/v1/audio/translations": [("speech", {"file": data_uri("audio/wav", wav), "filename": "speech.wav"})],
        "/v1/audio/speech": [("speech", {"input": "Hello from a Vast serverless endpoint.", "response_format": "wav"})],
        "/v1/audio/speech/batch": [("batch", {"items": [{"input": "One."}, {"input": "Two."}],
                                              "response_format": "wav"})],
        "/v1/images/generations": [("generate", {"prompt": "A lighthouse on a rocky coast at dusk", "n": 1,
                                                 "size": "512x512"})],
        "/v1/images/edits": [("edit", {"image": data_uri("image/png", png), "filename": "input.png",
                                       "prompt": "Make it look like a watercolour painting"})],
        "/v1/videos/sync": [
            ("text to video", {"prompt": "A red kite over a beach, slow pan", "width": 832, "height": 480,
                               "num_frames": 17}),
            ("image to video", {"prompt": "The bars slowly ripple", "width": 512, "height": 512, "num_frames": 17,
                                "input_reference": data_uri("image/png", png),
                                "input_reference_filename": "input.png"})],
    }


MUSIC = [("song", {"input": "[verse]\nLights on the water, the night is young\n",
                   "instructions": "upbeat indie pop, female vocals, 110 BPM", "max_new_tokens": 250,
                   "seed": 1, "response_format": "wav", "extra_params": {"cot": "off"}})]


def check(route: str, env: dict) -> tuple:
    """(passed, what came back)."""
    r = env.get("response")
    kind = (env.get("media") or {}).get("type", "")
    if not env.get("ok"):
        return False, (env.get("error") or f"HTTP {env.get('status')}")[:300]
    if route in ("/v1/completions", "/v1/chat/completions"):
        c = (r or {}).get("choices", [{}])[0]
        text = (c.get("message") or {}).get("content") or c.get("text") or ""
        return bool(text.strip()), json.dumps(text.strip()[:140])
    if route == "/v1/chat/completions/batch":
        texts = [(c.get("message") or {}).get("content", "") for c in (r or {}).get("choices", [])]
        return len(texts) == 2 and all(texts), json.dumps(texts)[:140]
    if route == "/v1/embeddings":
        v = [d["embedding"] for d in (r or {}).get("data", [])]
        return len(v) == 2 and len(v[0]) > 0, f"{len(v)} vectors of {len(v[0]) if v else 0}"
    if route == "/v1/rerank":
        res = r if isinstance(r, list) else (r or {}).get("results", [])
        best = max(res, key=lambda x: x.get("relevance_score", x.get("score", 0)), default={})
        return best.get("index") == 0, f"best document {best.get('index')} ({best.get('relevance_score', best.get('score'))})"
    if route == "/v1/score":
        d = (r or {}).get("data", [])
        return len(d) == 2 and d[0]["score"] > d[1]["score"], ", ".join(f"{x['score']:.3f}" for x in d)
    if route in ("/v1/audio/transcriptions", "/v1/audio/translations"):
        text = r if isinstance(r, str) else (r or {}).get("text", "")
        return bool(text.strip()), json.dumps(text.strip()[:140])
    if route in ("/v1/audio/speech", "/v1/audio/generate"):
        return kind.startswith("audio/"), f"{kind}, {len(env['media']['b64']) * 3 // 4 // 1024} KB" if kind else str(r)[:200]
    if route == "/v1/audio/speech/batch":
        items = (r or {}).get("results", [])
        good = [i for i in items if i.get("status") == "success" and i.get("audio_data")]
        return len(good) == 2, f"{len(good)}/{len(items)} items with audio" + "".join(
            f"; {i.get('error')}" for i in items if i not in good)
    if route in ("/v1/images/generations", "/v1/images/edits"):
        n = len([d for d in (r or {}).get("data", []) if d.get("b64_json") or d.get("url")])
        return n > 0, f"{n} image(s)"
    if route == "/v1/videos/sync":
        return kind.startswith("video/"), f"{kind}, {len(env['media']['b64']) * 3 // 4 // 1024} KB" if kind else str(r)[:200]
    return True, json.dumps(r)[:140]


def save(out: Path, stem: str, env: dict):
    """Media and images to disk, to look at and listen to."""
    m = env.get("media")
    if m:
        ext = m["type"].split("/")[-1].replace("mpeg", "mp3")
        (out / f"{stem}.{ext}").write_bytes(base64.b64decode(m["b64"]))
    r = env.get("response")
    for i, d in enumerate((r or {}).get("data", []) if isinstance(r, dict) else []):
        if isinstance(d, dict) and d.get("b64_json"):
            (out / f"{stem}-{i}.png").write_bytes(base64.b64decode(d["b64_json"]))
    for i in ((r or {}).get("results", []) if isinstance(r, dict) else []):
        if isinstance(i, dict) and i.get("audio_data"):
            (out / f"{stem}-{i.get('index')}.wav").write_bytes(base64.b64decode(i["audio_data"]))


class Server:
    """JSON posts to the server's /api, with the server's own key (no Authorization) and its
    access token, if SERVERLESS_UI_TOKEN is set."""

    def __init__(self, base: str):
        self.base = base

    def post(self, path: str, body: dict) -> dict:
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", **TOKEN_HEADER})
        with urllib.request.urlopen(req, timeout=LONG) as resp:
            return json.load(resp)


def found_model(api, ep) -> str:
    return api.post("/api/endpoint", {"id": ep["id"]})["summary"]["model"]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--server", default="http://127.0.0.1:8765")
    p.add_argument("--prefix", default="qs-")
    p.add_argument("--only", default="", help="comma-separated endpoint names")
    p.add_argument("--out", default=None, help="where media goes (default: a new temporary directory)")
    a = p.parse_args()
    out = Path(a.out or tempfile.mkdtemp(prefix="live-check-"))
    out.mkdir(parents=True, exist_ok=True)
    png, mp4, wav = media(out)
    tests = bodies(png, mp4, wav)
    api = Server(a.server)
    rows, failed = [], 0
    endpoints = [e for e in api.post("/api/endpoints", {})["endpoints"]
                 if e["name"].startswith(a.prefix) and (not a.only or e["name"] in a.only.split(","))]
    for ep in sorted(endpoints, key=lambda e: e["name"]):
        found = api.post("/api/endpoint", {"id": ep["id"]})
        s = found["summary"]
        print(f"\n== {ep['name']}: {s['family']}/{s['backend']} {s['model']} routes={','.join(r[4:] for r in s['routes'])}"
              + (f" WARNINGS={s['warnings']}" if s["warnings"] else ""), flush=True)
        for route in s["routes"]:
            cases = MUSIC if "YuE" in (s["model"] or "") and route == "/v1/audio/speech" else tests.get(route, [])
            if route == "/v1/chat/completions" and not any(m in (s["model"] or "") for m in ("Omni", "VL")):
                cases = cases[:1]  # images, audio and video only for a multimodal model
            for label, body in cases:
                started = time.time()
                try:
                    env = api.post("/api/call", {"endpoint": ep["id"], "route": route,
                                                 "body": {"model": s["model"], **body}})
                    ok, detail = check(route, env)
                    save(out, f"{ep['name']}-{route[4:].replace('/', '-')}-{label.replace(' ', '-')}", env)
                except Exception as e:
                    env, ok, detail = {}, False, f"{type(e).__name__}: {e}"
                failed += not ok
                worker = (env.get("worker") or "-").split("//")[-1]
                line = (f"  {'PASS' if ok else 'FAIL'} {route:28} {label:15} {env.get('status', '-')!s:4} "
                        f"{time.time() - started:6.1f}s {worker:22} {detail}")
                print(line, flush=True)
                rows.append(line)

    # The proxy, with the openai client, on the endpoints that serve each kind of call.
    print("\n== proxy (openai client)", flush=True)
    by_route = {}
    for ep in sorted(endpoints, key=lambda e: e["name"]):
        for route in api.post("/api/endpoint", {"id": ep["id"]})["summary"]["routes"]:
            by_route.setdefault(route, (ep["name"], found_model(api, ep)))
    client = lambda name: OpenAI(base_url=f"{a.server}/e/{name}/v1", api_key=TOKEN or "unused", timeout=900)  # noqa: E731
    proxied = [
        ("/v1/chat/completions", lambda c, m: c.chat.completions.create(
            model=m, messages=[{"role": "user", "content": "Say hello."}], max_tokens=32,
            stream=True)),
        ("/v1/embeddings", lambda c, m: c.embeddings.create(model=m, input="hello")),
        ("/v1/audio/transcriptions", lambda c, m: c.audio.transcriptions.create(
            model=m, file=("speech.wav", wav, "audio/wav"))),
        ("/v1/images/edits", lambda c, m: c.images.edit(model=m, image=("input.png", png, "image/png"),
                                                     prompt="Make it blue")),
    ]
    for route, call in proxied:
        if route not in by_route:
            continue
        started = time.time()
        try:
            name, model = by_route[route]
            got = call(client(name), model)
            if hasattr(got, "__iter__") and not hasattr(got, "model_dump"):  # a stream
                got = "".join((ch.choices[0].delta.content or "") for ch in got if ch.choices)
            ok, detail = True, str(got)[:120]
        except Exception as e:
            ok, detail = False, f"{type(e).__name__}: {e}"[:200]
        failed += not ok
        print(f"  {'PASS' if ok else 'FAIL'} {route:28} {by_route[route][0]:15} {time.time() - started:6.1f}s {detail}", flush=True)
    print(f"\n{failed} failed. Media in {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
