"""Checks the serverless UI's copy of pyworker's rules against a pyworker checkout.

    python scripts/check_pyworker.py [path/to/pyworker]     # default: $PYWORKER, else ../pyworker

The UI (vastai/serverless/ui) reads endpoints the way pyworker will serve them (discovery.py)
and offers the routes it serves (index.html). Those rules are copied, not imported, so they can drift.
This reads pyworker's source without importing it (its imports need the worker's own
dependencies): routes.py, which has no imports by design, and literals parsed from
benchmark.py, core.py and start_server.sh. Exit status 1 if anything differs.

routes.py is run, not just read, so point this only at a checkout you trust.
"""
import ast
import os
import re
import sys
from pathlib import Path

from vastai.serverless.ui import discovery

HERE = Path(__file__).resolve().parent
UI = HERE.parent / "vastai" / "serverless" / "ui"


class Pyworker:
    def __init__(self, root: Path):
        self.root = root
        self.openai = root / "workers" / "openai"
        self.routes: dict = {}
        exec(compile((self.openai / "routes.py").read_text(encoding="utf-8"), "routes.py", "exec"), self.routes)

    def route(self, node) -> str:
        """routes.X, or a string literal, as a path."""
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "routes":
            return self.routes[node.attr]
        return ast.literal_eval(node)

    def assigned(self, file: str, name: str):
        """The value node first assigned to a name, at any level."""
        tree = ast.parse((self.openai / file).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            targets = node.targets if isinstance(node, ast.Assign) else [getattr(node, "target", None)]
            if any(isinstance(t, ast.Name) and t.id == name for t in targets):
                return node.value
        raise LookupError(f"{name} not found in {file}")

    def all_routes(self) -> set:
        return {v for k, v in self.routes.items() if k.isupper() and isinstance(v, str) and v.startswith("/v1/")}

    def upload_routes(self) -> set:
        return set(self.routes["UPLOAD_ROUTES"])

    def model_vars(self) -> tuple:
        return ast.literal_eval(self.assigned("benchmark.py", "_MODEL_NAME_VARS"))

    def default_benchmark_route(self) -> str:
        return self.route(self.assigned("benchmark.py", "DEFAULT_BENCHMARK_ROUTE"))

    def benchmarked_routes(self) -> set:
        return {self.route(k) for k in self.assigned("benchmark.py", "BENCHMARKS").keys}

    def default_routes(self) -> set:
        return {self.route(e) for e in self.assigned("core.py", "DEFAULT_ROUTES").elts}

    def workload_calculators(self) -> dict:
        """{route: the workload_calculator's source} from the handler table in core.py."""
        source = (self.openai / "core.py").read_text(encoding="utf-8")
        found = {}
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "route" and node.args:
                for kw in node.keywords:
                    if kw.arg == "workload_calculator":
                        found[self.route(node.args[0])] = ast.get_source_segment(source, kw.value)
        return found

    def tokens_lambda(self) -> str:
        """The `tokens = lambda data: ...` the handler table passes as workload_calculator."""
        source = (self.openai / "core.py").read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Lambda)
                    and any(isinstance(t, ast.Name) and t.id == "tokens" for t in node.targets)):
                return ast.get_source_segment(source, node.value)
        return "(no tokens lambda in core.py)"

    def env_read(self, name: str) -> bool:
        return f'"{name}"' in (self.openai / "core.py").read_text(encoding="utf-8")

    def inferred_backends(self) -> tuple:
        """start_server.sh: the BACKEND it infers from each *_MODEL var, in order."""
        text = (self.root / "start_server.sh").read_text(encoding="utf-8")
        block = text[text.index('if [ -z "${BACKEND:-}" ]'):]
        return tuple(re.findall(r'\$\{(\w+_MODEL):-\}" \]; then\s+BACKEND=(\w+)', block))

    def backends(self) -> tuple:
        """(openai backends, other backends): workers/<name> with a worker.py or server.py,
        split by whether they use workers.openai; and as other backends, any BACKEND value
        start_server.sh still checks for (a name it accepts, such as comfyui, though its worker
        has gone)."""
        openai, other = set(), set()
        for d in sorted((self.root / "workers").iterdir()):
            files = [d / f for f in ("worker.py", "server.py") if (d / f).exists()]
            if not files:
                continue
            uses = any("workers.openai" in f.read_text(encoding="utf-8") for f in files)
            (openai if uses or d.name == "openai" else other).add(d.name)
        script = (self.root / "start_server.sh").read_text(encoding="utf-8")
        other |= set(re.findall(r'"\$BACKEND" = "([\w-]+)"', script)) - openai
        return openai, other


def page_list(name: str) -> set:
    """A route list literal from index.html: `const NAME = [...]` or `new Set([...])`."""
    text = (UI / "index.html").read_text(encoding="utf-8")
    m = re.search(rf"const {name} = (?:new Set\()?\[(.*?)\]", text, re.S)
    if not m:
        raise LookupError(f"{name} not found in index.html")
    return set(re.findall(r'"(/v1/[^"]+)"', m.group(1)))


def checks(pw: Pyworker):
    """(what, ok, detail) for each rule the UI copies."""
    def same(what, ours, theirs):
        ours, theirs = set(ours), set(theirs)
        detail = "; ".join(filter(None, [
            ours - theirs and f"UI only: {', '.join(sorted(ours - theirs))}",
            theirs - ours and f"pyworker only: {', '.join(sorted(theirs - ours))}"]))
        return what, ours == theirs, detail

    routes = pw.all_routes()
    yield same("routes (discovery.ROUTES)", discovery.ROUTES, routes)
    yield same("routes (page ROUTES)", page_list("ROUTES"), routes)
    yield same("upload routes (page UPLOADS)", page_list("UPLOADS"), pw.upload_routes())
    yield same("a BENCHMARK_ROUTE must be benchmarkable (discovery checks against ROUTES)",
               discovery.ROUTES, pw.benchmarked_routes())
    theirs = pw.default_benchmark_route()
    yield ("default BENCHMARK_ROUTE", discovery.DEFAULT_BENCHMARK_ROUTE == theirs,
           f"UI {discovery.DEFAULT_BENCHMARK_ROUTE}, pyworker {theirs}")
    yield same("routes served when OPENAI_ROUTES is unset", {discovery.COMPLETIONS, discovery.CHAT},
               pw.default_routes())
    yield ("model variables, in order", discovery.MODEL_VARS == pw.model_vars(),
           f"UI {discovery.MODEL_VARS}, pyworker {pw.model_vars()}")
    yield ("BACKEND inferred from *_MODEL, in order", discovery.INFERRED_BACKENDS == pw.inferred_backends(),
           f"UI {discovery.INFERRED_BACKENDS}, pyworker {pw.inferred_backends()}")
    openai, other = pw.backends()
    yield same("OpenAI-compatible backends", discovery.OPENAI_BACKENDS, openai)
    yield same("other backends", discovery.OTHER_BACKENDS, other)
    for var in ("OPENAI_ROUTES", "BENCHMARK_ROUTE"):
        yield f"core.py reads {var}", pw.env_read(var), ""
    # The UI's routing cost (server.Call.cost) is pyworker's workload for these routes.
    calc = pw.workload_calculators()
    tokens = pw.tokens_lambda()
    for route in (discovery.COMPLETIONS, discovery.CHAT):
        yield (f"workload of {route} is max_tokens (UI cost)",
               calc.get(route) == "tokens" and '"max_tokens"' in tokens,
               f"calculator {calc.get(route)!r}: {tokens}")
    yield ("workload of chat batch is max_tokens per conversation (UI cost)",
           calc.get("/v1/chat/completions/batch") == "_chat_batch_workload", repr(calc.get("/v1/chat/completions/batch")))


def main(argv=sys.argv[1:]) -> int:
    root = Path(argv[0] if argv else os.environ.get("PYWORKER", HERE.parent.parent / "pyworker")).expanduser()
    if not (root / "workers" / "openai" / "routes.py").exists():
        print(f"No pyworker checkout at {root}", file=sys.stderr)
        return 2
    results = list(checks(Pyworker(root)))
    for what, ok, detail in results:
        print(f"{'ok   ' if ok else 'DRIFT'}  {what}" + (f"\n         {detail}" if detail and not ok else ""))
    drifted = sum(not ok for _, ok, _ in results)
    print(f"\n{len(results) - drifted}/{len(results)} match pyworker at {root}")
    return 1 if drifted else 0


if __name__ == "__main__":
    sys.exit(main())
