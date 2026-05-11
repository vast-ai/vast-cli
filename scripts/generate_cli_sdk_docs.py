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
import inspect
import json
import re
import sys
import textwrap
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


def load_cli_parser():
    """Import the CLI and return its top-level apwrap parser fully wired."""
    # Importing the commands triggers @parser.command decorator registration.
    from vastai.cli.commands import (  # noqa: F401
        instances, offers, machines, teams, keys, endpoints,
        billing, storage, auth, misc, deployments,
    )
    from vastai.cli.main import parser
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
        out.append(cmd.summary)
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
        out.append(cmd.description)
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
        out.append(method.summary)
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
            out.append(f"  {p.help or ''}")
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

    written: list[dict] = []

    if not args.skip_cli:
        cli_dir = out_root / args.cli_subdir
        cli_dir.mkdir(parents=True, exist_ok=True)
        for doc_name, cmd in sorted(cli_commands.items()):
            mdx = render_cli_mdx(cmd)
            (cli_dir / f"{doc_name}.mdx").write_text(mdx)
            written.append({"kind": "cli", "name": doc_name})
        print(f"Wrote {len(cli_commands)} CLI pages to {cli_dir}")

    if not args.skip_sdk:
        sdk_dir = out_root / args.sdk_subdir
        sdk_dir.mkdir(parents=True, exist_ok=True)
        sdk_methods = extract_sdk_methods(cli_commands)
        print(f"Discovered {len(sdk_methods)} SDK methods.")
        for m in sorted(sdk_methods, key=lambda x: x.doc_name):
            mdx = render_sdk_mdx(m)
            (sdk_dir / f"{m.doc_name}.mdx").write_text(mdx)
            written.append({"kind": "sdk", "name": m.doc_name})
        print(f"Wrote {len(sdk_methods)} SDK pages to {sdk_dir}")

    if args.manifest:
        Path(args.manifest).write_text(json.dumps({
            "cli_count": sum(1 for w in written if w["kind"] == "cli"),
            "sdk_count": sum(1 for w in written if w["kind"] == "sdk"),
            "files": written,
        }, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
