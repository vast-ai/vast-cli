"""Pins that do not derive their expectations from vastai/agent_harnesses.json.

A wrong copy of the data file (a dropped harness, a swapped order, a misspelled variable)
must not pass because the detection tests were generated from the same file.
"""

import json
import os

from vastai._user_agent import AGENT_HARNESSES, detect_agent_id

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "vastai", "agent_harnesses.json")


def _ids():
    return [h["id"] for h in AGENT_HARNESSES]


def test_registry_has_forty_harnesses():
    assert len(AGENT_HARNESSES) == 40


def test_order_that_decides_ties():
    ids = _ids()
    assert ids.index("cowork") < ids.index("claude-code")
    assert ids.index("cursor-cli") < ids.index("cursor")


def test_ids_without_variables_are_pinned_by_count_only():
    # hi and sandbase-harness have no variables, so only AI_AGENT can name them.
    by_id = {h["id"]: h for h in AGENT_HARNESSES}
    assert by_id["hi"]["env"] == {}
    assert by_id["sandbase-harness"]["env"] == {}


def test_five_variables_named_by_the_ticket(monkeypatch):
    for var, expected in [
        ("CLAUDECODE", "claude-code"),
        ("CODEX_SANDBOX", "codex"),
        ("CODEX_THREAD_ID", "codex"),
        ("CURSOR_AGENT", "cursor-cli"),
        ("GEMINI_CLI", "gemini-cli"),
        ("CLAUDE_CODE", "claude-code"),
        ("CODEX_CI", "codex"),
    ]:
        monkeypatch.setenv(var, "1")
        assert detect_agent_id() == expected
        monkeypatch.delenv(var)


def test_value_gated_harnesses_are_pinned():
    by_id = {h["id"]: h for h in AGENT_HARNESSES}
    assert by_id["vtcode"]["env"] == {"VTCODE": "1"}
    assert by_id["grok-build"]["env"]["GROK_AGENT"] == "1"


def test_fixture_list_matches_the_data_file(agent_env_var_names):
    with open(DATA_FILE) as f:
        data = json.load(f)
    in_file = {var for h in data["harnesses"] for var in h["env"]} | {"AI_AGENT", "AGENT"}
    assert set(agent_env_var_names) == in_file
    assert len(agent_env_var_names) == len(set(agent_env_var_names))
    assert data["source"]["commit"] == "b0f65c20e8c1"
