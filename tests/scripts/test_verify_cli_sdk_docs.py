"""
Regression tests for scripts/verify_cli_sdk_docs.py.

Every case here is a false positive that the drift checker used to report. Taken
together they were loud enough that the weekly run was permanently red, which is
what led to the docs pipeline being reverted -- the checker was reporting
correct documentation as drift.

These exercise the pure parsing/comparison helpers only, so they need neither an
installed `vastai` console script nor a clone of the docs repo.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def _load_verifier():
    path = SCRIPTS_DIR / "verify_cli_sdk_docs.py"
    spec = importlib.util.spec_from_file_location("verify_cli_sdk_docs", path)
    module = importlib.util.module_from_spec(spec)
    # Register before exec: the module defines dataclasses, and @dataclass
    # resolves annotations through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verifier = _load_verifier()


# ---------------------------------------------------------------------------
# Policy constants are read from the generator, not duplicated
# ---------------------------------------------------------------------------

def test_reads_policy_constants_from_the_generator():
    """Both scripts must apply one definition of each policy."""
    excluded = verifier.get_excluded_names()
    globals_ = verifier.get_global_cli_options()

    assert "add-network-disk" in excluded
    assert {"url", "retry", "raw", "explain", "api_key", "no_color"} <= globals_


def test_missing_generator_constant_warns_but_does_not_crash(monkeypatch, tmp_path, capsys):
    """A verification tool must still run if the generator is unreadable."""
    monkeypatch.setattr(verifier, "GENERATOR_PATH", tmp_path / "absent.py")

    assert verifier._generator_constant("EXCLUDED_NAMES", "consequence text") == set()
    assert "WARNING" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# `vastai --help` parsing
# ---------------------------------------------------------------------------

GROUPED_HELP = """\
usage: vastai [-h] command ...

positional arguments:
  command

Instances:
  show instances                Display current instances
  create instance               Create a new instance
  copy                          Copy directories between instances

Billing & account:
  show invoices                 Show invoices

options:
  -h, --help                    show this help message and exit

Use 'vastai COMMAND --help' for more info about a command. AI agent? See https://example.com/SKILL.md
"""


def test_group_headings_are_not_commands():
    """
    The CLI groups its help output. Those headings sit in the same column as
    commands and were being scraped as commands named "Instances:", "options:".
    """
    parsed = verifier._parse_subcommands(GROUPED_HELP)
    names = {"-".join(p) for p in parsed}

    assert names == {"show-instances", "create-instance", "copy", "show-invoices"}


def test_trailing_prose_is_not_a_command():
    """The footer line used to become a command name of its own."""
    parsed = verifier._parse_subcommands(GROUPED_HELP)

    assert not any("Use" in part or "http" in part for parts in parsed for part in parts)


# ---------------------------------------------------------------------------
# Per-command flag parsing
# ---------------------------------------------------------------------------

WORKERGROUP_HELP = """\
usage: vastai create workergroup [-h] [--launch_args LAUNCH_ARGS]

options:
  -h, --help                     show this help message and exit
  --launch_args LAUNCH_ARGS      launch args string, ex: "--onstart onstart.sh --env '-e A=b' --image someimage --disk 64"
  --test_workers TEST_WORKERS    number of test workers
  --url URL                      server REST API URL

Example: vastai create workergroup --template_hash HASH --endpoint_name "LLama"
"""


def test_flags_quoted_inside_help_text_are_ignored():
    """
    --launch_args' description embeds an example containing four other flags.
    Scanning the whole help text reported them as real options of this command.
    """
    flags = verifier._parse_flags(WORKERGROUP_HELP)

    assert set(flags) == {"--launch_args", "--test_workers", "--url"}


def test_flags_in_epilog_examples_are_ignored():
    """--template_hash/--endpoint_name appear only in the trailing Example line."""
    flags = verifier._parse_flags(WORKERGROUP_HELP)

    assert "--template_hash" not in flags
    assert "--endpoint_name" not in flags


def test_global_options_are_dropped_from_help():
    """
    Globals are inherited by every command and documented once per page, so
    including them reported the same flags as undocumented on every command.
    """
    flags = verifier._parse_flags(WORKERGROUP_HELP, {"url", "retry", "no_color"})

    assert "--url" not in flags
    assert "--launch_args" in flags


def test_global_option_matching_is_dash_insensitive():
    """`--no-color` in help output vs `no_color` in the parser's dest list."""
    flags = verifier._parse_flags("options:\n  --no-color   disable color\n", {"no_color"})

    assert flags == []


# ---------------------------------------------------------------------------
# MDX parsing
# ---------------------------------------------------------------------------

CLI_PAGE = """\
## Arguments

<ParamField path="id" type="integer" required>
The instance id.
</ParamField>

<ParamField path="--type" type="string" default="on-demand">
Offer type.
</ParamField>

## Global Options

| Option | Description |
| --- | --- |
| `--raw` | Output machine-readable JSON |
"""


def test_markdown_table_separator_is_not_a_parameter():
    """`| --- | --- |` parsed to a parameter with an empty name."""
    params = verifier._parse_mdx_params_from_text(CLI_PAGE, param_type="flag")

    assert "" not in params


def test_positional_arguments_excluded_from_cli_flag_comparison():
    """
    CLI pages document positionals as ParamFields, but the code-side inventory
    is scraped from `--flags` and can never contain one, so returning them made
    every command with a positional report it as stale documentation.
    """
    params = verifier._parse_mdx_params_from_text(CLI_PAGE, param_type="flag")

    assert "id" not in params
    assert "type" in params


def test_sdk_pages_keep_non_flag_parameters():
    """SDK ParamFields are plain names; the flag filter must not apply."""
    page = '<ParamField path="instance_id" type="integer">The id.</ParamField>'
    params = verifier._parse_mdx_params_from_text(page, param_type="param")

    assert params == ["instance_id"]


# ---------------------------------------------------------------------------
# Inventory comparison
# ---------------------------------------------------------------------------

def test_policy_excluded_commands_are_not_reported_missing():
    actual = {"create-instance": [], "add-network-disk": []}
    documented = {"create-instance": []}

    undocumented, stale = verifier.compare_inventory(
        actual, documented, lambda n: n, {"add-network-disk"},
    )

    assert undocumented == []
    assert stale == []


def test_policy_excluded_command_is_reported_if_actually_published():
    """
    Suppression is one-directional. A page we deliberately never generate that
    shows up in the docs repo anyway is a real problem worth reporting.
    """
    actual = {"add-network-disk": []}
    documented = {"add-network-disk": []}

    undocumented, stale = verifier.compare_inventory(
        actual, documented, lambda n: n, {"add-network-disk"},
    )

    assert undocumented == []
    assert stale == ["add-network-disk"]


def test_genuinely_missing_and_stale_pages_still_reported():
    actual = {"create-instance": [], "brand-new": []}
    documented = {"create-instance": [], "long-gone": []}

    undocumented, stale = verifier.compare_inventory(actual, documented, lambda n: n)

    assert undocumented == ["brand-new"]
    assert stale == ["long-gone"]


# ---------------------------------------------------------------------------
# Parameter comparison
# ---------------------------------------------------------------------------

def test_open_signature_suppresses_stale_params_only():
    """
    Methods ending in **kwargs do not enumerate what they accept; the generator
    fills those parameters in from the matching CLI command. Calling them stale
    flagged correct documentation -- this was the bulk of the parameter noise.
    """
    actual = {"update_endpoint": ["id"]}
    documented = {"update-endpoint": ["id", "cold_mult", "min_load"]}

    mismatches = verifier.compare_params(
        actual, documented, verifier.sdk_method_to_doc_name, {"update_endpoint"},
    )

    assert mismatches == {}


def test_open_signature_still_reports_missing_params():
    """Suppression covers extra documented params, never absent ones."""
    actual = {"update_endpoint": ["id", "undocumented_arg"]}
    documented = {"update-endpoint": ["id", "cold_mult"]}

    mismatches = verifier.compare_params(
        actual, documented, verifier.sdk_method_to_doc_name, {"update_endpoint"},
    )

    assert mismatches == {
        "update-endpoint": {"missing_from_docs": ["undocumented_arg"]}
    }


def test_closed_signature_still_reports_stale_params():
    actual = {"delete_instance": ["id"]}
    documented = {"delete-instance": ["id", "removed_param"]}

    mismatches = verifier.compare_params(
        actual, documented, verifier.sdk_method_to_doc_name, set(),
    )

    assert mismatches == {"delete-instance": {"stale_in_docs": ["removed_param"]}}


# ---------------------------------------------------------------------------
# SDK introspection
# ---------------------------------------------------------------------------

def test_variadic_markers_are_not_treated_as_parameters():
    """
    inspect.signature reports **kwargs as a parameter named "kwargs", so the
    checker demanded a documented parameter literally called "kwargs" on every
    method that takes them.
    """
    methods, open_signatures = verifier.get_sdk_methods()

    assert methods, "expected to introspect at least one SDK method"
    for name in open_signatures:
        assert "kwargs" not in methods[name], f"{name} still reports kwargs as a parameter"

    # Filtering is by parameter kind, not by name: create_instance takes a real
    # keyword parameter called args (the container arguments).
    assert "args" in methods["create_instance"]

    assert open_signatures, "expected at least one **kwargs method"
    assert open_signatures <= set(methods)
