#!/usr/bin/env python3
"""
Generate detailed CLI documentation pages from vast.py --help output.

This script extracts help text from all CLI commands and generates
organized Markdown pages for the MkDocs documentation site.

Usage:
    python scripts/generate_detailed_cli_docs.py

Output:
    docs/cli/client/*.md
    docs/cli/host/*.md
"""

import re
import subprocess
import sys
from pathlib import Path

# Command categorization
CLIENT_CATEGORIES = {
    "instances": {
        "title": "Instance Commands",
        "description": "Commands for creating and managing GPU instances.",
        "commands": [
            "create instance", "launch instance", "destroy instance", "destroy instances",
            "start instance", "start instances", "stop instance", "stop instances",
            "reboot instance", "recycle instance", "label instance", "update instance",
            "prepay instance", "change bid", "show instance", "show instances",
            "logs", "execute"
        ]
    },
    "search": {
        "title": "Search Commands",
        "description": "Commands for searching offers, templates, and other resources.",
        "extra_content": """
## Query Syntax for String Values

When searching for values that contain spaces (like GPU names), you have two options:

1. **Underscores (recommended)** - most portable across shells:
   ```bash
   vastai search offers "gpu_name=RTX_4090"
   ```

2. **Escaped double quotes** - wrap query in single quotes, escape inner double quotes:
   ```bash
   vastai search offers 'gpu_name=\\"RTX 4090\\"'
   ```

!!! warning
    Single quotes around values do NOT work: `gpu_name='RTX 4090'` will fail.

---
""",
        "commands": [
            "search offers", "search templates", "search volumes",
            "search network-volumes", "search benchmarks", "search invoices"
        ]
    },
    "ssh": {
        "title": "SSH & File Transfer Commands",
        "description": "Commands for connecting to instances and transferring files.",
        "commands": [
            "ssh-url", "scp-url", "copy", "cloud copy", "cancel copy", "cancel sync",
            "attach ssh", "detach ssh"
        ]
    },
    "billing": {
        "title": "Billing & Account Commands",
        "description": "Commands for managing billing, invoices, and account information.",
        "commands": [
            "show user", "show invoices", "show invoices-v1", "transfer credit",
            "show deposit", "show audit-logs", "show ipaddrs",
            "create subaccount", "show subaccounts"
        ]
    },
    "volumes": {
        "title": "Volume Commands",
        "description": "Commands for managing persistent storage volumes.",
        "commands": [
            "create volume", "create network-volume", "delete volume",
            "clone volume", "show volumes"
        ]
    },
    "teams": {
        "title": "Team Commands",
        "description": "Commands for managing teams and team members.",
        "commands": [
            "create team", "destroy team", "invite member", "remove member",
            "show members", "create team-role", "show team-roles", "show team-role",
            "update team-role", "remove team-role"
        ]
    },
    "autoscaling": {
        "title": "Autoscaling Commands",
        "description": "Commands for managing autoscale/worker groups and serverless endpoints.",
        "commands": [
            "create workergroup", "delete workergroup", "update workergroup",
            "show workergroups", "get wrkgrp-logs",
            "create endpoint", "delete endpoint", "update endpoint",
            "show endpoints", "get endpt-logs"
        ]
    },
    "keys": {
        "title": "API & SSH Key Commands",
        "description": "Commands for managing API keys, SSH keys, and environment variables.",
        "commands": [
            "set api-key", "show api-key", "show api-keys", "create api-key",
            "delete api-key", "reset api-key",
            "show ssh-keys", "create ssh-key", "delete ssh-key", "update ssh-key",
            "show env-vars", "create env-var", "update env-var", "delete env-var"
        ]
    },
}

HOST_CATEGORIES = {
    "machines": {
        "title": "Machine Commands",
        "description": "Commands for managing your hosted machines on Vast.ai.",
        "commands": [
            "show machines", "show machine", "list machine", "list machines",
            "unlist machine", "delete machine", "set min-bid", "self-test machine",
            "list volume", "list volumes", "unlist volume",
            "list network-volume", "unlist network-volume",
            "set defjob", "remove defjob"
        ]
    },
    "maintenance": {
        "title": "Maintenance Commands",
        "description": "Commands for scheduling and managing machine maintenance.",
        "commands": [
            "schedule maint", "cancel maint", "show maints",
            "cleanup machine", "defrag machines"
        ]
    },
    "reports": {
        "title": "Reports & Earnings",
        "description": "Commands for viewing machine reports and earning history.",
        "commands": [
            "show earnings", "reports"
        ]
    },
    "clusters": {
        "title": "Cluster Commands (Host)",
        "description": "Commands for managing physical clusters and network disks.",
        "commands": [
            "add network-disk", "show network-disks",
            "create cluster", "delete cluster", "join cluster",
            "show clusters", "remove-machine-from-cluster",
            "create overlay", "delete overlay", "show overlays", "join overlay"
        ]
    },
}

# Additional commands not in categories (for reference)
OTHER_COMMANDS = [
    "help", "take snapshot", "show connections", "show scheduled-jobs",
    "delete scheduled-job", "create template", "delete template", "update template",
    "set user"
]


def run_help(command_parts: list[str] | None = None) -> str:
    """Run vast.py with --help and capture output."""
    cmd = [sys.executable, "vast.py"]
    if command_parts:
        cmd.extend(command_parts)
    cmd.append("--help")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout + result.stderr


def parse_help_sections(help_text: str) -> dict:
    """Parse help text into structured sections."""
    sections = {
        "usage": "",
        "description": "",
        "positional": "",
        "options": "",
        "global_options": "",
        "examples": "",
        "epilog": ""
    }

    lines = help_text.split("\n")
    current_section = None
    current_content = []
    seen_global_option = False  # Track if we've seen an actual option line

    for line in lines:
        stripped = line.strip()

        # Detect section headers
        if line.startswith("usage:"):
            if current_section:
                sections[current_section] = "\n".join(current_content)
            current_section = "usage"
            current_content = [line]
            seen_global_option = False
        elif stripped.lower() == "positional arguments:":
            if current_section:
                sections[current_section] = "\n".join(current_content)
            current_section = "positional"
            current_content = []
            seen_global_option = False
        elif stripped.lower() in ("options:", "optional arguments:"):
            if current_section:
                sections[current_section] = "\n".join(current_content)
            current_section = "options"
            current_content = []
            seen_global_option = False
        elif "global options" in line.lower():
            if current_section:
                sections[current_section] = "\n".join(current_content)
            current_section = "global_options"
            current_content = []
            seen_global_option = False
        elif stripped.lower() == "examples:":
            if current_section:
                sections[current_section] = "\n".join(current_content)
            current_section = "examples"
            current_content = []
            seen_global_option = False
        # Detect epilog: non-indented text after we've seen actual global options
        elif current_section == "global_options" and seen_global_option and stripped and not line.startswith(" "):
            sections[current_section] = "\n".join(current_content)
            current_section = "epilog"
            current_content = [line]
        elif current_section:
            current_content.append(line)
            # Track when we've seen an actual option (indented line starting with -)
            if current_section == "global_options" and line.startswith(" ") and stripped.startswith("-"):
                seen_global_option = True

    if current_section:
        sections[current_section] = "\n".join(current_content)

    return sections


def parse_options(options_text: str) -> list[dict]:
    """Parse options section into structured list."""
    options = []
    current_option = None

    for line in options_text.split("\n"):
        if not line.strip():
            continue

        # Check if this is an option line (starts with spaces then -)
        match = re.match(r"^\s+(-\S+(?:,\s*--\S+)?(?:\s+\S+)?)\s{2,}(.*)$", line)
        if match:
            if current_option:
                options.append(current_option)
            current_option = {
                "flags": match.group(1).strip(),
                "description": match.group(2).strip()
            }
        elif current_option and line.startswith("      "):
            # Continuation of description
            current_option["description"] += " " + line.strip()

    if current_option:
        options.append(current_option)

    return options


def parse_positional(positional_text: str) -> list[dict]:
    """Parse positional arguments section."""
    args = []

    for line in positional_text.split("\n"):
        if not line.strip():
            continue

        match = re.match(r"^\s+(\S+)\s{2,}(.*)$", line)
        if match:
            args.append({
                "name": match.group(1).strip(),
                "description": match.group(2).strip()
            })

    return args


def format_command_doc(cmd_name: str, help_text: str) -> str:
    """Format a single command's documentation."""
    sections = parse_help_sections(help_text)

    output = []
    output.append(f"## {cmd_name}")
    output.append("")

    # Extract description - look for text AFTER the usage line
    # In argparse with description=, the description appears after "usage: ..." line
    lines = help_text.split("\n")
    description = None
    for i, line in enumerate(lines):
        if line.startswith("usage:"):
            # Look for non-empty line after usage that's not a section header
            for j in range(i + 1, len(lines)):
                stripped = lines[j].strip()
                if stripped and not stripped.lower().startswith(("positional", "options:", "optional", "global options")):
                    description = stripped
                    break
                elif stripped.lower().startswith(("positional", "options:", "optional", "global options")):
                    # Hit a section header without finding description
                    break
            break

    if description:
        output.append(description)
        output.append("")

    # Usage - only the usage line itself, not the description that follows
    if sections["usage"]:
        usage_text = sections["usage"].replace("usage: vast.py", "vastai").replace("usage:", "").strip()
        # Only take the first line (the actual usage pattern), not subsequent description lines
        usage_line = usage_text.split("\n")[0].strip()
        output.append("```bash")
        output.append(usage_line)
        output.append("```")
        output.append("")

    # Positional arguments
    positional = parse_positional(sections.get("positional", ""))
    if positional:
        output.append("**Arguments:**")
        output.append("")
        output.append("| Argument | Description |")
        output.append("|----------|-------------|")
        for arg in positional:
            output.append(f"| `{arg['name']}` | {arg['description']} |")
        output.append("")

    # Options (excluding global)
    options = parse_options(sections.get("options", ""))
    # Filter out -h/--help
    options = [o for o in options if not o["flags"].startswith("-h")]

    if options:
        output.append("**Options:**")
        output.append("")
        output.append("| Option | Description |")
        output.append("|--------|-------------|")
        for opt in options:
            flags = opt["flags"].replace("|", "\\|")
            desc = opt["description"].replace("|", "\\|")
            output.append(f"| `{flags}` | {desc} |")
        output.append("")

    # Parse epilog content into sections
    # Combine epilog (notes before Examples:) and examples (content after Examples: header)
    epilog_part = sections.get("epilog", "")
    examples_part = sections.get("examples", "")
    if epilog_part and examples_part:
        epilog_text = epilog_part + "\nExamples:\n" + examples_part
    else:
        epilog_text = epilog_part or examples_part
    if epilog_text.strip():
        lines = epilog_text.split("\n")

        # Separate epilog into: notes (before examples), examples, post-example notes, return value
        pre_notes = []
        example_lines = []
        post_notes = []
        return_lines = []

        in_examples = False
        in_return = False
        found_examples = False

        for line in lines:
            stripped = line.strip()

            # Detect section transitions
            if stripped.lower().startswith("example"):
                in_examples = True
                in_return = False
                found_examples = True
                continue
            elif stripped.lower().startswith("return value") or stripped.lower().startswith("returns:"):
                in_return = True
                in_examples = False
                continue

            # Check if this line is an example command or comment
            is_example_line = (
                stripped.startswith("#") or
                stripped.startswith("vastai") or
                stripped.startswith("vast ") or
                stripped.startswith("$")
            )

            if is_example_line and not in_return:
                in_examples = True
                found_examples = True

            # Non-example line after examples started - back to notes
            if in_examples and not is_example_line and stripped and not stripped.startswith("{"):
                in_examples = False

            # Categorize the line
            if in_return:
                return_lines.append(line)
            elif in_examples:
                example_lines.append(line)
            elif stripped and not stripped.startswith("{") and not stripped.startswith("'"):
                if found_examples:
                    post_notes.append(stripped)
                else:
                    pre_notes.append(stripped)

        # Output pre-example notes with warning detection
        if pre_notes:
            notes_text = " ".join(pre_notes).lower()
            has_warning = any(
                word in notes_text
                for word in ["warning", "important", "caution", "irreversible", "dangerous"]
            )
            if has_warning:
                output.append("!!! warning")
                for note in pre_notes:
                    output.append(f"    {note}")
                output.append("")
            else:
                output.append("**Notes:**")
                output.append("")
                for note in pre_notes:
                    output.append(note)
                output.append("")

        # Output examples
        if example_lines:
            cleaned_examples = []
            for line in example_lines:
                line = line.replace("vast.py", "vastai").replace("vast ", "vastai ")
                cleaned_examples.append(line)

            while cleaned_examples and not cleaned_examples[-1].strip():
                cleaned_examples.pop()

            if cleaned_examples:
                output.append("**Examples:**")
                output.append("")
                output.append("```bash")
                for line in cleaned_examples:
                    output.append(line)
                output.append("```")
                output.append("")

        # Output post-example notes (tips, additional info)
        if post_notes:
            output.append("!!! tip")
            for note in post_notes:
                output.append(f"    {note}")
            output.append("")

        # Output return value
        if return_lines:
            cleaned_return = [line for line in return_lines if line.strip()]
            if cleaned_return:
                output.append("**Return Value:**")
                output.append("")
                output.append("```json")
                for line in cleaned_return:
                    output.append(line)
                output.append("```")
                output.append("")

    output.append("---")
    output.append("")

    return "\n".join(output)


def generate_category_page(category_info: dict, commands_help: dict) -> str:
    """Generate a full category page."""
    output = []

    output.append(f"# {category_info['title']}")
    output.append("")
    output.append(category_info['description'])
    output.append("")

    # Add extra content if present (e.g., query syntax notes for search)
    if "extra_content" in category_info:
        output.append(category_info["extra_content"])

    for cmd in category_info["commands"]:
        if cmd in commands_help:
            output.append(format_command_doc(cmd, commands_help[cmd]))

    output.append("## See Also")
    output.append("")
    output.append("- [Full Command Reference](../commands.md) - Complete help text for all commands")
    output.append("")

    return "\n".join(output)


def main():
    """Generate all detailed CLI documentation pages."""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    import os
    os.chdir(repo_root)

    print("Fetching help for all commands...")

    # Get all command help
    all_commands = set()
    for cat in CLIENT_CATEGORIES.values():
        all_commands.update(cat["commands"])
    for cat in HOST_CATEGORIES.values():
        all_commands.update(cat["commands"])

    commands_help = {}
    for cmd in sorted(all_commands):
        cmd_parts = cmd.split()
        try:
            help_text = run_help(cmd_parts)
            commands_help[cmd] = help_text
            print(f"  Got help for: {cmd}")
        except Exception as e:
            print(f"  Error getting help for {cmd}: {e}")

    # Generate client pages
    client_dir = repo_root / "docs" / "cli" / "client"
    client_dir.mkdir(parents=True, exist_ok=True)

    print("\nGenerating client documentation...")
    for filename, category in CLIENT_CATEGORIES.items():
        content = generate_category_page(category, commands_help)
        output_path = client_dir / f"{filename}.md"
        output_path.write_text(content, encoding="utf-8")
        print(f"  Wrote {output_path}")

    # Generate host pages
    host_dir = repo_root / "docs" / "cli" / "host"
    host_dir.mkdir(parents=True, exist_ok=True)

    print("\nGenerating host documentation...")
    for filename, category in HOST_CATEGORIES.items():
        content = generate_category_page(category, commands_help)
        output_path = host_dir / f"{filename}.md"
        output_path.write_text(content, encoding="utf-8")
        print(f"  Wrote {output_path}")

    print("\nDone!")


if __name__ == "__main__":
    main()
