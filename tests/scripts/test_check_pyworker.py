"""scripts/check_pyworker.py against a small pyworker tree built to match the serverless UI,
then changed. It runs a checkout's routes.py, so it is a maintainer tool, not part of vastai."""
import importlib.util
from pathlib import Path

from vastai.serverless.ui import discovery

_spec = importlib.util.spec_from_file_location(
    "check_pyworker", Path(__file__).resolve().parents[2] / "scripts" / "check_pyworker.py")
check_pyworker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_pyworker)

NAMES = ["COMPLETIONS", "CHAT", "CHAT_BATCH", "EMBEDDINGS", "RERANK", "SCORE", "SPEECH", "SPEECH_BATCH",
         "AUDIO_GENERATE", "TRANSCRIPTIONS", "TRANSLATIONS", "IMAGES", "IMAGE_EDITS", "VIDEO"]
ROUTES = dict(zip(NAMES, discovery.ROUTES))
UPLOADS = ("IMAGE_EDITS", "VIDEO", "TRANSCRIPTIONS", "TRANSLATIONS")


def tree(root, routes=ROUTES, model_vars=discovery.MODEL_VARS, inferred=discovery.INFERRED_BACKENDS,
         tokens='lambda data: data.get("max_tokens", 0)', backends=None, script=""):
    openai = root / "workers" / "openai"
    openai.mkdir(parents=True)
    (openai / "routes.py").write_text(
        "".join(f'{k} = "{v}"\n' for k, v in routes.items())
        + f"UPLOAD_ROUTES = ({', '.join(UPLOADS)},)\n")
    (openai / "benchmark.py").write_text(
        f"_MODEL_NAME_VARS = {tuple(model_vars)!r}\n"
        "BENCHMARKS = {" + "".join(f"routes.{k}: 1, " for k in routes) + "}\n"
        "DEFAULT_BENCHMARK_ROUTE = routes.COMPLETIONS\n")
    (openai / "core.py").write_text(
        "DEFAULT_ROUTES = (routes.COMPLETIONS, routes.CHAT)\n"
        'os.environ.get("OPENAI_ROUTES"); os.environ.get("BENCHMARK_ROUTE")\n'
        "def build_config():\n"
        f"    tokens = {tokens}\n"
        "    handlers = [route(routes.COMPLETIONS, workload_calculator=tokens),\n"
        "                route(routes.CHAT, workload_calculator=tokens),\n"
        "                route(routes.CHAT_BATCH, workload_calculator=_chat_batch_workload)]\n")
    (openai / "worker.py").write_text("from workers.openai import core\n")
    branches = "".join(f'    {"if" if i == 0 else "elif"} [ -n "${{{var}:-}}" ]; then\n        BACKEND={b}\n'
                       for i, (var, b) in enumerate(inferred))
    (root / "start_server.sh").write_text(f'if [ -z "${{BACKEND:-}}" ]; then\n{branches}    fi\nfi\n{script}')
    for name in backends or (discovery.OPENAI_BACKENDS | discovery.OTHER_BACKENDS) - {"openai"}:
        d = root / "workers" / name
        d.mkdir()
        uses = "from workers.openai import core" if name in discovery.OPENAI_BACKENDS else ""
        (d / "worker.py").write_text(uses + "\n")
    return root


def drifted(root) -> dict:
    return {what: detail for what, ok, detail in check_pyworker.checks(check_pyworker.Pyworker(root)) if not ok}


def test_a_matching_pyworker_passes(tmp_path):
    assert drifted(tree(tmp_path)) == {}
    assert check_pyworker.main([str(tmp_path)]) == 0


def test_a_new_route_is_reported(tmp_path):
    found = drifted(tree(tmp_path, routes={**ROUTES, "MUSIC": "/v1/music"}))
    assert "pyworker only: /v1/music" in found["routes (discovery.ROUTES)"]
    assert "routes (page ROUTES)" in found
    assert "a BENCHMARK_ROUTE must be benchmarkable (discovery checks against ROUTES)" in found


def test_a_renamed_or_reordered_model_variable_is_reported(tmp_path):
    found = drifted(tree(tmp_path, model_vars=("VLLM_MODEL", "MODEL_NAME", "SGLANG_MODEL", "LLAMA_MODEL")))
    assert set(found) == {"model variables, in order"}


def test_a_changed_backend_inference_is_reported(tmp_path):
    inferred = (("SGLANG_MODEL", "sglang"), ("VLLM_MODEL", "vllm"), ("LLAMA_MODEL", "llama"))
    assert set(drifted(tree(tmp_path, inferred=inferred))) == {"BACKEND inferred from *_MODEL, in order"}


def test_a_changed_workload_is_reported(tmp_path):
    found = drifted(tree(tmp_path, tokens='lambda data: data.get("max_completion_tokens", 0)'))
    assert set(found) == {"workload of /v1/completions is max_tokens (UI cost)",
                          "workload of /v1/chat/completions is max_tokens (UI cost)"}


def test_a_new_backend_is_reported(tmp_path):
    found = drifted(tree(tmp_path, backends=(discovery.OPENAI_BACKENDS | discovery.OTHER_BACKENDS | {"kokoro"}) - {"openai"}))
    assert found == {"other backends": "pyworker only: kokoro"}


def test_a_backend_start_server_still_accepts_counts_without_its_worker(tmp_path):
    """pyworker's start script still accepts BACKEND=comfyui, though its worker has gone."""
    others = discovery.OPENAI_BACKENDS | discovery.OTHER_BACKENDS
    script = '[ "$BACKEND" = "comfyui" ] && [ -z "$COMFY_MODEL" ] && exit 1\n'
    assert drifted(tree(tmp_path, backends=(others - {"openai", "comfyui"}), script=script)) == {}


def test_no_checkout(tmp_path, capsys):
    assert check_pyworker.main([str(tmp_path)]) == 2
