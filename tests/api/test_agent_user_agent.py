"""AI coding agent detection and the User-Agent suffix (CLNT-3586)."""

import json
import os

import pytest

from vastai._user_agent import AGENT_HARNESSES, agent_suffix, build_user_agent, detect_agent_id
from vastai.utils import VERSION

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "vastai", "agent_harnesses.json")

with open(DATA_FILE) as _f:
    _DATA = json.load(_f)

# (harness id, variable, value that must detect it)
_VARIABLE_CASES = [
    (h["id"], var, "1" if pattern == "*" else pattern)
    for h in _DATA["harnesses"]
    for var, pattern in h["env"].items()
]
_NO_VARIABLE_IDS = [h["id"] for h in _DATA["harnesses"] if not h["env"]]


@pytest.mark.parametrize("harness_id,var,value", _VARIABLE_CASES)
def test_each_variable_of_each_harness_detects_it_singly(monkeypatch, harness_id, var, value):
    monkeypatch.setenv(var, value)
    assert detect_agent_id() == harness_id
    assert agent_suffix() == f" (via {harness_id})"


@pytest.mark.parametrize("harness_id", _NO_VARIABLE_IDS)
def test_harness_without_variables_is_named_through_ai_agent_only(monkeypatch, harness_id):
    assert detect_agent_id() == ""
    monkeypatch.setenv("AI_AGENT", harness_id)
    assert detect_agent_id() == harness_id


@pytest.mark.parametrize("var,required,other", [("VTCODE", "1", "0"), ("GROK_AGENT", "1", "2")])
def test_value_gated_variable_needs_its_value(monkeypatch, var, required, other):
    monkeypatch.setenv(var, other)
    assert detect_agent_id() == ""
    monkeypatch.setenv(var, required)
    assert detect_agent_id() != ""


def test_nothing_detected_gives_no_suffix():
    assert detect_agent_id() == ""
    assert agent_suffix() == ""
    assert build_user_agent("cli") == f"vastai-cli/{VERSION}"
    assert build_user_agent("sdk") == f"vastai-sdk/{VERSION}"


def test_suffix_format_is_exact(monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    assert agent_suffix() == " (via claude-code)"
    assert build_user_agent("cli") == f"vastai-cli/{VERSION} (via claude-code)"
    assert build_user_agent("sdk") == f"vastai-sdk/{VERSION} (via claude-code)"


def test_registry_order_first_match_wins(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_IS_COWORK", "1")
    assert detect_agent_id() == "cowork"
    monkeypatch.delenv("CLAUDE_CODE_IS_COWORK")
    assert detect_agent_id() == "claude-code"
    monkeypatch.setenv("CURSOR_TRACE_ID", "t")
    monkeypatch.setenv("CURSOR_AGENT", "1")
    monkeypatch.delenv("CLAUDE_CODE")
    assert detect_agent_id() == "cursor-cli"


def test_harness_beats_ai_agent(monkeypatch):
    monkeypatch.setenv("AI_AGENT", "custom-agent")
    monkeypatch.setenv("CODEX_CI", "1")
    assert detect_agent_id() == "codex"


def test_ai_agent_with_a_custom_value_is_used(monkeypatch):
    monkeypatch.setenv("AI_AGENT", "custom-agent")
    assert detect_agent_id() == "custom-agent"
    assert agent_suffix() == " (via custom-agent)"


def test_bare_agent_variable_is_ignored(monkeypatch):
    monkeypatch.setenv("AGENT", "x")
    assert detect_agent_id() == ""
    assert agent_suffix() == ""


def test_ai_agent_value_is_filtered_to_safe_characters(monkeypatch):
    monkeypatch.setenv("AI_AGENT", "my agent/v1.2_x-y!")
    assert detect_agent_id() == "myagentv1.2_x-y"


def test_ai_agent_value_is_cut_at_64_characters(monkeypatch):
    monkeypatch.setenv("AI_AGENT", "a" * 70)
    assert detect_agent_id() == "a" * 64


def test_filter_then_cut_order(monkeypatch):
    # Ten unsafe characters first: filtering before the cut keeps 64 safe ones;
    # cutting before the filter would keep 54.
    monkeypatch.setenv("AI_AGENT", "!" * 10 + "a" * 70)
    assert detect_agent_id() == "a" * 64


def test_surrounding_whitespace_is_trimmed(monkeypatch):
    monkeypatch.setenv("AI_AGENT", "  tidy-agent \n")
    assert detect_agent_id() == "tidy-agent"


@pytest.mark.parametrize("value", ["", "   ", "!!!", "///"])
def test_empty_or_fully_filtered_ai_agent_gives_no_suffix(monkeypatch, value):
    monkeypatch.setenv("AI_AGENT", value)
    assert detect_agent_id() == ""
    assert agent_suffix() == ""


@pytest.mark.parametrize("value", ["", "  "])
def test_empty_harness_variable_is_not_a_detection(monkeypatch, value):
    monkeypatch.setenv("CLAUDECODE", value)
    assert detect_agent_id() == ""


def test_sentinel_environment_value_never_reaches_the_header(monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "SENTINEL-SECRET-VALUE-123")
    monkeypatch.setenv("CODEX_THREAD_ID", "SENTINEL-SECRET-VALUE-456")
    monkeypatch.setenv("SOME_OTHER_VARIABLE", "SENTINEL-SECRET-VALUE-789")
    ua = build_user_agent("cli")
    assert "SENTINEL" not in ua
    assert ua == f"vastai-cli/{VERSION} (via claude-code)"


def test_registry_is_loaded_from_the_committed_file():
    assert [h["id"] for h in AGENT_HARNESSES] == [h["id"] for h in _DATA["harnesses"]]
