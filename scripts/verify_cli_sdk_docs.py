#!/usr/bin/env python3
"""
Verify CLI/SDK documentation against the actual vast-cli package.

Compares:
  1. CLI commands (from `vastai --help` + subcommand help) vs docs/cli/reference/*.mdx
  2. SDK methods (from introspecting VastAI class) vs docs/sdk/python/reference/*.mdx
  3. Flags/parameters for each CLI command vs documented flags in MDX pages

Usage:
    # Basic inventory check (requires vastai CLI installed + docs repo cloned)
    python scripts/verify_cli_sdk_docs.py --docs-path /path/to/docs

    # Full parameter-level validation
    python scripts/verify_cli_sdk_docs.py --docs-path /path/to/docs --check-params

    # Output as JSON (for CI)
    python scripts/verify_cli_sdk_docs.py --docs-path /path/to/docs --json

Exit codes:
    0 = no drift detected
    1 = drift detected (missing/stale docs or parameter mismatches)
"""

import argparse
import ast
import inspect
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DriftReport:
    cli_undocumented: list = field(default_factory=list)
    cli_stale: list = field(default_factory=list)
    sdk_undocumented: list = field(default_factory=list)
    sdk_stale: list = field(default_factory=list)
    cli_param_mismatches: dict = field(default_factory=dict)
    sdk_param_mismatches: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)

    @property
    def has_drift(self):
        return any([
            self.cli_undocumented,
            self.cli_stale,
            self.sdk_undocumented,
            self.sdk_stale,
            self.cli_param_mismatches,
            self.sdk_param_mismatches,
        ])

    def to_dict(self):
        return {
            "cli": {
                "undocumented": self.cli_undocumented,
                "stale_docs": self.cli_stale,
                "param_mismatches": self.cli_param_mismatches,
            },
            "sdk": {
                "undocumented": self.sdk_undocumented,
                "stale_docs": self.sdk_stale,
                "param_mismatches": self.sdk_param_mismatches,
            },
            "errors": self.errors,
            "has_drift": self.has_drift,
        }

    def print_summary(self):
        print("\n" + "=" * 60)
        print("CLI/SDK Documentation Drift Report")
        print("=" * 60)

        if not self.has_drift and not self.errors:
            print("\nNo drift detected. Docs are in sync.")
            return

        if self.cli_undocumented:
            print(f"\nCLI commands missing docs ({len(self.cli_undocumented)}):")
            for cmd in sorted(self.cli_undocumented):
                print(f"  - {cmd}")

        if self.cli_stale:
            print(f"\nCLI docs for removed commands ({len(self.cli_stale)}):")
            for cmd in sorted(self.cli_stale):
                print(f"  - {cmd}")

        if self.sdk_undocumented:
            print(f"\nSDK methods missing docs ({len(self.sdk_undocumented)}):")
            for method in sorted(self.sdk_undocumented):
                print(f"  - {method}")

        if self.sdk_stale:
            print(f"\nSDK docs for removed methods ({len(self.sdk_stale)}):")
            for method in sorted(self.sdk_stale):
                print(f"  - {method}")

        if self.cli_param_mismatches:
            print(f"\nCLI parameter mismatches ({len(self.cli_param_mismatches)}):")
            for cmd, diff in sorted(self.cli_param_mismatches.items()):
                print(f"  {cmd}:")
                if diff.get("missing_from_docs"):
                    print(f"    undocumented flags: {diff['missing_from_docs']}")
                if diff.get("stale_in_docs"):
                    print(f"    stale in docs:      {diff['stale_in_docs']}")

        if self.sdk_param_mismatches:
            print(f"\nSDK parameter mismatches ({len(self.sdk_param_mismatches)}):")
            for method, diff in sorted(self.sdk_param_mismatches.items()):
                print(f"  {method}:")
                if diff.get("missing_from_docs"):
                    print(f"    undocumented params: {diff['missing_from_docs']}")
                if diff.get("stale_in_docs"):
                    print(f"    stale in docs:       {diff['stale_in_docs']}")

        if self.errors:
            print(f"\nErrors ({len(self.errors)}):")
            for err in self.errors:
                print(f"  - {err}")

        print()


# ---------------------------------------------------------------------------
# Environment resolution
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent


GENERATOR_PATH = SCRIPT_DIR / "generate_cli_sdk_docs.py"


def _generator_constant(name: str, consequence: str) -> set[str]:
    """
    Read a module-level set literal out of generate_cli_sdk_docs.py.

    The verifier must apply the same publishing policy as the generator or it
    reports the generator's deliberate choices as drift on every single run.
    Those permanent false alarms are what made the weekly drift check
    untrustworthy. Reading the values keeps one definition of each policy.

    Read statically with `ast` rather than by importing: the verifier is the
    independent check on the generator, so it should not need the generator (or
    the generator's imports) to load successfully in order to run.
    """
    try:
        tree = ast.parse(GENERATOR_PATH.read_text())
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets
            ):
                continue
            return {str(v) for v in ast.literal_eval(node.value)}

        raise ValueError(f"no module-level {name} assignment found")
    except Exception as exc:  # pragma: no cover - defensive
        print(
            f"WARNING: could not read {name} from {GENERATOR_PATH.name} ({exc}); "
            f"{consequence}",
            file=sys.stderr,
        )
        return set()


def get_excluded_names() -> set[str]:
    """Doc names the generator never publishes (network-volume surface)."""
    return _generator_constant(
        "EXCLUDED_NAMES",
        "policy-excluded commands will be reported as drift.",
    )


def get_global_cli_options() -> set[str]:
    """
    Options every command inherits from the top-level parser.

    The generator renders these once in a static "Global Options" table per page
    instead of repeating them in each command's parameter list, so they appear in
    `--help` output but never as a per-command ParamField. Without this the
    checker reports the same six flags as undocumented on all ~134 commands.
    """
    return _generator_constant(
        "GLOBAL_CLI_OPTIONS",
        "global options will be reported as undocumented on every command.",
    )


def vastai_cmd() -> list[str]:
    """
    Argv prefix for invoking the CLI that belongs to THIS interpreter.

    Resolving bare "vastai" through PATH is wrong: it picks up whatever build
    happens to be installed globally, while get_sdk_methods() introspects the
    imported `vastai` package. The two halves of this script then describe
    different versions of the CLI and every difference is reported as drift.
    Prefer the console script next to sys.executable so both halves agree.
    """
    candidate = Path(sys.executable).parent / "vastai"
    if candidate.exists():
        return [str(candidate)]

    print(
        "WARNING: no 'vastai' console script next to the running interpreter "
        f"({candidate}); falling back to PATH. CLI and SDK results may come from "
        "different installs.",
        file=sys.stderr,
    )
    return ["vastai"]


# ---------------------------------------------------------------------------
# CLI introspection
# ---------------------------------------------------------------------------

def get_cli_commands() -> dict[str, list[str]]:
    """
    Run `vastai --help` to get commands, then `vastai <cmd> --help` for each
    to extract flags.

    Handles both flat commands (e.g., `vastai copy`) and two-level commands
    (e.g., `vastai show instances`). Two-level commands are flattened to
    kebab-case (e.g., "show-instances") for matching against doc filenames.

    Returns: {command_name: [list of --flags]}
    """
    commands = {}
    base = vastai_cmd()
    global_options = get_global_cli_options()

    # Get help output
    result = subprocess.run(
        base + ["--help"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"vastai --help failed: {result.stderr}")

    subcommands = _parse_subcommands(result.stdout)

    for cmd_parts in subcommands:
        # cmd_parts is a list like ["show", "instances"] or ["copy"]
        doc_name = "-".join(cmd_parts)  # flatten to kebab-case for doc matching
        try:
            sub_result = subprocess.run(
                base + cmd_parts + ["--help"],
                capture_output=True, text=True, timeout=30,
            )
        except subprocess.TimeoutExpired:
            commands[doc_name] = []
            continue

        # `<cmd> --help` exiting non-zero means _parse_subcommands scraped
        # something that is not actually a command (a group heading, a wrapped
        # description line, trailing prose). Dropping those here keeps a help
        # -format change from inventing phantom commands and failing the run.
        if sub_result.returncode != 0:
            continue

        commands[doc_name] = _parse_flags(
            sub_result.stdout + sub_result.stderr, global_options,
        )

    return commands


def _parse_subcommands(help_text: str) -> list[list[str]]:
    """
    Extract command names from vastai --help output.

    Handles two-level commands like:
        show instances           Display user's current instances
        create instance          Create a new instance
        copy                     Copy directories between instances

    Returns: list of command parts, e.g., [["show", "instances"], ["copy"]]
    """
    commands = []
    in_commands_section = False

    for line in help_text.splitlines():
        stripped = line.strip()

        # Detect start of commands section
        if re.match(r"^(positional arguments|command)", stripped, re.IGNORECASE):
            in_commands_section = True
            continue

        # Detect end of commands section
        if in_commands_section:
            if stripped == "" and commands:
                # Empty line after we've found commands — might be end of section
                continue
            if re.match(r"^(optional arguments|options|$)", stripped, re.IGNORECASE) and commands:
                if stripped.startswith(("options", "optional")):
                    in_commands_section = False
                    continue

        if not in_commands_section:
            continue

        # Skip non-command lines
        if stripped.startswith("-") or stripped.startswith("command"):
            continue

        # Parse command line: "  verb noun       description text"
        # Use 2+ spaces as separator between command and description
        parts = re.split(r"\s{2,}", stripped, maxsplit=1)
        if not parts or not parts[0]:
            continue

        cmd_text = parts[0].strip()
        if not cmd_text or cmd_text.startswith("-"):
            continue

        # Group headings ("Instances:", "Billing & account:", "options:") sit in
        # the same column as commands once the CLI groups its help output. They
        # are never commands.
        if cmd_text.endswith(":"):
            continue

        # Split the command into parts (handles "show instances", "tfa activate", "copy")
        cmd_parts = cmd_text.split()
        if not cmd_parts or cmd_parts[0] == "help":
            continue

        # Every real command token is lowercase kebab-case. This rejects prose
        # that wraps into the command column -- e.g. the trailing
        # "Use 'vastai COMMAND --help' ..." footer.
        if not all(re.fullmatch(r"[a-z0-9][a-z0-9-]*", part) for part in cmd_parts):
            continue

        commands.append(cmd_parts)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for parts in commands:
        key = tuple(parts)
        if key not in seen:
            seen.add(key)
            unique.append(parts)

    return unique


def _parse_flags(help_text: str, global_options: set[str] | None = None) -> list[str]:
    """
    Extract --flag names from argparse help output.

    Global options are dropped: they are inherited by every command and the docs
    render them once in a per-page "Global Options" table rather than as
    per-command parameters.
    """
    global_options = global_options or set()
    flags = set()

    for line in help_text.splitlines():
        stripped = line.strip()

        # Only lines that *declare* an option count. Scanning the whole help
        # text also matched flags quoted inside description strings and epilog
        # prose -- e.g. create-workergroup's --launch_args help embeds an
        # example containing "--onstart --env --image --disk", and
        # tfa-totp-setup's epilog walks the user through `vastai tfa activate
        # --method-type ... --secret ...`. Those belong to other commands and
        # were reported as undocumented flags of this one.
        if not stripped.startswith("-"):
            continue

        # argparse puts >=2 spaces between the option signature and its help
        # text, so the signature is everything before that gap.
        signature = re.split(r"\s{2,}", stripped, maxsplit=1)[0]

        for match in re.finditer(r'(--[\w][\w-]*)', signature):
            flag = match.group(1)
            if flag in ("--help", "--version"):
                continue
            # `--no-color` in help vs `no_color` in the parser's dest list.
            if flag.lstrip("-").replace("-", "_") in global_options:
                continue
            flags.add(flag)

    return sorted(flags)


# ---------------------------------------------------------------------------
# SDK introspection
# ---------------------------------------------------------------------------

def get_sdk_methods() -> tuple[dict[str, list[str]], set[str]]:
    """
    Import vastai SDK and introspect the VastAI class for public methods.

    `*args` / `**kwargs` are variadic markers, not parameters. Including them
    made the checker demand a documented parameter literally named "kwargs" on
    every method that takes them.

    Returns: ({method_name: [parameter names]}, {methods taking **kwargs})
    """
    try:
        from vastai.sdk import VastAI
    except ImportError:
        try:
            from vastai_sdk import VastAI
        except ImportError:
            raise ImportError(
                "Cannot import VastAI. Install with: pip install vastai"
            )

    methods = {}
    open_signatures = set()
    variadic = (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)

    for name, func in inspect.getmembers(VastAI, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue
        sig = inspect.signature(func)
        params = [
            p.name for p in sig.parameters.values()
            if p.name != "self" and p.kind not in variadic
        ]
        methods[name] = params

        if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            open_signatures.add(name)

    return methods, open_signatures


# ---------------------------------------------------------------------------
# Docs introspection
# ---------------------------------------------------------------------------

def get_documented_cli_commands(docs_path: Path) -> dict[str, list[str]]:
    """
    Scan docs/cli/reference/*.mdx for documented CLI commands.

    Returns: {command_name: [list of documented flags]}
    """
    ref_dir = docs_path / "cli" / "reference"
    if not ref_dir.exists():
        return {}

    # Each CLI page ends with a static "Global Options" table. Those rows parse
    # as flags, so drop them here exactly as _parse_flags drops them from the
    # help output -- otherwise every page reports them as stale documentation.
    global_options = get_global_cli_options()

    commands = {}
    for mdx_file in ref_dir.glob("*.mdx"):
        cmd_name = mdx_file.stem  # e.g., "create-instance"
        flags = _parse_mdx_params(mdx_file, param_type="flag")
        commands[cmd_name] = [
            f for f in flags if f.replace("-", "_") not in global_options
        ]

    return commands


def get_documented_sdk_methods(docs_path: Path) -> dict[str, list[str]]:
    """
    Scan docs/sdk/python/reference/*.mdx for documented SDK methods.

    Returns: {method_name: [list of documented params]}
    """
    ref_dir = docs_path / "sdk" / "python" / "reference"
    if not ref_dir.exists():
        return {}

    methods = {}
    for mdx_file in ref_dir.glob("*.mdx"):
        method_name = mdx_file.stem  # e.g., "create-instance"
        params = _parse_mdx_params(mdx_file, param_type="param")
        methods[method_name] = params

    return methods


def _parse_mdx_params(mdx_file: Path, param_type: str = "flag") -> list[str]:
    """
    Extract parameter/flag names from an MDX documentation page.

    Handles common Mintlify patterns:
      - <ParamField name="--flag-name" ...>
      - <ParamField path="flag_name" ...>
      - | `--flag-name` | description |  (markdown tables)
      - **--flag-name** or `--flag-name`  (inline)

    For param_type="flag" (CLI pages) only flag-shaped entries are returned.
    CLI pages document positional arguments as ParamFields too (`path="id"`),
    but the actual-side inventory comes from scraping `--flags` out of `--help`
    and so can never contain a positional. Returning them made every command
    with a positional argument report it as stale documentation.
    """
    return _parse_mdx_params_from_text(
        _resolve_snippets(mdx_file), param_type,
    )


def _resolve_snippets(mdx_file: Path, docs_root: Path | None = None) -> str:
    """Return the page text with any Mintlify snippet imports inlined.

    The host reference pages are one-line wrappers around
    /snippets/host/sdk/*.mdx. Reading only the wrapper made every parameter on
    those pages invisible, so the checker reported them all as missing from the
    docs and could not see wrong ones at all.
    """
    content = mdx_file.read_text(errors="replace")
    if docs_root is None:
        # .../<docs>/sdk/python/reference/<page>.mdx and the host equivalent
        for parent in mdx_file.parents:
            if (parent / "snippets").is_dir():
                docs_root = parent
                break
    if docs_root is None:
        return content

    for path in re.findall(r"""import\s+\w+\s+from\s+['"](/snippets/[^'"]+)['"]""", content):
        snippet = docs_root / path.lstrip("/")
        if snippet.is_file():
            content += "\n" + snippet.read_text(errors="replace")
    return content


def _parse_mdx_params_from_text(content: str, param_type: str = "flag") -> list[str]:
    """Parameter extraction for _parse_mdx_params, split out to be testable."""
    raw = set()

    # Mintlify <ParamField> components
    for match in re.finditer(
        r'<ParamField\s+[^>]*(?:name|path|query|body)\s*=\s*["\']([^"\']+)["\']',
        content,
    ):
        raw.add(match.group(1).strip())

    # Markdown table rows with flags: | `--flag` | or | --flag |
    # Require a letter after the dashes so the `| --- | --- |` header separator
    # is not picked up as a parameter named "".
    for match in re.finditer(r'\|\s*`?(--[a-zA-Z][\w-]*)`?\s*\|', content):
        raw.add(match.group(1).strip())

    # Fallback: look for --flag patterns in code blocks and descriptions
    if not raw:
        for match in re.finditer(r'`(--[a-zA-Z][\w-]*)`', content):
            raw.add(match.group(1).strip())

    if param_type == "flag":
        raw = {p for p in raw if p.startswith("--")}

    return sorted({p.lstrip("-").strip() for p in raw} - {""})


# ---------------------------------------------------------------------------
# Name normalization (SDK method_name <-> doc filename)
# ---------------------------------------------------------------------------

def sdk_method_to_doc_name(method_name: str) -> str:
    """Convert SDK method name (snake_case) to doc filename (kebab-case)."""
    return method_name.replace("_", "-")


def doc_name_to_sdk_method(doc_name: str) -> str:
    """Convert doc filename (kebab-case) to SDK method name (snake_case)."""
    return doc_name.replace("-", "_")


def cli_command_to_doc_name(command: str) -> str:
    """CLI commands already use kebab-case matching doc filenames."""
    return command


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def compare_inventory(
    actual: dict[str, list[str]],
    documented: dict[str, list[str]],
    name_to_doc: callable,
    excluded: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    """
    Compare actual commands/methods against documented ones.

    `excluded` holds doc names the generator never publishes by policy. They are
    dropped from the code side so they stop showing up as "missing docs" forever.
    They are deliberately NOT dropped from the docs side: a policy-excluded page
    that exists in the docs repo is a real problem and should still be reported
    as stale.

    Returns: (undocumented, stale)
    """
    excluded = excluded or set()

    actual_doc_names = {name_to_doc(name) for name in actual} - excluded
    documented_names = set(documented.keys())

    undocumented = sorted(actual_doc_names - documented_names)
    stale = sorted(documented_names - actual_doc_names)

    return undocumented, stale


def compare_params(
    actual: dict[str, list[str]],
    documented: dict[str, list[str]],
    name_to_doc: callable,
    open_signatures: set[str] | None = None,
) -> dict:
    """
    For each command/method that exists in both, compare parameters.

    `open_signatures` holds names whose signature ends in `**kwargs`. Those are
    the only ones where an extra documented parameter cannot be judged: the
    signature does not enumerate what it accepts, so the generator fills the
    table in from the matching CLI command. The suppression used to cover the
    create/update instance and template methods too, which is how 50 parameters
    that raise TypeError stayed published. Those now have closed
    signatures, so they are checked like anything else.

    Returns: {name: {"missing_from_docs": [...], "stale_in_docs": [...]}}
    """
    open_signatures = open_signatures or set()
    mismatches = {}

    for actual_name, actual_params in actual.items():
        doc_name = name_to_doc(actual_name)
        if doc_name not in documented:
            continue

        doc_params = documented[doc_name]
        if not actual_params and not doc_params:
            continue

        # Normalize for comparison (strip --, convert to comparable form)
        actual_set = {p.lstrip("-").replace("-", "_") for p in actual_params}
        doc_set = {p.lstrip("-").replace("-", "_") for p in doc_params}

        missing = sorted(actual_set - doc_set)
        stale = [] if actual_name in open_signatures else sorted(doc_set - actual_set)

        if missing or stale:
            mismatches[doc_name] = {}
            if missing:
                mismatches[doc_name]["missing_from_docs"] = missing
            if stale:
                mismatches[doc_name]["stale_in_docs"] = stale

    return mismatches


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(docs_path: str, check_params: bool = False, output_json: bool = False):
    report = DriftReport()
    docs = Path(docs_path)

    if not docs.exists():
        print(f"Error: docs path does not exist: {docs_path}", file=sys.stderr)
        sys.exit(2)

    excluded = get_excluded_names()

    # --- CLI ---
    try:
        cli_actual = get_cli_commands()
        cli_documented = get_documented_cli_commands(docs)

        undoc, stale = compare_inventory(
            cli_actual, cli_documented, cli_command_to_doc_name, excluded,
        )
        report.cli_undocumented = undoc
        report.cli_stale = stale

        if check_params and cli_actual and cli_documented:
            report.cli_param_mismatches = compare_params(
                cli_actual, cli_documented, cli_command_to_doc_name,
            )
    except Exception as e:
        report.errors.append(f"CLI check failed: {e}")

    # --- SDK ---
    try:
        sdk_actual, sdk_open_signatures = get_sdk_methods()
        sdk_documented = get_documented_sdk_methods(docs)

        undoc, stale = compare_inventory(
            sdk_actual, sdk_documented, sdk_method_to_doc_name, excluded,
        )
        report.sdk_undocumented = undoc
        report.sdk_stale = stale

        if check_params and sdk_actual and sdk_documented:
            report.sdk_param_mismatches = compare_params(
                sdk_actual, sdk_documented, sdk_method_to_doc_name,
                sdk_open_signatures,
            )
    except Exception as e:
        report.errors.append(f"SDK check failed: {e}")

    # --- Output ---
    if output_json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        report.print_summary()

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Verify CLI/SDK docs match the actual vastai package.",
    )
    parser.add_argument(
        "--docs-path", required=True,
        help="Path to the cloned vast-ai/docs repository",
    )
    parser.add_argument(
        "--check-params", action="store_true",
        help="Also validate flags/parameters for each command (slower)",
    )
    parser.add_argument(
        "--json", action="store_true", dest="output_json",
        help="Output report as JSON",
    )
    args = parser.parse_args()

    report = run(args.docs_path, args.check_params, args.output_json)
    sys.exit(1 if report.has_drift else 0)


if __name__ == "__main__":
    main()
