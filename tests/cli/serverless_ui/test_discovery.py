"""The pyworker rules, read from template env."""
from vastai.serverless.ui.discovery import (CHAT, COMPLETIONS, detect, launch_args_env, merge_env, parse_docker_env,
                       secret_values, summarise)

EMBED = "/v1/embeddings"
SPEECH = "/v1/audio/speech"


def env(**values):
    return merge_env(values, {})


def test_parse_docker_env_forms():
    text = ("-p 8000:8000 -e A=1 --env B=two -eC=3 --env=D=4 -e 'E=has spaces' "
            '-e "F=x=y" -e HOST_PASSTHROUGH -v /a:/b -e A=override')
    assert parse_docker_env(text) == {"A": "override", "B": "two", "C": "3", "D": "4",
                                      "E": "has spaces", "F": "x=y"}


def test_parse_docker_env_survives_bad_quoting_and_nothing():
    assert parse_docker_env("-e A=1 -e 'B=unterminated") == {"A": "1", "B": "unterminated"}
    assert parse_docker_env(None) == {} and parse_docker_env("") == {}


def test_launch_args_env():
    text = ("--image vastai/vllm --env '-e VLLM_MODEL=org/model -e IS_DEPLOYMENT=true' "
            "--onstart-cmd 'echo -e X=1' --disk 64")
    assert launch_args_env(text) == {"VLLM_MODEL": "org/model", "IS_DEPLOYMENT": "true"}


def test_workergroup_env_overrides_template_and_says_so():
    merged = merge_env({"VLLM_MODEL": "a", "BACKEND": "vllm"}, {"VLLM_MODEL": "b"})
    assert merged == {"VLLM_MODEL": ("b", "workergroup"), "BACKEND": ("vllm", "template")}


def test_defaults_serve_completions_chat_and_the_benchmark_route():
    d = detect(env(BACKEND="vllm", VLLM_MODEL="Qwen/Qwen3-8B"))
    assert (d["family"], d["model"], d["model_var"]) == ("openai", "Qwen/Qwen3-8B", "VLLM_MODEL")
    assert d["routes"] == [COMPLETIONS, CHAT]
    assert d["benchmark_route"] == COMPLETIONS and d["warnings"] == []

    d = detect(env(BACKEND="vllm", VLLM_MODEL="m", BENCHMARK_ROUTE=EMBED))
    assert d["routes"] == [COMPLETIONS, CHAT, EMBED]


def test_openai_routes_replace_the_defaults():
    d = detect(env(BACKEND="sglang", SGLANG_MODEL="m",
                   OPENAI_ROUTES=f" {SPEECH} , {EMBED},", BENCHMARK_ROUTE=SPEECH))
    assert d["routes"] == [EMBED, SPEECH] and d["warnings"] == []


def test_worker_startup_failures_are_warned():
    d = detect(env(BACKEND="vllm", VLLM_MODEL="m", OPENAI_ROUTES=EMBED))
    assert any("refuse to start" in w for w in d["warnings"])  # benchmark route left out
    d = detect(env(BACKEND="vllm", VLLM_MODEL="m", BENCHMARK_ROUTE="/v1/nope"))
    assert any("not a route" in w for w in d["warnings"])
    d = detect(env(BACKEND="vllm", VLLM_MODEL="m", OPENAI_ROUTES=f"{COMPLETIONS},/v1/typo"))
    assert d["unknown_routes"] == ["/v1/typo"] and d["routes"] == [COMPLETIONS]


def test_backend_inferred_like_start_server_and_model_order_like_benchmark():
    d = detect(env(LLAMA_MODEL="llama-3.gguf"))
    assert (d["backend"], d["backend_from"], d["family"]) == ("llama", "LLAMA_MODEL", "openai")
    d = detect(env(BACKEND="openai", MODEL_NAME="served-name", VLLM_MODEL="org/weights"))
    assert (d["family"], d["model"], d["model_var"]) == ("openai", "served-name", "MODEL_NAME")


def test_non_openai_backends():
    d = detect(env(BACKEND="comfyui-json", COMFY_MODEL="flux"))
    assert (d["family"], d["model"], d["routes"]) == ("comfyui-json", "flux", ["/generate/sync"])
    d = detect(env())
    assert d["family"] == "unknown" and d["warnings"]


def test_only_known_vars_are_shown():
    d = detect(env(BACKEND="vllm", VLLM_MODEL="m", HF_TOKEN="hf_secret", OTHER="x"))
    assert set(d["env"]) == {"BACKEND", "VLLM_MODEL"}
    assert d["env"]["VLLM_MODEL"] == {"value": "m", "from": "template"}


def test_credentials_are_told_from_model_settings_by_name():
    found = secret_values({"HF_TOKEN": "a", "HFTOKEN": "b", "AWS_SECRET_ACCESS_KEY": "c",
                           "DOCKER_PASSWORD": "d", "TOKENIZER": "Qwen/Qwen3-8B",
                           "VLLM_TOKENIZER": "Qwen/Qwen3-8B", "PASSTHROUGH": "x", "MODEL_NAME": "m"})
    assert found == ["a", "b", "c", "d"]


def test_download_urls_are_shown_without_query_values_or_passwords():
    url = ("https://civitai.com/api/download/models/1?type=Model&token=abc123|/w/ComfyUI/input/x.png;"
           "https://bob:s3cret@files.example:8443/y.png|/w/ComfyUI/input/y.png")
    d = detect(env(BACKEND="comfyui-json", PROVISIONING_DOWNLOADS=url))
    shown = d["env"]["PROVISIONING_DOWNLOADS"]["value"]
    assert "abc123" not in shown and "token=[redacted]" in shown and "|/w/ComfyUI/input/x.png;" in shown
    assert "s3cret" not in shown and "https://bob:[redacted]@files.example:8443/y.png" in shown
    assert d["comfy"]["inputs"] == ["x.png", "y.png"]


def test_summary_across_workergroups():
    a = {"detected": detect(env(BACKEND="vllm", VLLM_MODEL="m", OPENAI_ROUTES=f"{COMPLETIONS},{EMBED}"))}
    b = {"detected": detect(env(BACKEND="vllm", VLLM_MODEL="m"))}
    s = summarise([a, b])
    assert s["routes"] == [COMPLETIONS] and s["model"] == "m"
    assert any("different routes" in w for w in s["warnings"])
    c = {"detected": detect(env(BACKEND="vllm", VLLM_MODEL="other"))}
    assert any("disagree on model" in w for w in summarise([b, c])["warnings"])
    assert summarise([])["routes"] == [] and summarise([])["warnings"]


def test_backend_baked_into_the_image():
    # MODEL_NAME only, as the coverage templates have: the image's ENV BACKEND decides.
    d = detect(env(MODEL_NAME="openai/whisper-large-v3"), "vastai/vllm")
    assert (d["backend"], d["backend_from"], d["family"]) == ("vllm", "image vastai/vllm", "openai")
    assert d["model"] == "openai/whisper-large-v3" and d["warnings"] == []
    assert detect(env(MODEL_NAME="m"), "docker.io/vastai/vllm-omni:v0.30.0-cuda-13.0")["backend"] == "vllm"
    assert detect(env(), "vastai/comfy@sha256:abc")["family"] == "comfyui-json"  # published as vastai/comfy
    # The template's BACKEND wins over the image's, and the image's over *_MODEL inference.
    assert detect(env(BACKEND="sglang", MODEL_NAME="m"), "vastai/vllm")["backend"] == "sglang"
    assert detect(env(SGLANG_MODEL="m"), "vastai/vllm")["backend"] == "vllm"
    assert detect(env(MODEL_NAME="m"), "someone/else")["family"] == "unknown"


def test_image_names():
    from vastai.serverless.ui.discovery import image_repo
    assert image_repo("vastai/vllm:v1") == "vastai/vllm"
    assert image_repo("registry.example:5000/vastai/vllm:v1") == "registry.example:5000/vastai/vllm"
    assert image_repo("registry.example:5000/vastai/vllm") == "registry.example:5000/vastai/vllm"
    assert image_repo(None) == ""



def test_comfyui_workflows_and_inputs_from_onstart_exports():
    from vastai.serverless.ui.discovery import onstart_env
    onstart = ('export PROVISIONING_COMFYUI_WORKFLOWS="https://x/templates/image_z_image.json;'
               'https://x/templates/image_z_image_turbo.json"\n'
               'export PROVISIONING_DOWNLOADS="https://x/input/jet.png|${WORKSPACE}/ComfyUI/input/jet.png;'
               'https://x/m.safetensors|${WORKSPACE}/ComfyUI/models/m.safetensors"\n'
               'export SERVERLESS=true\nentrypoint.sh &')
    found = onstart_env(onstart)
    assert found["SERVERLESS"] == "true" and "image_z_image.json" in found["PROVISIONING_COMFYUI_WORKFLOWS"]
    d = detect(merge_env(found, {}), "vastai/comfy:v0.43.0-cuda-13.2-py312")
    assert d["family"] == "comfyui-json" and d["routes"] == ["/generate/sync"]
    assert d["comfy"] == {"workflows": ["image_z_image.json", "image_z_image_turbo.json"], "inputs": ["jet.png"]}
    assert summarise([{"detected": d}])["comfy"] == d["comfy"]
