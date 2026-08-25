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

A clean run means the report is empty and the exit code is 0. Running the
checker against the generator's own output is expected to produce exactly that,
and `tests/scripts/test_verify_cli_sdk_docs.py` pins the behaviour, so anything
reported is worth reading rather than assuming it is noise.

What the checker deliberately does *not* report:

- **Policy-excluded commands.** `EXCLUDED_NAMES` in
  `generate_cli_sdk_docs.py` lists surface we never publish (the
  network-volume commands). Absent pages for those are correct. If such a page
  *does* exist in the docs repo it is still reported, as stale — it should be
  removed.
- **Global options.** `--url`, `--raw`, `--api_key` and friends are inherited by
  every command and rendered once per page in a "Global Options" table, not as
  per-command parameters.
- **Extra parameters on `**kwargs` methods.** Those signatures do not enumerate
  what they accept, and the generator fills the parameters in from the matching
  CLI command, so extra documented parameters cannot be judged stale. Genuinely
  *missing* parameters are still reported.

  This carve-out is narrow on purpose. It used to cover `create_instance`,
  `create_instances`, `launch_instance` and `update_template`, which is how 50
  parameters that raise `TypeError` stayed published. Those have closed
  signatures now and are checked like anything else. What the verifier
  still declines to judge, `tests/scripts/test_sdk_documented_params.py` checks
  instead: it binds every published parameter against the real method with the
  transport stubbed, so a fabricated parameter on a genuinely open signature
  fails CI there. Closing a signature is always preferable to relying on the
  carve-out.
- **Positional arguments, on CLI parameter checks.** The code-side inventory is
  scraped from `--help` flags, so positionals only ever appear on the docs side.

Still worth a human eye:

- **CLI command restructuring** (e.g., flat → two-level commands) will show
  everything as "stale" under the old names and "undocumented" under the new
  names. This means the verification script's name-matching logic may need
  updating to match the new CLI structure.
- **Case differences** (e.g., `Id` vs `id`, `COMMAND` vs `command`) are
  flagged as mismatches. These are usually cosmetic.

The checker invokes the `vastai` console script next to the interpreter running
it, not whatever `vastai` is first on `PATH`. Run it with the interpreter of the
environment you want to check — a stale global install otherwise gets compared
against the current SDK and every difference is reported as drift.

## Automation

**Currently manual — run the commands above yourself.**

The GitHub Actions workflows that ran this check on every PR, and that
generated and pushed docs to [vast-ai/docs](https://github.com/vast-ai/docs),
are parked on the `SO-80--reland-cli-sdk-docs` branch and are deliberately not
on `master`. They were pulled because the docs baseline had drifted far enough
that every run produced a full-rewrite pull request that nobody could review.

The scripts in this directory are the durable part and stay on `master`, so
drift can be checked on demand at any time. When the docs baseline has been
regenerated and a typical run yields a small diff, re-land the workflows from
that branch. It restores:

| Trigger | Behavior |
|---------|----------|
| PR that changes `vastai/` or `vastai_sdk/` | Runs check, comments on PR if drift found |
| Push to master | Runs check |
| Weekly (Monday 9am UTC) | Opens a GitHub issue if drift detected |
