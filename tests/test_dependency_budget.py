"""Guard the CLI's dependency closure against bloat regressions.

A CLI has no business pulling an ML / scientific-computing stack. `transformers`
once slipped in via a version-bump PR (#424) and silently dragged ~138 MiB of
transitive deps (numpy, tokenizers, hf-xet, ...) into every install. This test
fails the instant any of that re-enters `poetry.lock` — the full *transitive*
closure, since that's where the weight hides.

This is the cheap, deterministic, platform-agnostic guard (Layer 1). The
installed-size ratchet in installer-ci.yml (Layer 2) is the complementary
backstop for an existing dep ballooning without a new name appearing.
"""

import pathlib
import tomllib

LOCK = pathlib.Path(__file__).resolve().parent.parent / "poetry.lock"

# Packages that must never appear in the CLI's resolved dependency closure.
# Add here (with intent) if one ever becomes genuinely required.
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
    data = tomllib.loads(LOCK.read_text())
    return {pkg["name"].lower() for pkg in data["package"]}


def test_no_heavy_deps_in_closure():
    intruders = sorted(_closure_names() & FORBIDDEN)
    assert not intruders, (
        f"heavy dependency re-entered the CLI closure: {intruders}. "
        "A CLI should not pull an ML/scientific stack — slim the change, or if "
        "this is genuinely required, remove it from FORBIDDEN with justification."
    )
