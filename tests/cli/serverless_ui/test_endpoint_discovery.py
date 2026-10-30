"""POST /api/endpoint: workergroups and templates in, only derived fields out."""
from .fake_vast import AUTH, HF_TOKEN, TEMPLATE, assert_clean


async def discover(client, id_=7):
    return await client.post("/api/endpoint", json={"id": id_}, headers=AUTH)


async def test_reads_backend_model_and_routes_from_the_template(client, logs):
    resp = await discover(client)
    assert resp.status == 200
    body = await resp.json()
    assert body["endpoint"] == {"id": 7, "name": "flux-demo", "state": "active"}
    assert body["summary"] == {
        "family": "openai", "backend": "vllm", "model": "Qwen/Qwen3-8B",
        "routes": ["/v1/chat/completions", "/v1/embeddings"], "warnings": [], "comfy": None}
    [group] = body["workergroups"]  # workergroup 91 belongs to another endpoint
    assert group["id"] == 90
    assert group["template"] == {k: TEMPLATE[k] for k in ("id", "hash_id", "name", "image", "tag")}
    assert "HF_TOKEN" not in group["detected"]["env"]
    assert_clean(await resp.text(), logs.getvalue())


async def test_launch_args_env_overrides_the_template(client, vast_api):
    vast_api.state["workergroups"][0]["launch_args"] = (
        f"--image x --env '-e VLLM_MODEL=org/override -e HF_TOKEN={HF_TOKEN}'")
    body = await (await discover(client)).json()
    detected = body["workergroups"][0]["detected"]
    assert detected["model"] == "org/override"
    assert detected["env"]["VLLM_MODEL"] == {"value": "org/override", "from": "workergroup"}
    assert_clean(str(body))


async def test_template_found_by_id(client, vast_api):
    group = vast_api.state["workergroups"][0]
    group["template_hash"], group["template_id"] = None, TEMPLATE["id"]
    body = await (await discover(client)).json()
    assert body["summary"]["model"] == "Qwen/Qwen3-8B"


async def test_template_not_visible(client, vast_api):
    vast_api.state["templates"] = []
    body = await (await discover(client)).json()
    assert body["workergroups"][0]["template_missing"] is True
    assert body["summary"]["family"] == "unknown"


async def test_endpoint_without_workergroups(client, vast_api):
    vast_api.state["workergroups"] = []
    body = await (await discover(client)).json()
    assert body["workergroups"] == [] and body["summary"]["routes"] == []
    assert "no workergroups" in body["summary"]["warnings"][0]


async def test_bad_requests(client, vast_api):
    for payload in ({}, {"id": "seven"}, None):
        resp = await client.post("/api/endpoint", json=payload, headers=AUTH)
        assert resp.status == 400
    assert (await client.post("/api/endpoint", json={"id": 7})).status == 401
    vast_api.state["mode"] = "bad-key"
    assert (await discover(client)).status == 401
    vast_api.state["mode"] = "ok"
    assert (await discover(client, 12345)).status == 502  # not this account's endpoint


async def test_a_failed_template_lookup_is_shown_on_its_group_and_scrubbed(client, vast_api, logs):
    vast_api.state["mode"] = "template-leak"  # the lookup fails with the key in its text
    resp = await discover(client)
    assert resp.status == 200  # the endpoint is still described
    [group] = (await resp.json())["workergroups"]
    assert group["template_error"] and not group["template_missing"]
    assert_clean(await resp.text(), logs.getvalue())
