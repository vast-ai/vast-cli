"""One builder for the User-Agent that the CLI and SDK send to Vast hosts.

When an AI coding agent is running the process, the header ends with
" (via <agent-id>)", so Vast can see which agents use the CLI and SDK. The agent is
found from environment variables that agent harnesses set in the processes they start
(the registry is vastai/agent_harnesses.json, copied from Hugging Face's public
agent-harnesses list, so the same ids are used across tools). Only the id is sent; the
value of a harness variable is never put in the header.

Kept to the standard library and vastai.utils so that both the SDK and the standalone
serve-vast-deployment entry point can import it without a circular import.
"""

import json
import os
import re

from vastai.utils import VERSION

_REGISTRY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_harnesses.json")

# The generic variable any tool can set to name itself. A bare AGENT is ignored: it is too
# common in unrelated environments and would label traffic with arbitrary values.
_STANDARD_VARIABLE = "AI_AGENT"
_MAX_ID_LENGTH = 64
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")


def _load_registry():
    """Read the committed registry, keeping only well-formed entries.

    A missing, unreadable or wrongly shaped file (or entry) must never break a request or
    an import: it just means that harness is not known, and AI_AGENT still works.
    """
    try:
        with open(_REGISTRY_FILE, encoding="utf-8") as f:
            entries = json.load(f)["harnesses"]
    except Exception:
        return []
    if not isinstance(entries, list):
        return []
    return [
        {"id": e["id"], "env": e["env"]}
        for e in entries
        if isinstance(e, dict)
        and isinstance(e.get("id"), str)
        and isinstance(e.get("env"), dict)
        and all(isinstance(k, str) and isinstance(v, str) for k, v in e["env"].items())
    ]


AGENT_HARNESSES = _load_registry()


def _variable_matches(name, pattern):
    """The variable counts when set to a non-blank value (surrounding whitespace is ignored)
    that fits the pattern: "*" any value, "<prefix>*" a prefix, anything else an exact value.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        return False
    if pattern == "*":
        return True
    if pattern.endswith("*"):
        return value.startswith(pattern[:-1])
    return value == pattern


def _clean_id(value):
    """Trim, keep only [A-Za-z0-9._-], then cut to 64 characters, in that order."""
    return _UNSAFE.sub("", value.strip())[:_MAX_ID_LENGTH]


def detect_agent_id():
    """Return the id of the AI coding agent running this process, or "" if none is found.

    Harnesses are checked in registry order and the first match wins; AI_AGENT is only the
    fallback when no harness matches.
    """
    for harness in AGENT_HARNESSES:
        for name, pattern in harness.get("env", {}).items():
            if _variable_matches(name, pattern):
                return harness["id"]
    return _clean_id(os.environ.get(_STANDARD_VARIABLE, ""))


def agent_suffix():
    """Return " (via <id>)" for the detected agent, or "" when none is detected."""
    agent_id = detect_agent_id()
    return f" (via {agent_id})" if agent_id else ""


def build_user_agent(client_type="sdk"):
    """Return the User-Agent for a request: vastai-<cli|sdk>/<version>[ (via <agent-id>)]."""
    return f"vastai-{client_type}/{VERSION}{agent_suffix()}"
