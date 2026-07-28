# CLI/SDK Documentation Verification

This guide explains how to verify that the CLI/SDK documentation in
[vast-ai/docs](https://github.com/vast-ai/docs) matches the actual `vastai`
CLI commands and SDK methods.

## Prerequisites

- Python 3.10+
- The `vastai` package installed (from this repo)
- A clone of the docs repo (or a specific branch/PR)

## Quick Start

```bash
# 1. Install the vastai package from this repo
pip install -e .

# 2. Clone the docs repo (or a specific PR branch)
git clone https://github.com/vast-ai/docs.git /tmp/docs

# To check a specific PR branch instead:
# git clone --branch <branch-name> --depth 1 https://github.com/vast-ai/docs.git /tmp/docs

# 3. Run the inventory check
python3 scripts/verify_cli_sdk_docs.py --docs-path /tmp/docs

# 4. Run with parameter-level validation
python3 scripts/verify_cli_sdk_docs.py --docs-path /tmp/docs --check-params

# 5. Output as JSON (useful for CI or sharing)
python3 scripts/verify_cli_sdk_docs.py --docs-path /tmp/docs --check-params --json > drift-report.json
```

## What It Checks

### Inventory (always runs)
- **CLI commands missing docs**: commands found in `vastai --help` with no
  matching `cli/reference/<command>.mdx` page
- **Stale CLI docs**: MDX pages for commands that no longer exist in the CLI
- **SDK methods missing docs**: public methods on the `VastAI` class with no
  matching `sdk/python/reference/<method>.mdx` page
- **Stale SDK docs**: MDX pages for methods that no longer exist in the SDK

### Parameter validation (`--check-params`)
- **Undocumented flags/params**: flags in `--help` output or method signature
  parameters not mentioned in the corresponding MDX page
- **Stale flags/params**: flags/params documented in the MDX page that no
  longer exist in the CLI/SDK

## Naming Conventions

The script converts between naming conventions for matching:

| Source | Convention | Example |
|--------|-----------|---------|
| CLI commands | kebab-case | `show-instances` |
| SDK methods | snake_case | `show_instances` |
| Doc filenames | kebab-case | `show-instances.mdx` |

**Note**: If the CLI uses a two-level command structure (e.g., `vastai show
instances`), the script parses top-level subcommands from `vastai --help`. The
doc filenames should match the flattened kebab-case form (e.g.,
`show-instances.mdx`). If this doesn't match, the script will report drift.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | No drift detected |
| 1 | Drift detected |
| 2 | Script error (missing files, import failure, etc.) |

## Interpreting Results

Not all drift is a bug:

- **CLI command restructuring** (e.g., flat → two-level commands) will show
  everything as "stale" under the old names and "undocumented" under the new
  names. This means the verification script's name-matching logic may need
  updating to match the new CLI structure.
- **`kwargs` as undocumented param** means the SDK method accepts flexible
  keyword arguments. The docs should list the commonly used kwargs, but the
  script can't extract individual kwargs from `**kwargs`.
- **Case differences** (e.g., `Id` vs `id`, `COMMAND` vs `command`) are
  flagged as mismatches. These are usually cosmetic.

## Automation

This check runs automatically via GitHub Actions
(`.github/workflows/verify-docs.yml`):

| Trigger | Behavior |
|---------|----------|
| PR that changes `vastai/` or `vastai_sdk/` | Runs check, comments on PR if drift found |
| Push to master | Runs check |
| Weekly (Monday 9am UTC) | Opens a GitHub issue if drift detected |
