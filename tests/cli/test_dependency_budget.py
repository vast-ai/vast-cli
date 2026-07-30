"""Fails if a heavy ML/scientific package re-enters poetry.lock's transitive closure — the way transformers did via #424."""

import pathlib
import tomllib


def _find_lock() -> pathlib.Path:
    """Walk up from this file to the repo's poetry.lock (robust to test location)."""
    for parent in pathlib.Path(__file__).resolve().parents:
        candidate = parent / "poetry.lock"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("poetry.lock not found in any parent directory")


LOCK = _find_lock()

# Packages that must never appear in the CLI's resolved dependency closure.
FORBIDDEN = {
    "transformers",
    "tokenizers",
    "huggingface-hub",
    "hf-xet",
    "hf-transfer",
    "safetensors",
    "numpy",
    "scipy",
    "pandas",
    "torch",
    "tensorflow",
    "nltk",
}


def _closure_names():
    data = tomllib.loads(LOCK.read_text(encoding="utf-8"))
    return {pkg["name"].lower() for pkg in data["package"]}


def test_no_heavy_deps_in_closure():
    intruders = sorted(_closure_names() & FORBIDDEN)
    assert not intruders, (
        f"heavy dependency re-entered the CLI closure: {intruders}. "
        "A CLI should not pull an ML/scientific stack — slim the change, or if "
        "this is genuinely required, remove it from FORBIDDEN with justification."
    )
