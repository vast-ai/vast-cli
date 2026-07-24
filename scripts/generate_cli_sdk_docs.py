#!/usr/bin/env python3
"""
Auto-generate CLI and SDK reference MDX pages for vast-ai/docs.

Mirrors the API docs auto-generation pipeline in the vast (backend) repo:
the source of truth is the installed vastai package, and the generator
walks the argparse subparsers and the VastAI class to produce one MDX
file per command/method in the format expected by the Mintlify docs site.

Output layout:

    <output-dir>/
        cli/reference/<command-name>.mdx
        sdk/python/reference/<method-name>.mdx

Usage:

    # Generate to ./generated-docs/ (default)
    python scripts/generate_cli_sdk_docs.py

    # Generate into a clone of vast-ai/docs for diffing/cutover
    python scripts/generate_cli_sdk_docs.py --output-dir /path/to/docs

    # JSON manifest of what was generated (for CI)
    python scripts/generate_cli_sdk_docs.py --manifest manifest.json
"""

from __future__ import annotations

import argparse
import ast
import inspect
import json
import re
import sys
import textwrap
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# Global options added by vastai/cli/main.py to the top-level parser.  We
# render these once in a static "Global Options" section per CLI page rather
# than repeating them inside every command's Options list.
GLOBAL_CLI_OPTIONS = {
    "url", "retry", "explain", "raw", "full", "curl", "api_key",
    "version", "no_color", "help",
}

# Commands/methods we never publish to public docs, regardless of scope.
# These are CLI/SDK surface that exists in code but isn't part of the
# publicly-supported product. Public stance is that vast.ai does not offer
# network volumes — the network-volume / network-disk commands were written
# for a single customer and aren't verified to work for general users.
#
# Names are doc_names (kebab-case, no extension). The same set applies to
# both CLI and SDK because the kebab-case is identical across surfaces.
EXCLUDED_NAMES = {
    "add-network-disk",
    "create-network-volume",
    "list-network-volume",
    "search-network-volumes",
    "show-network-disks",
    "unlist-network-volume",
}

# Hardcoded markdown block to render at the bottom of every CLI page so the
# table of universal flags stays consistent.  Matches the format guthrie-vast
# established in docs PR #99.
GLOBAL_OPTIONS_MD = """## Global Options

The following options are available for all commands:

| Option | Description |
| --- | --- |
| `--url URL` | Server REST API URL |
| `--retry N` | Retry limit |
| `--raw` | Output machine-readable JSON |
| `--explain` | Verbose explanation of API calls |
| `--api-key KEY` | API key (defaults to `~/.config/vastai/vast_api_key`) |
"""


def _escape_mdx_prose(text: str) -> str:
    """Escape ``<`` and ``>`` outside inline backticks so MDX doesn't parse
    placeholder text like ``<PHONE_NUMBER>`` or ``<name of a field>`` as JSX.

    Mintlify renders ``&lt;`` / ``&gt;`` identically to ``<`` / ``>`` in prose,
    so this is visually transparent. Text inside inline backticks is left
    alone so it stays literal in monospace.
    """
    if not text or ("<" not in text and ">" not in text):
        return text
    out: list[str] = []
    in_code = False
    for chunk in re.split(r"(`[^`\n]*`)", text):
        if chunk.startswith("`") and chunk.endswith("`") and len(chunk) >= 2:
            out.append(chunk)
        else:
            out.append(chunk.replace("<", "&lt;").replace(">", "&gt;"))
    return "".join(out)


# ---------------------------------------------------------------------------
# CLI introspection
# ---------------------------------------------------------------------------

@dataclass
class CliArg:
    name: str               # original arg name, e.g. "--onstart-cmd" or "id"
    dest: str               # argparse dest, e.g. "onstart_cmd"
    help: str
    type_label: str         # rendered type for MDX, e.g. "string", "boolean"
    default: Any
    required: bool
    is_positional: bool
    choices: Optional[list] = None


@dataclass
class CliCommand:
    name: str               # space-form, e.g. "create instance"
    doc_name: str           # filename stem, e.g. "create-instance"
    summary: str            # one-line help, used as title-level description
    usage: str              # cleaned usage line
    description: str        # prose body from epilog
    examples: str           # block from epilog after "Examples:" / "Example:"
    arguments: list[CliArg] = field(default_factory=list)
    options: list[CliArg] = field(default_factory=list)
    func_name: str = ""     # Python name of the handler — used for scope lookup


def load_cli_parser():
    """Import the CLI and return its top-level apwrap parser fully wired."""
    # register_all_commands() imports every enabled command module, and the
    # import itself triggers @parser.command decorator registration. Reusing
    # the CLI's canonical registration helper (rather than a local copy of the
    # import list) keeps the generator in lockstep with the real command set,
    # so newly added command modules are documented automatically with no
    # drift. main() in vastai/cli/main.py performs the same imports at runtime.
    from vastai.cli.commands import register_all_commands
    from vastai.cli.main import parser
    register_all_commands(parser)
    return parser


def _action_type_label(action: argparse.Action) -> str:
    """Map an argparse Action back to the type label the docs use."""
    if isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
        return "boolean"
    t = action.type
    if t is int:
        return "integer"
    if t is float:
        return "number"
    if t is str or t is None:
        return "string"
    name = getattr(t, "__name__", str(t))
    return name


def _normalize_dest(action: argparse.Action) -> str:
    return action.dest


def extract_command(subparser: argparse.ArgumentParser, command_name: str,
                    func) -> CliCommand:
    """Pull all the metadata we need from one subparser into a CliCommand."""
    summary = (getattr(func, "mysignature_help", None) or "").strip()

    usage_line = subparser.format_usage().strip()
    # argparse prints "usage: vastai create instance ID [OPTIONS] ..."
    usage_line = re.sub(r"^usage:\s*", "", usage_line, flags=re.IGNORECASE)
    # argparse may wrap long usage across lines — collapse runs of whitespace
    usage_line = re.sub(r"\s+", " ", usage_line).strip()

    description, examples = _split_epilog(subparser.epilog or "")

    arguments: list[CliArg] = []
    options: list[CliArg] = []

    for a in subparser._actions:
        if isinstance(a, (argparse._HelpAction, argparse._VersionAction)):
            continue
        if a.help == argparse.SUPPRESS:
            continue
        # Skip subparsers action itself (the "command" placeholder)
        if isinstance(a, argparse._SubParsersAction):
            continue
        if a.dest in GLOBAL_CLI_OPTIONS:
            continue

        is_positional = not bool(a.option_strings)
        # For positionals, use dest as the displayed name; for flags, prefer
        # the long form (longest option string).
        if is_positional:
            name = a.dest
        else:
            name = max(a.option_strings, key=len)

        carg = CliArg(
            name=name,
            dest=a.dest,
            help=(a.help or "").strip(),
            type_label=_action_type_label(a),
            default=a.default,
            required=bool(a.required) if not is_positional else True,
            is_positional=is_positional,
            choices=list(a.choices) if a.choices else None,
        )
        if is_positional:
            arguments.append(carg)
        else:
            options.append(carg)

    return CliCommand(
        name=command_name,
        doc_name=command_name.replace(" ", "-"),
        summary=summary,
        usage=usage_line,
        description=description,
        examples=examples,
        arguments=arguments,
        options=options,
        func_name=getattr(func, "__name__", ""),
    )


def _split_epilog(epilog: str) -> tuple[str, str]:
    """Split an argparse epilog into (description prose, examples block).

    The CLI's epilog convention (see vastai/cli/commands/instances.py) is:

        ____________  <- horizontal rule of underscores
        <prose ...>

        Examples:

        # comment
        vastai ...

        ____________

    We strip the rule lines, then take everything before the first
    "Examples:" / "Example:" header as the description and everything after
    as the examples block.
    """
    if not epilog:
        return "", ""

    lines = epilog.splitlines()
    # Drop leading/trailing pure-underscore separator lines and blanks
    def is_rule(ln: str) -> bool:
        s = ln.strip()
        return bool(s) and set(s) == {"_"}

    while lines and (is_rule(lines[0]) or not lines[0].strip()):
        lines.pop(0)
    while lines and (is_rule(lines[-1]) or not lines[-1].strip()):
        lines.pop()

    # Find Examples: header
    desc_lines: list[str] = []
    example_lines: list[str] = []
    found = False
    for ln in lines:
        if not found and re.match(r"^\s*examples?:\s*$", ln, re.IGNORECASE):
            found = True
            continue
        if found:
            example_lines.append(ln)
        else:
            desc_lines.append(ln)

    description = "\n".join(desc_lines).strip()
    examples = "\n".join(example_lines).strip()
    return description, examples


# ---------------------------------------------------------------------------
# CLI MDX rendering
# ---------------------------------------------------------------------------

def render_cli_mdx(cmd: CliCommand) -> str:
    title = f"vastai {cmd.name}"
    sidebar = cmd.name

    out: list[str] = []
    out.append("---")
    out.append(f'title: "{title}"')
    out.append(f'sidebarTitle: "{sidebar}"')
    out.append("---")
    out.append("")
    if cmd.summary:
        out.append(_escape_mdx_prose(cmd.summary))
        out.append("")

    out.append("## Usage")
    out.append("")
    out.append("```bash")
    out.append(cmd.usage if cmd.usage else f"vastai {cmd.name}")
    out.append("```")
    out.append("")

    if cmd.arguments:
        out.append("## Arguments")
        out.append("")
        for a in cmd.arguments:
            out.append(_render_param_field(a, is_arg=True))
            out.append("")

    if cmd.options:
        out.append("## Options")
        out.append("")
        for a in cmd.options:
            out.append(_render_param_field(a, is_arg=False))
            out.append("")

    if cmd.description:
        out.append("## Description")
        out.append("")
        out.append(_escape_mdx_prose(cmd.description))
        out.append("")

    if cmd.examples:
        out.append("## Examples")
        out.append("")
        out.append("```bash")
        out.append(cmd.examples)
        out.append("```")
        out.append("")

    out.append(GLOBAL_OPTIONS_MD)

    return "\n".join(out).rstrip() + "\n"


def _render_param_field(a: CliArg, is_arg: bool) -> str:
    attrs = [f'path="{a.name}"', f'type="{a.type_label}"']
    if a.required and is_arg:
        attrs.append("required")
    if a.default not in (None, False, [], "", argparse.SUPPRESS):
        attrs.append(f'default="{a.default}"')
    if a.choices:
        choices_str = ", ".join(str(c) for c in a.choices)
        # Mintlify ParamField doesn't support choices natively; embed in help
        # text instead via the body.
        body_lines = []
        if a.help:
            body_lines.append(a.help)
        body_lines.append(f"Allowed values: {choices_str}")
        body = "\n  ".join(body_lines)
    else:
        body = a.help or ""

    body = _escape_mdx_prose(body)
    open_tag = f"<ParamField {' '.join(attrs)}>"
    return f"{open_tag}\n  {body}\n</ParamField>"


# ---------------------------------------------------------------------------
# SDK introspection + rendering
# ---------------------------------------------------------------------------

@dataclass
class SdkParam:
    name: str
    type_label: str
    default_repr: Optional[str]
    required: bool
    help: str = ""


@dataclass
class SdkMethod:
    name: str
    doc_name: str
    summary: str
    signature_str: str
    params: list[SdkParam]
    returns_label: str
    has_kwargs: bool
    cli_doc_name: Optional[str] = None  # matched CLI command, if any


def load_sdk_class():
    try:
        from vastai.sdk import VastAI
    except ImportError:
        from vastai_sdk import VastAI  # type: ignore
    return VastAI


def extract_sdk_methods(cli_commands: dict[str, CliCommand]) -> list[SdkMethod]:
    VastAI = load_sdk_class()
    methods: list[SdkMethod] = []

    for name, func in inspect.getmembers(VastAI, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue

        sig = inspect.signature(func)
        params: list[SdkParam] = []
        has_kwargs = False
        for p in sig.parameters.values():
            if p.name == "self":
                continue
            if p.kind == inspect.Parameter.VAR_KEYWORD:
                has_kwargs = True
                continue
            if p.kind == inspect.Parameter.VAR_POSITIONAL:
                continue
            params.append(SdkParam(
                name=p.name,
                type_label=_annotation_label(p.annotation),
                default_repr=(
                    None if p.default is inspect.Parameter.empty
                    else repr(p.default)
                ),
                required=(p.default is inspect.Parameter.empty),
            ))

        # Cross-reference CLI command to enrich **kwargs methods
        doc_name = name.replace("_", "-")
        cli_doc_name = doc_name if doc_name in cli_commands else None
        if has_kwargs and cli_doc_name:
            cli_cmd = cli_commands[cli_doc_name]
            existing = {p.name for p in params}
            for opt in cli_cmd.options:
                kw = opt.dest
                if kw in existing or kw in GLOBAL_CLI_OPTIONS:
                    continue
                # CLI-derived kwargs are always optional in the SDK (they
                # flow through **kwargs).  Wrap non-bool types in Optional
                # and surface the CLI default — falling back to None.
                base_t = _cli_type_to_sdk(opt.type_label)
                if base_t == "bool":
                    type_label = "bool"
                    default_repr = repr(bool(opt.default)) if opt.default is not None else "False"
                else:
                    type_label = f"Optional[{base_t}]"
                    default_repr = (
                        repr(opt.default)
                        if opt.default not in (None, argparse.SUPPRESS)
                        else "None"
                    )
                params.append(SdkParam(
                    name=kw,
                    type_label=type_label,
                    default_repr=default_repr,
                    required=False,
                    help=opt.help,
                ))

        # Pull docstring help into params we don't have help for
        doc = inspect.getdoc(func) or ""
        summary = doc.splitlines()[0].strip() if doc else ""

        # If the method had no `help` text (came from raw signature) pull
        # what we can from the matching CLI option list.
        if cli_doc_name:
            cli_cmd = cli_commands[cli_doc_name]
            cli_help_by_dest = {o.dest: o.help for o in cli_cmd.options}
            cli_help_by_dest.update({a.dest: a.help for a in cli_cmd.arguments})
            for sp in params:
                if not sp.help and sp.name in cli_help_by_dest:
                    sp.help = cli_help_by_dest[sp.name]

        ret = sig.return_annotation
        ret_label = _annotation_label(ret) if ret is not inspect.Parameter.empty else "Any"

        methods.append(SdkMethod(
            name=name,
            doc_name=doc_name,
            summary=summary,
            signature_str=_render_signature(name, params, ret_label),
            params=params,
            returns_label=ret_label,
            has_kwargs=has_kwargs,
            cli_doc_name=cli_doc_name,
        ))

    return methods


def _annotation_label(ann) -> str:
    if ann is inspect.Parameter.empty or ann is None:
        return "Any"
    if isinstance(ann, str):
        return ann
    # typing types stringify well; fall back to __name__
    name = getattr(ann, "__name__", None)
    if name:
        return name
    return str(ann).replace("typing.", "")


def _cli_type_to_sdk(t: str) -> str:
    return {
        "boolean": "bool",
        "integer": "int",
        "number": "float",
        "string": "str",
    }.get(t, t)


def _render_signature(name: str, params: list[SdkParam],
                      ret_label: str) -> str:
    """Render a multi-line Python signature for the docs page.

    For methods with **kwargs we expand the merged param list (CLI flags
    folded in) so the signature reflects the full effective surface.
    """
    suffix = f" -> {ret_label}" if ret_label and ret_label != "Any" else ""
    if not params:
        return f"VastAI.{name}(){suffix}"
    parts = []
    for p in params:
        annot = p.type_label
        if p.default_repr is None:
            parts.append(f"    {p.name}: {annot}")
        else:
            parts.append(f"    {p.name}: {annot} = {p.default_repr}")
    body = ",\n".join(parts)
    return f"VastAI.{name}(\n{body}\n){suffix}"


def render_sdk_mdx(method: SdkMethod) -> str:
    title = f"VastAI.{method.name}"
    sidebar = method.name

    out: list[str] = []
    out.append("---")
    out.append(f'title: "{title}"')
    out.append(f'sidebarTitle: "{sidebar}"')
    out.append("---")
    out.append("")
    if method.summary:
        out.append(_escape_mdx_prose(method.summary))
        out.append("")

    out.append("## Signature")
    out.append("")
    out.append("```python")
    out.append(method.signature_str)
    out.append("```")
    out.append("")

    if method.params:
        out.append("## Parameters")
        out.append("")
        for p in method.params:
            attrs = [f'path="{p.name}"', f'type="{p.type_label}"']
            if p.required:
                attrs.append("required")
            if p.default_repr is not None and p.default_repr not in ("None", "False"):
                attrs.append(f'default="{p.default_repr.strip(chr(39))}"')
            out.append(f"<ParamField {' '.join(attrs)}>")
            out.append(f"  {_escape_mdx_prose(p.help or '')}")
            out.append("</ParamField>")
            out.append("")

    out.append("## Returns")
    out.append("")
    out.append(f"`{method.returns_label}`")
    out.append("")

    out.append("## Example")
    out.append("")
    out.append("```python")
    out.append("from vastai import VastAI")
    out.append("")
    out.append('client = VastAI(api_key="YOUR_API_KEY")')
    args_demo = ", ".join(
        f"{p.name}={_demo_value(p)}"
        for p in method.params if p.required
    )
    out.append(f"result = client.{method.name}({args_demo})")
    out.append("print(result)")
    out.append("```")
    out.append("")

    return "\n".join(out).rstrip() + "\n"


def _demo_value(p: SdkParam) -> str:
    t = p.type_label.lower()
    if "int" in t:
        return "12345"
    if "float" in t or "number" in t:
        return "1.0"
    if "bool" in t:
        return "True"
    if "list" in t:
        return "[]"
    if "dict" in t:
        return "{}"
    return '"value"'


# ---------------------------------------------------------------------------
# Scope-based filtering
# ---------------------------------------------------------------------------
#
# A CLI command or SDK method is "internal" if every backend endpoint it hits
# is gated by an internal-only scope (admin_read_new, lower_admin, etc.).  We
# determine the endpoints by AST-walking vastai/api/*.py, vastai/cli/commands/*.py,
# and vastai/sdk.py, then look each (METHOD, URL) up in the snapshot file
# scripts/data/api_scopes.json (derived from vast/web/scope.json + paths.py).
#
# Policy:
#   - endpoint scope ∈ INTERNAL_SCOPES                → endpoint is internal
#   - endpoint scope ∉ INTERNAL_SCOPES (or "misc")    → endpoint is public
#   - all endpoints internal → command/method excluded
#   - at least one endpoint public → command/method included
#   - no endpoints found (couldn't statically resolve) → included (don't drop
#     unclassified items; emits a manifest warning instead)

SCOPE_DATA_PATH = Path(__file__).resolve().parent / "data" / "api_scopes.json"

# HTTP verbs exposed on VastClient (mirrors vastai/api/client.py)
CLIENT_VERBS = {"get", "post", "put", "delete", "patch"}


def _is_client_receiver(node: ast.AST) -> bool:
    """True if `node` denotes a VastClient instance — i.e. the parameter
    named ``client`` (the convention in vastai/api/*.py) or ``self.client``.
    Restricting matches this way prevents collisions with unrelated ``.get(...)``
    calls on dicts, requests.Response, the requests module, etc."""
    if isinstance(node, ast.Name) and node.id == "client":
        return True
    if (isinstance(node, ast.Attribute)
            and node.attr == "client"
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"):
        return True
    return False


def _stringify_url(node: ast.AST) -> Optional[str]:
    """Convert a string literal or f-string AST node to a route pattern.

    f-string interpolations are turned into named placeholders so
    f"/instances/{id}/" -> "/instances/{id}/", matching the route pattern
    style in vast/web/paths.py.  Returns None if the path can't be
    statically resolved.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out: list[str] = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                out.append(v.value)
            elif isinstance(v, ast.FormattedValue):
                inner = v.value
                if isinstance(inner, ast.Name):
                    out.append("{" + inner.id + "}")
                elif isinstance(inner, ast.Attribute):
                    out.append("{" + inner.attr + "}")
                else:
                    # Unresolvable expression — placeholder
                    out.append("{x}")
            else:
                return None
        return "".join(out)
    return None


def _normalize_subpath(subpath: Optional[str]) -> Optional[str]:
    """Apply VastClient._build_url's /api/v0 prefix rule and strip
    trailing slash so callsite and snapshot URLs can be compared
    irrespective of the noslash _auto routes Pyramid generates."""
    if not subpath:
        return None
    if not re.match(r"^/api/v\d+/", subpath):
        subpath = "/api/v0" + subpath
    if subpath.endswith("/") and len(subpath) > 1:
        subpath = subpath[:-1]
    return subpath


def _build_import_map(tree: ast.AST) -> dict[str, str]:
    """Map local names -> api module basenames for `from vastai.api import X`
    and `from vastai.api import X as Y` style imports."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("vastai.api"):
                # `from vastai.api import instances` -> instances=instances
                # `from vastai.api.instances import foo` -> foo=instances::foo
                #   (function-level alias, ignored — we resolve via call attr)
                if node.module == "vastai.api":
                    for alias in node.names:
                        aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("vastai.api."):
                    base = alias.name.split(".")[-1]
                    aliases[alias.asname or base] = base
    return aliases


def _stringify_url_candidates(node: ast.AST) -> list[str]:
    """Like _stringify_url but for ``a if cond else b`` returns both
    branches.  Useful for resolving things like
    ``endpoint = '/v0/charges/' if x else '/v1/invoices/'``."""
    single = _stringify_url(node)
    if single is not None:
        return [single]
    if isinstance(node, ast.IfExp):
        out: list[str] = []
        for branch in (node.body, node.orelse):
            out.extend(_stringify_url_candidates(branch))
        return out
    return []


def _collect_client_endpoints(fn_node: ast.AST) -> list[tuple[str, str]]:
    """Walk one function body and return the list of (METHOD, URL) tuples
    for every ``client.<verb>(<path>, ...)`` (or ``self.client.<verb>(...)``)
    call inside it.  Handles three forms of path expression:
      1. Literal string or f-string passed directly.
      2. A ``Name`` reference resolved against simple local bindings of the
         form ``url = "..."`` or ``url = f"..."`` earlier in the function.
      3. The bound value may itself be an ``a if cond else b`` expression
         where both branches are stringifiable — both URLs are recorded.
    """
    # First pass: gather trivial local string bindings within this function.
    local_strs: dict[str, list[str]] = {}
    for sub in ast.walk(fn_node):
        if not isinstance(sub, ast.Assign):
            continue
        if len(sub.targets) == 1 and isinstance(sub.targets[0], ast.Name):
            vals = _stringify_url_candidates(sub.value)
            if vals:
                local_strs[sub.targets[0].id] = vals

    out: list[tuple[str, str]] = []
    for sub in ast.walk(fn_node):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        if not (isinstance(func, ast.Attribute)
                and func.attr in CLIENT_VERBS
                and sub.args
                and _is_client_receiver(func.value)):
            continue
        arg = sub.args[0]
        candidates = _stringify_url_candidates(arg)
        if not candidates and isinstance(arg, ast.Name):
            candidates = local_strs.get(arg.id, [])
        for url in candidates:
            norm = _normalize_subpath(url)
            if norm:
                out.append((func.attr.upper(), norm))
    return out


def walk_api_endpoints(api_dir: Path) -> dict[tuple[str, str], list[tuple[str, str]]]:
    """For every function in vastai/api/*.py, list every (METHOD, URL) it
    calls on a VastClient.  Returns {(module_basename, func_name): [...]}."""
    endpoints: dict[tuple[str, str], list[tuple[str, str]]] = {}

    for f in sorted(api_dir.glob("*.py")):
        if f.name.startswith("_") or f.name == "client.py":
            continue
        mod = f.stem
        try:
            tree = ast.parse(f.read_text())
        except SyntaxError:
            continue

        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            hits = _collect_client_endpoints(fn)
            if hits:
                endpoints[(mod, fn.name)] = hits
    return endpoints


def walk_caller_endpoints(
    py_path: Path,
    api_endpoints: dict[tuple[str, str], list[tuple[str, str]]],
) -> dict[str, list[tuple[str, str]]]:
    """For each module-level function (or method on a class) in `py_path`,
    list the endpoints it reaches.

    Resolution chains through:
      1. Direct alias.api_fn(...) calls (resolved via this file's import map).
      2. Same-file function references — e.g. ``create__instance`` simply
         delegates to ``create_instance_impl``, which is where the api call
         actually lives.

    Returns {fn_name: [(METHOD, URL), ...]}.
    """
    tree = ast.parse(py_path.read_text())
    alias_map = _build_import_map(tree)

    # Collect local function names so we can chase intra-file calls
    local_fns = set()
    # Class-body assignments like ``invite_team_member = invite_member`` are
    # alias re-exports — record the source name so we can copy its endpoints.
    method_aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            local_fns.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    local_fns.add(sub.name)
                elif (isinstance(sub, ast.Assign)
                        and len(sub.targets) == 1
                        and isinstance(sub.targets[0], ast.Name)
                        and isinstance(sub.value, ast.Name)):
                    method_aliases[sub.targets[0].id] = sub.value.id

    direct: dict[str, list[tuple[str, str]]] = defaultdict(list)
    local_refs: dict[str, set[str]] = defaultdict(set)

    def scan(fn_node: ast.AST, fn_name: str) -> None:
        # Direct client.verb(...) calls in the function body — search__offers
        # in offers.py is the canonical example.
        direct[fn_name].extend(_collect_client_endpoints(fn_node))

        for sub in ast.walk(fn_node):
            if not isinstance(sub, ast.Call):
                continue
            func = sub.func
            # alias.fn(...) where alias resolves to an api module
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                mod = alias_map.get(func.value.id)
                if mod is not None:
                    hits = api_endpoints.get((mod, func.attr))
                    if hits:
                        direct[fn_name].extend(hits)
                    continue
                # self.<method>(...) — record for sdk.py-style methods
                if func.value.id == "self" and func.attr in local_fns:
                    local_refs[fn_name].add(func.attr)
            # local_helper(...) at the module level
            elif isinstance(func, ast.Name) and func.id in local_fns:
                local_refs[fn_name].add(func.id)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scan(node, node.name)
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    scan(sub, sub.name)

    # Resolve same-file call chains to fixed point.  Depth-bounded to avoid
    # cycles (mutual recursion is fine — we just stop reseeding after we
    # stop accumulating new endpoints).
    resolved: dict[str, list[tuple[str, str]]] = {fn: list(direct.get(fn, [])) for fn in local_fns}

    # Seed aliases with their source method's direct endpoints; chain
    # resolution below will continue propagating through any helpers the
    # source calls.
    for alias, source in method_aliases.items():
        if source in resolved:
            resolved[alias] = list(resolved[source])
            local_refs.setdefault(alias, set()).add(source)
            local_fns.add(alias)

    for _ in range(8):
        changed = False
        for fn, callees in local_refs.items():
            before = len(resolved.get(fn, []))
            existing = set(map(tuple, resolved.get(fn, [])))
            for callee in callees:
                for hit in resolved.get(callee, []):
                    if tuple(hit) not in existing:
                        resolved.setdefault(fn, []).append(hit)
                        existing.add(tuple(hit))
            if len(resolved.get(fn, [])) != before:
                changed = True
        if not changed:
            break

    return {k: v for k, v in resolved.items() if v}


@dataclass
class ScopeIndex:
    """Snapshot of api endpoints -> {METHOD: scope}.

    Match logic uses regex patterns so a call to ``/api/v0/users/me/invoices``
    matches the snapshot route ``/api/v0/users/{user_id}/invoices``.  Exact
    matches are tried first (fast path); the regex pass handles literal/
    placeholder mismatches.
    """
    by_url: dict[str, dict[str, str]]
    patterns: list[tuple[re.Pattern, dict[str, str]]]
    internal_scopes: set[str]

    @classmethod
    def load(cls, path: Path = SCOPE_DATA_PATH) -> "ScopeIndex":
        raw = json.loads(path.read_text())
        by_url: dict[str, dict[str, str]] = {}
        patterns: list[tuple[re.Pattern, dict[str, str]]] = []
        for url, methods in raw["endpoints"].items():
            canon = _canon_url(url)
            by_url[canon] = methods
            # Compile a regex by replacing each placeholder token with a
            # one-segment wildcard.  _canon_url already mapped {name} -> {}.
            regex = re.compile("^" + re.escape(canon).replace(r"\{\}", "[^/]+") + "$")
            patterns.append((regex, methods))
        return cls(
            by_url=by_url,
            patterns=patterns,
            internal_scopes=set(raw["_meta"]["internal_scopes"]),
        )

    def _lookup(self, url: str) -> Optional[dict[str, str]]:
        canon = _canon_url(url)
        hit = self.by_url.get(canon)
        if hit is not None:
            return hit
        for regex, methods in self.patterns:
            if regex.match(canon):
                return methods
        return None

    def classify(self, endpoint_hits: list[tuple[str, str]]) -> str:
        """Return 'public', 'internal', or 'unknown'."""
        if not endpoint_hits:
            return "unknown"
        any_public = False
        any_matched = False
        for method, url in endpoint_hits:
            scopes = self._lookup(url)
            if not scopes:
                continue
            scope = scopes.get(method)
            if scope is None:
                continue
            any_matched = True
            if scope not in self.internal_scopes:
                any_public = True
        if not any_matched:
            return "unknown"
        return "public" if any_public else "internal"


_PLACEHOLDER_RX = re.compile(r"\{[^}]*\}")


def _canon_url(url: str) -> str:
    """Strip trailing slash and replace every ``{name}`` placeholder with
    ``{}`` so call-sites using ``{id}`` line up with routes declared with
    ``{machine_id}`` and similar."""
    s = _PLACEHOLDER_RX.sub("{}", url)
    if s.endswith("/") and len(s) > 1:
        s = s[:-1]
    return s


def build_function_endpoint_map(
    vastai_pkg: Path,
) -> tuple[dict[str, list[tuple[str, str]]], dict[str, list[tuple[str, str]]]]:
    """Return (cli_command_endpoints, sdk_method_endpoints) keyed by
    plain Python function/method name.  Names collide across CLI command
    files only when the same dest name is registered twice, which doesn't
    happen in this codebase — but if it ever does, the last writer wins."""
    api_endpoints = walk_api_endpoints(vastai_pkg / "api")

    cli_endpoints: dict[str, list[tuple[str, str]]] = {}
    cmd_dir = vastai_pkg / "cli" / "commands"
    for f in sorted(cmd_dir.glob("*.py")):
        if f.name.startswith("_"):
            continue
        for fn_name, hits in walk_caller_endpoints(f, api_endpoints).items():
            cli_endpoints[fn_name] = hits

    sdk_endpoints = walk_caller_endpoints(vastai_pkg / "sdk.py", api_endpoints)
    return cli_endpoints, sdk_endpoints


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

SKIP_COMMAND_NAMES = {"help"}


def collect_cli_commands(parser_obj) -> dict[str, CliCommand]:
    """Walk the registered subparsers and return {doc_name: CliCommand}.

    Each subparser's `prog` is `<parent_prog> <command_name>`, where
    command_name is the string apwrap registered (e.g., "create instance"
    or "copy").  We strip the parent prefix to recover the command name —
    this works regardless of how the script is invoked (vastai entrypoint,
    `python -m`, `python scripts/...`).
    """
    commands: dict[str, CliCommand] = {}
    parent_prog = parser_obj.parser.prog

    # Pull canonical names from the SubParsersAction.choices map for cases
    # where stripping the parent prog is ambiguous.
    name_to_subparser: dict[str, argparse.ArgumentParser] = {}
    if parser_obj.subparsers_ is not None:
        for canonical_name, sub in parser_obj.subparsers_.choices.items():
            name_to_subparser.setdefault(id(sub), canonical_name)

    canonical_by_id = {}
    if parser_obj.subparsers_ is not None:
        for canonical_name, sub in parser_obj.subparsers_.choices.items():
            canonical_by_id.setdefault(id(sub), canonical_name)

    seen_names: set[str] = set()

    for sp in parser_obj.subparser_objs:
        cmd_name = canonical_by_id.get(id(sp))
        if cmd_name is None:
            # Fallback: strip parent prog prefix.
            if sp.prog.startswith(parent_prog + " "):
                cmd_name = sp.prog[len(parent_prog) + 1:]
            else:
                # Last-ditch: take the trailing 1-2 tokens.
                cmd_name = " ".join(sp.prog.split()[-2:])
        cmd_name = cmd_name.strip()
        if not cmd_name:
            continue
        if cmd_name in SKIP_COMMAND_NAMES or cmd_name.split()[0] in SKIP_COMMAND_NAMES:
            continue
        # Aliases register as separate subparsers in apwrap; dedupe by name.
        if cmd_name in seen_names:
            continue
        seen_names.add(cmd_name)

        func = sp.get_default("func")
        cmd = extract_command(sp, cmd_name, func)
        commands[cmd.doc_name] = cmd
    return commands


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output-dir", default="generated-docs",
                    help="Directory to write generated MDX (default: generated-docs)")
    ap.add_argument("--cli-subdir", default="cli/reference",
                    help="Subdirectory under output-dir for CLI pages")
    ap.add_argument("--sdk-subdir", default="sdk/python/reference",
                    help="Subdirectory under output-dir for SDK pages")
    ap.add_argument("--manifest", default=None,
                    help="Optional path to write a JSON manifest of generated files")
    ap.add_argument("--skip-cli", action="store_true",
                    help="Skip generating CLI pages")
    ap.add_argument("--skip-sdk", action="store_true",
                    help="Skip generating SDK pages")
    args = ap.parse_args()

    out_root = Path(args.output_dir)

    parser_obj = load_cli_parser()
    cli_commands = collect_cli_commands(parser_obj)
    print(f"Discovered {len(cli_commands)} CLI commands.")

    # Load the scope snapshot + endpoint map so we can drop internal-only
    # commands/methods.  Snapshot lives at scripts/data/api_scopes.json.
    import vastai
    scope_index = ScopeIndex.load()
    vastai_pkg = Path(vastai.__file__).resolve().parent
    cli_fn_endpoints, sdk_fn_endpoints = build_function_endpoint_map(vastai_pkg)

    written: list[dict] = []
    excluded_cli: list[dict] = []
    excluded_sdk: list[dict] = []
    excluded_policy_cli: list[str] = []
    excluded_policy_sdk: list[str] = []
    unknown_cli: list[str] = []
    unknown_sdk: list[str] = []

    if not args.skip_cli:
        cli_dir = out_root / args.cli_subdir
        cli_dir.mkdir(parents=True, exist_ok=True)
        for doc_name, cmd in sorted(cli_commands.items()):
            if doc_name in EXCLUDED_NAMES:
                excluded_policy_cli.append(doc_name)
                continue
            hits = cli_fn_endpoints.get(cmd.func_name, [])
            verdict = scope_index.classify(hits)
            if verdict == "internal":
                excluded_cli.append({
                    "name": doc_name,
                    "func": cmd.func_name,
                    "endpoints": hits,
                })
                continue
            if verdict == "unknown":
                unknown_cli.append(doc_name)
            mdx = render_cli_mdx(cmd)
            (cli_dir / f"{doc_name}.mdx").write_text(mdx)
            written.append({"kind": "cli", "name": doc_name})
        print(f"Wrote {sum(1 for w in written if w['kind'] == 'cli')} CLI pages to {cli_dir} "
              f"({len(excluded_policy_cli)} excluded by policy, "
              f"{len(excluded_cli)} excluded as internal, {len(unknown_cli)} unclassified)")

    if not args.skip_sdk:
        sdk_dir = out_root / args.sdk_subdir
        sdk_dir.mkdir(parents=True, exist_ok=True)
        sdk_methods = extract_sdk_methods(cli_commands)
        print(f"Discovered {len(sdk_methods)} SDK methods.")
        for m in sorted(sdk_methods, key=lambda x: x.doc_name):
            if m.doc_name in EXCLUDED_NAMES:
                excluded_policy_sdk.append(m.doc_name)
                continue
            hits = sdk_fn_endpoints.get(m.name, [])
            verdict = scope_index.classify(hits)
            if verdict == "internal":
                excluded_sdk.append({
                    "name": m.doc_name,
                    "func": m.name,
                    "endpoints": hits,
                })
                continue
            if verdict == "unknown":
                unknown_sdk.append(m.doc_name)
            mdx = render_sdk_mdx(m)
            (sdk_dir / f"{m.doc_name}.mdx").write_text(mdx)
            written.append({"kind": "sdk", "name": m.doc_name})
        print(f"Wrote {sum(1 for w in written if w['kind'] == 'sdk')} SDK pages to {sdk_dir} "
              f"({len(excluded_policy_sdk)} excluded by policy, "
              f"{len(excluded_sdk)} excluded as internal, {len(unknown_sdk)} unclassified)")

    if args.manifest:
        Path(args.manifest).write_text(json.dumps({
            "cli_count": sum(1 for w in written if w["kind"] == "cli"),
            "sdk_count": sum(1 for w in written if w["kind"] == "sdk"),
            "files": written,
            "excluded_internal_cli": excluded_cli,
            "excluded_internal_sdk": excluded_sdk,
            "excluded_policy_cli": excluded_policy_cli,
            "excluded_policy_sdk": excluded_policy_sdk,
            "unclassified_cli": unknown_cli,
            "unclassified_sdk": unknown_sdk,
        }, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
