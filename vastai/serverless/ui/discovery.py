"""What an endpoint serves, worked out from its workergroups' template env.

Pure functions only: server.py fetches the workergroups and templates, this module reads them.
The rules mirror pyworker, so a change there must be copied here:

  backend   start_server.sh: BACKEND, else inferred from VLLM_MODEL / SGLANG_MODEL / LLAMA_MODEL.
            A BACKEND baked into the image (IMAGE_BACKENDS) is set before that script runs,
            so it comes after the template's BACKEND and before the inference.
  model     workers/openai/benchmark.py: the first of _MODEL_NAME_VARS that is set
  routes    workers/openai/core.py _served_routes: OPENAI_ROUTES, else completions + chat +
            BENCHMARK_ROUTE (default /v1/completions)
  comfyui   workers/comfyui-json/worker.py: one route, /generate/sync, taking a whole API-format
            workflow. Templates name their GUI-format workflows in PROVISIONING_COMFYUI_WORKFLOWS
            and sample inputs in PROVISIONING_DOWNLOADS (base-image's provisioner), often as
            `export` lines in onstart rather than in the env block.
"""
import re
import shlex

# workers/openai/routes.py
COMPLETIONS = "/v1/completions"
CHAT = "/v1/chat/completions"
ROUTES = (
    COMPLETIONS, CHAT, "/v1/chat/completions/batch", "/v1/embeddings", "/v1/rerank",
    "/v1/score", "/v1/audio/speech", "/v1/audio/speech/batch", "/v1/audio/generate",
    "/v1/audio/transcriptions", "/v1/audio/translations", "/v1/images/generations",
    "/v1/images/edits", "/v1/videos/sync",
)
DEFAULT_BENCHMARK_ROUTE = COMPLETIONS
COMFY_ROUTE = "/generate/sync"  # workers/comfyui-json/worker.py
ALL_ROUTES = (*ROUTES, COMFY_ROUTE)

OPENAI_BACKENDS = {"vllm", "sglang", "llama", "openai"}  # openai is an alias for vllm
OTHER_BACKENDS = {"comfyui", "comfyui-json", "wan", "ace", "tgi"}
MODEL_VARS = ("MODEL_NAME", "VLLM_MODEL", "SGLANG_MODEL", "LLAMA_MODEL")
INFERRED_BACKENDS = (("VLLM_MODEL", "vllm"), ("SGLANG_MODEL", "sglang"), ("LLAMA_MODEL", "llama"))
# vast-ai/base-image: the BACKEND each published image bakes with `ENV BACKEND=` (vllm-omni
# runs the vllm worker). The UI cannot read an image's env, so it is copied here.
IMAGE_BACKENDS = {"vastai/vllm": "vllm", "vastai/vllm-omni": "vllm", "vastai/sglang": "sglang",
                  "vastai/llama-cpp": "llama", "vastai/comfy": "comfyui-json"}
# The only env vars the page ever sees. Templates also carry tokens (HF_TOKEN etc.).
SHOWN_VARS = ("BACKEND", *MODEL_VARS, "COMFY_MODEL", "OPENAI_ROUTES", "BENCHMARK_ROUTE",
              "PROVISIONING_COMFYUI_WORKFLOWS", "PROVISIONING_DOWNLOADS")
# A credential's name ends a word in one of these (HF_TOKEN, AWS_SECRET_ACCESS_KEY, HFTOKEN),
# so TOKENIZER or PASSTHROUGH, which name model settings, are not taken for one.
SECRET_NAME = re.compile(r"(TOKEN|KEY|SECRET|PASS(WORD|WD)?|AUTH|CREDENTIALS?)(_|$)", re.I)
# Signed or tokened download URLs (CivitAI's ?token=, S3's X-Amz-Signature=) carry secrets in
# their query, and some put a user and password before the host; shown values keep the
# parameter names and the user, and lose the values and the password.
QUERY_VALUE = re.compile(r"([?&][^=&\s;|#]+=)[^&\s;|#]+")
URL_PASSWORD = re.compile(r"(\w+://[^/:@\s;|]+:)[^/@\s;|]+@")


def hide_url_secrets(text: str) -> str:
    return URL_PASSWORD.sub(r"\1[redacted]@", QUERY_VALUE.sub(r"\1[redacted]", text))


def _split(text: str) -> list:
    try:
        return shlex.split(text)
    except ValueError:  # unbalanced quotes: plain whitespace, stray quotes dropped
        return [t.strip("'\"") for t in text.split()]


def parse_docker_env(text) -> dict:
    """`-e K=V` / `--env K=V` / `-eK=V` / `--env=K=V` pairs from a docker args string.
    Later settings win, as they do in docker. `-e K` alone passes the host's value: skipped."""
    env = {}
    tokens = _split(text or "")
    i = 0
    while i < len(tokens):
        token, value = tokens[i], None
        if token in ("-e", "--env") and i + 1 < len(tokens):
            value, i = tokens[i + 1], i + 1
        elif token.startswith("--env="):
            value = token[len("--env="):]
        elif token.startswith("-e") and len(token) > 2 and "=" in token:
            value = token[2:]
        if value and "=" in value:
            name, _, val = value.partition("=")
            if name:
                env[name] = val
        i += 1
    return env


def launch_args_env(text) -> dict:
    """The env in a workergroup's launch_args: `--env '-e K=V ...' --image ...`."""
    env = {}
    tokens = _split(text or "")
    for i, token in enumerate(tokens):
        if token == "--env" and i + 1 < len(tokens):
            env.update(parse_docker_env(tokens[i + 1]))
        elif token.startswith("--env="):
            env.update(parse_docker_env(token[len("--env="):]))
    return env


def onstart_env(text) -> dict:
    """`export NAME=value` lines in a template's onstart script, which the provisioner reads
    like env. Only literal values: anything with a shell expansion is kept as written."""
    env = {}
    for line in str(text or "").splitlines():
        m = re.match(r"\s*export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if m:
            value = _split(m.group(2))
            env[m.group(1)] = value[0] if len(value) == 1 else m.group(2).strip().strip("'\"")
    return env


def comfy_files(env_value: str, kind: str) -> list:
    """Workflow names (PROVISIONING_COMFYUI_WORKFLOWS: url;url) or input file names
    (PROVISIONING_DOWNLOADS: url|dest;url|dest, keeping those under ComfyUI/input)."""
    names = []
    for item in str(env_value or "").split(";"):
        item = item.strip()
        if not item:
            continue
        if kind == "workflows":
            names.append(item.rsplit("/", 1)[-1].split("?")[0])
        else:
            url, _, dest = item.partition("|")
            if "/input/" in dest:
                names.append(dest.rsplit("/", 1)[-1])
    return names


def secret_values(env: dict) -> list:
    """Values of env vars whose names suggest a credential, for the scrubber."""
    return [v for k, v in env.items() if SECRET_NAME.search(k)]


def merge_env(template_env: dict, group_env: dict) -> dict:
    """{name: (value, source)}. The workergroup's launch_args are applied after the template.
    Assumption: the autoscaler merges them this way; it is not in this repo, so each value
    carries its source and the page shows it."""
    merged = {k: (v, "template") for k, v in template_env.items()}
    merged.update({k: (v, "workergroup") for k, v in group_env.items()})
    return merged


def image_repo(image) -> str:
    """vastai/vllm from docker.io/vastai/vllm:v0.30.0 and the like."""
    name = str(image or "").strip().split("@")[0]  # no digest
    for registry in ("docker.io/", "index.docker.io/"):
        name = name.removeprefix(registry)
    repo, _, tag = name.rpartition(":")
    return repo if repo and "/" not in tag else name  # a ":" before a "/" is a registry port


def detect(env: dict, image: str | None = None) -> dict:
    """Backend, model and served routes from a merged env ({name: (value, source)}) and the
    image the workers run."""
    value = lambda name: (env.get(name) or ("", ""))[0].strip()  # noqa: E731
    warnings = []

    backend, backend_from = value("BACKEND"), "BACKEND"
    if not backend and IMAGE_BACKENDS.get(image_repo(image)):
        backend, backend_from = IMAGE_BACKENDS[image_repo(image)], f"image {image_repo(image)}"
    if not backend:
        backend, backend_from = next(
            ((b, var) for var, b in INFERRED_BACKENDS if value(var)), ("", None))
    family = ("openai" if backend in OPENAI_BACKENDS else
              backend if backend in OTHER_BACKENDS else "unknown")
    if family == "unknown":
        warnings.append(f"Unrecognised backend {backend!r}." if backend else
                        "No BACKEND and no engine model var, so the backend is unknown.")

    model_var = next((v for v in MODEL_VARS if value(v)), None)
    if backend in ("comfyui", "comfyui-json"):
        model_var = "COMFY_MODEL" if value("COMFY_MODEL") else None
    model = value(model_var) if model_var else None
    if family == "openai" and not model:
        warnings.append("No model set: " + " / ".join(MODEL_VARS) + " are all empty.")

    routes, benchmark_route, unknown, comfy = [], None, [], None
    if family == "comfyui-json":
        routes = [COMFY_ROUTE]
        comfy = {"workflows": comfy_files(value("PROVISIONING_COMFYUI_WORKFLOWS"), "workflows"),
                 "inputs": comfy_files(value("PROVISIONING_DOWNLOADS"), "inputs")}
    if family == "openai":
        benchmark_route = value("BENCHMARK_ROUTE") or DEFAULT_BENCHMARK_ROUTE
        wanted = [r.strip() for r in value("OPENAI_ROUTES").split(",") if r.strip()]
        unknown = [r for r in wanted if r not in ROUTES]
        if unknown:
            warnings.append("OPENAI_ROUTES names unknown routes: " + ", ".join(unknown))
        if benchmark_route not in ROUTES:
            warnings.append(f"BENCHMARK_ROUTE={benchmark_route!r} is not a route; "
                            "the worker will refuse to start.")
        wanted = set(wanted) or {COMPLETIONS, CHAT, benchmark_route}
        routes = [r for r in ROUTES if r in wanted]
        if benchmark_route in ROUTES and benchmark_route not in routes:
            warnings.append(f"OPENAI_ROUTES leaves out BENCHMARK_ROUTE={benchmark_route}; "
                            "the worker will refuse to start.")

    return {
        "backend": backend or None, "backend_from": backend_from, "family": family,
        "model": model, "model_var": model_var, "routes": routes,
        "benchmark_route": benchmark_route, "unknown_routes": unknown, "warnings": warnings,
        "comfy": comfy,
        "env": {k: {"value": hide_url_secrets(env[k][0]), "from": env[k][1]}
                for k in SHOWN_VARS if k in env},
    }


def summarise(groups: list) -> dict:
    """One view across workergroups. A request can land on any group's worker, so only the
    routes every group serves are safe, and disagreement is called out."""
    found = [g["detected"] for g in groups if g.get("detected")]
    if not found:
        return {"family": None, "backend": None, "model": None, "routes": [], "warnings":
                ["This endpoint has no workergroups, so there is no template to read."]}
    first, warnings = found[0], []
    for field in ("family", "backend", "model"):
        if len({d[field] for d in found}) > 1:
            warnings.append(f"Workergroups disagree on {field}: "
                            + ", ".join(sorted(str(d[field]) for d in found)))
    shared = set.intersection(*(set(d["routes"]) for d in found))
    if any(set(d["routes"]) != shared for d in found):
        warnings.append("Workergroups serve different routes; only the shared ones are listed.")
    comfy = None
    if first.get("comfy") is not None:  # every group's workflows and inputs, in order, once each
        comfy = {k: list(dict.fromkeys(x for d in found for x in (d.get("comfy") or {}).get(k, [])))
                 for k in ("workflows", "inputs")}
    return {"family": first["family"], "backend": first["backend"], "model": first["model"],
            "routes": [r for r in ALL_ROUTES if r in shared], "warnings": warnings, "comfy": comfy}
