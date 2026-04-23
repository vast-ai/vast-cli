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

    # Get help output
    result = subprocess.run(
        ["vastai", "--help"],
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
                ["vastai"] + cmd_parts + ["--help"],
                capture_output=True, text=True, timeout=30,
            )
            flags = _parse_flags(sub_result.stdout + sub_result.stderr)
            commands[doc_name] = flags
        except (subprocess.TimeoutExpired, Exception):
            commands[doc_name] = []

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

        # Split the command into parts (handles "show instances", "tfa activate", "copy")
        cmd_parts = cmd_text.split()
        if cmd_parts and cmd_parts[0] != "help":
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


def _parse_flags(help_text: str) -> list[str]:
    """Extract --flag names from argparse help output."""
    flags = set()
    for match in re.finditer(r'(--[\w][\w-]*)', help_text):
        flag = match.group(1)
        if flag not in ("--help", "--version"):
            flags.add(flag)
    return sorted(flags)


# ---------------------------------------------------------------------------
# SDK introspection
# ---------------------------------------------------------------------------

def get_sdk_methods() -> dict[str, list[str]]:
    """
    Import vastai SDK and introspect the VastAI class for public methods.

    Returns: {method_name: [list of parameter names]}
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
    for name, func in inspect.getmembers(VastAI, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue
        sig = inspect.signature(func)
        params = [
            p.name for p in sig.parameters.values()
            if p.name != "self"
        ]
        methods[name] = params

    return methods


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

    commands = {}
    for mdx_file in ref_dir.glob("*.mdx"):
        cmd_name = mdx_file.stem  # e.g., "create-instance"
        flags = _parse_mdx_params(mdx_file, param_type="flag")
        commands[cmd_name] = flags

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
    """
    content = mdx_file.read_text(errors="replace")
    params = set()

    # Mintlify <ParamField> components
    for match in re.finditer(
        r'<ParamField\s+[^>]*(?:name|path|query|body)\s*=\s*["\']([^"\']+)["\']',
        content,
    ):
        params.add(match.group(1).lstrip("-").strip())

    # Markdown table rows with flags: | `--flag` | or | --flag |
    for match in re.finditer(r'\|\s*`?(--[\w-]+)`?\s*\|', content):
        params.add(match.group(1).lstrip("-").strip())

    # Fallback: look for --flag patterns in code blocks and descriptions
    if not params:
        for match in re.finditer(r'`(--[\w-]+)`', content):
            params.add(match.group(1).lstrip("-").strip())

    return sorted(params)


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
) -> tuple[list[str], list[str]]:
    """
    Compare actual commands/methods against documented ones.

    Returns: (undocumented, stale)
    """
    actual_doc_names = {name_to_doc(name) for name in actual}
    documented_names = set(documented.keys())

    undocumented = sorted(actual_doc_names - documented_names)
    stale = sorted(documented_names - actual_doc_names)

    return undocumented, stale


def compare_params(
    actual: dict[str, list[str]],
    documented: dict[str, list[str]],
    name_to_doc: callable,
) -> dict:
    """
    For each command/method that exists in both, compare parameters.

    Returns: {name: {"missing_from_docs": [...], "stale_in_docs": [...]}}
    """
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
        stale = sorted(doc_set - actual_set)

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

    # --- CLI ---
    try:
        cli_actual = get_cli_commands()
        cli_documented = get_documented_cli_commands(docs)

        undoc, stale = compare_inventory(cli_actual, cli_documented, cli_command_to_doc_name)
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
        sdk_actual = get_sdk_methods()
        sdk_documented = get_documented_sdk_methods(docs)

        undoc, stale = compare_inventory(sdk_actual, sdk_documented, sdk_method_to_doc_name)
        report.sdk_undocumented = undoc
        report.sdk_stale = stale

        if check_params and sdk_actual and sdk_documented:
            report.sdk_param_mismatches = compare_params(
                sdk_actual, sdk_documented, sdk_method_to_doc_name,
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
