#!/usr/bin/env python3
"""
Generate CLI command reference documentation from vast.py --help output.

This script extracts help text from all CLI commands and formats them
as Markdown for the MkDocs documentation site.

Usage:
    python scripts/generate_cli_docs.py

Output:
    docs/cli/commands.md
"""

import re
import subprocess
import sys
from pathlib import Path


def run_help(command_parts: list[str] | None = None) -> str:
    """Run vast.py with --help and capture output."""
    cmd = [sys.executable, "vast.py"]
    if command_parts:
        cmd.extend(command_parts)
    cmd.append("--help")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout


def parse_commands_from_help(help_text: str) -> list[tuple[str, str]]:
    """
    Parse command names and descriptions from main --help output.

    Returns list of (command_name, description) tuples.
    """
    commands = []
    in_commands_section = False

    for line in help_text.split("\n"):
        # Skip empty lines
        if not line.strip():
            continue

        # Detect commands section start
        if "positional arguments:" in line.lower() or "commands:" in line.lower():
            in_commands_section = True
            continue

        # Detect section end
        if line.strip() and not line.startswith(" ") and in_commands_section:
            if "optional arguments:" in line.lower() or "options:" in line.lower():
                in_commands_section = False
                continue

        # Parse command lines (indented, with description)
        if in_commands_section and line.startswith("  "):
            # Split on multiple spaces to separate command from description
            parts = re.split(r"\s{2,}", line.strip(), maxsplit=1)
            if parts and parts[0] and not parts[0].startswith("-"):
                command = parts[0].strip()
                description = parts[1].strip() if len(parts) > 1 else ""
                # Skip meta entries like {command1,command2,...}
                if not command.startswith("{"):
                    commands.append((command, description))

    return commands


def generate_command_docs() -> str:
    """Generate full CLI command reference as Markdown."""
    output = []

    # Header
    output.append("# CLI Command Reference")
    output.append("")
    output.append("This reference is auto-generated from `vastai --help` output.")
    output.append("")
    output.append('!!! tip "Regenerate this page"')
    output.append("    Run `python scripts/generate_cli_docs.py` to update this documentation.")
    output.append("")

    # Get main help
    main_help = run_help()

    # Overview section
    output.append("## Overview")
    output.append("")
    output.append("```")
    output.append(main_help.rstrip())
    output.append("```")
    output.append("")

    # Parse commands
    commands = parse_commands_from_help(main_help)

    if not commands:
        output.append('!!! warning "No commands found"')
        output.append("    Could not parse commands from --help output.")
        return "\n".join(output)

    # Categorize commands
    client_commands = []
    host_commands = []

    for cmd, desc in commands:
        if "[Host]" in desc:
            host_commands.append((cmd, desc))
        else:
            client_commands.append((cmd, desc))

    # Client commands section
    output.append("## Client Commands")
    output.append("")
    output.append("Commands for renting and managing GPU instances.")
    output.append("")

    for cmd, desc in sorted(client_commands):
        if not cmd or cmd.startswith("-"):
            continue

        output.append(f"### {cmd}")
        output.append("")
        output.append(desc if desc else "*No description*")
        output.append("")

        # Get detailed help
        cmd_parts = cmd.split()
        try:
            detailed_help = run_help(cmd_parts)
            output.append("```")
            output.append(detailed_help.rstrip())
            output.append("```")
        except subprocess.TimeoutExpired:
            output.append("*Help text timed out*")
        except Exception as e:
            output.append(f"*Error getting help: {e}*")

        output.append("")
        output.append("---")
        output.append("")

    # Host commands section
    if host_commands:
        output.append("## Host Commands")
        output.append("")
        output.append("Commands for GPU providers hosting machines on Vast.ai.")
        output.append("")

        for cmd, desc in sorted(host_commands):
            output.append(f"### {cmd}")
            output.append("")
            # Remove [Host] marker from description
            clean_desc = desc.replace("[Host]", "").strip()
            output.append(clean_desc if clean_desc else "*No description*")
            output.append("")

            cmd_parts = cmd.split()
            try:
                detailed_help = run_help(cmd_parts)
                output.append("```")
                output.append(detailed_help.rstrip())
                output.append("```")
            except subprocess.TimeoutExpired:
                output.append("*Help text timed out*")
            except Exception as e:
                output.append(f"*Error getting help: {e}*")

            output.append("")
            output.append("---")
            output.append("")

    return "\n".join(output)


def main():
    """Generate CLI docs and write to file."""
    # Ensure we're in the right directory
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    # Change to repo root so vast.py is found
    import os
    os.chdir(repo_root)

    print("Generating CLI command documentation...")
    content = generate_command_docs()

    # Write output
    output_path = repo_root / "docs" / "cli" / "commands.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    # Count commands
    command_count = content.count("### ")
    line_count = len(content.split("\n"))

    print(f"Wrote {len(content):,} bytes ({line_count:,} lines) to {output_path}")
    print(f"Documented {command_count} commands")


if __name__ == "__main__":
    main()
