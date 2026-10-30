"""ComfyUI endpoints: discovery, calls and the proxy."""
import asyncio
import base64
import json

import pytest

from vastai.serverless.ui import server as ui
from .fake_vast import AUTH, KEY, PNG, Z_IMAGE, assert_clean

COMFY = "/generate/sync"


@pytest.fixture(autouse=True)
def comfy_endpoint(vast_api):
    vast_api.state["endpoints"] = [7, 9]


def body(**extra):
    return {"input": {"workflow_json": Z_IMAGE, "return_outputs_as_base64": True, **extra}}


async def test_discovery_reads_the_image_and_onstart(client, logs):
    resp = await client.post("/api/endpoint", json={"id": 9}, headers=AUTH)
    text = await resp.text()
    summary = json.loads(text)["summary"]
    assert (summary["family"], summary["backend"], summary["routes"]) == ("comfyui-json", "comfyui-json", [COMFY])
    assert summary["comfy"] == {"workflows": ["image_z_image.json"], "inputs": ["fighter_jet.png"]}
    assert_clean(text, logs.getvalue())  # onstart exports an HF_TOKEN


async def test_call_returns_outputs_inline(client, vast_api, logs):
    resp = await client.post("/api/call", headers=AUTH, json={"endpoint": 9, "route": COMFY, "body": body()})
    env = await resp.json()
    assert env["ok"] and env["route"] == COMFY and env["worker"]
    [out] = env["response"]["output"]
    assert base64.b64decode(out["data"]) == PNG and out["mimetype"] == "image/png"
    assert env["response"]["timings"]["total"] == 1.4
    assert vast_api.state["payloads"][-1] == body()  # sent as written
    assert vast_api.state["routed"][-1] == {"cost": 100}


async def test_an_empty_workflow_is_the_workers_error(client):
    env = await (await client.post("/api/call", headers=AUTH, json={
        "endpoint": 9, "route": COMFY, "body": {"input": {}}})).json()
    assert not env["ok"] and env["status"] == 422


async def test_proxy_passes_comfyui_through(aiohttp_client, vast_api, logs):
    base = str(vast_api.make_url("")).rstrip("/")
    proxy = await aiohttp_client(ui.make_app(base, autoscaler_url=base, api_key=KEY))
    watching = asyncio.create_task(proxy.post("/api/traffic", json={}))
    resp = await proxy.post("/e/comfy-demo/generate/sync", json=body())
    assert resp.status == 200 and resp.headers["X-Vast-Endpoint"] == "comfy-demo" and resp.headers["X-Vast-Worker"]
    assert (await resp.json())["output"][0]["mimetype"] == "image/png"
    assert "model" not in vast_api.state["payloads"][-1]  # not an OpenAI request: nothing added
    # By model there is nothing to pick: a ComfyUI endpoint is reached by its path.
    assert (await proxy.post("/v1/generate/sync", json=body())).status == 404
    traffic = await watching
    rows = []  # the watch began before the request, so the row arrives live, not in the history
    while not any(r.get("state") == "done" for r in rows):
        line = json.loads(await asyncio.wait_for(traffic.content.readline(), 5))
        rows += line["requests"] if line["type"] == "history" else [line]
    traffic.close()
    row = next(r for r in rows if r.get("state") == "done")
    assert row["prompt"] == "a lighthouse at dusk"  # the positive prompt, not the negative
    assert row["reply"] == "completed: 1 output(s) image/png" and row["route"] == COMFY
    assert_clean(json.dumps(rows), logs.getvalue())


def test_workflow_prompt_prefers_the_positive_input():
    flipped = {**Z_IMAGE, "3": {**Z_IMAGE["3"], "inputs": {**Z_IMAGE["3"]["inputs"],
                                                          "positive": ["7", 0], "negative": ["6", 0]}}}
    assert ui.workflow_prompt(Z_IMAGE) == "a lighthouse at dusk"
    assert ui.workflow_prompt(flipped) == "blurry"
    assert ui.workflow_prompt({"1": {"class_type": "X", "inputs": {"prompt": "only one"}}}) == "only one"
    assert ui.workflow_prompt("nonsense") == ""
