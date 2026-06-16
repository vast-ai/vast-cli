# Design: One CLI Source of Truth (`vast.py` → shim over `vastai`)

## Problem

The repo ships **two parallel CLI implementations** that do not share code:

| | Legacy | Refactored |
|---|---|---|
| File / package | `vast.py` (root, ~9.8k lines) | `vastai/` package (`vastai/cli/…`) |
| Invocation | `python vast.py …` | `vastai …` (pip entry point) |
| Entry point | own `main()` at `vast.py:9736` | `vastai = "vastai.cli.main:main"` (`pyproject.toml`) |
| Argparse, commands, helpers | self-contained | `vastai/cli/{main,parser,util,display}.py` + `commands/` |
| Imports the other? | **No** — `grep "from vastai" vast.py` is empty | n/a |

`vast.py` already carries the header `# DEPRECATED: This file is kept for
backwards compatibility. Please use the vastai package instead.` — but it is
not a shim. It is a **full second copy** of the CLI with its own argparse tree,
its own `_get_gpu_names()`, its own error handling. A fix landed in one is not
present in the other unless ported by hand.

This is the source-of-truth split. Symptoms it produces:

- `python vast.py <cmd>` and `vastai <cmd>` can behave differently for the same
  command (different code paths, different bug-fix state).
- It is unclear which copy a given helper (e.g. the GPU-name/`gpu_types`
  catalog logic) is the live one, so claims about "the CLI" vs "the SDK" are
  ambiguous — the ambiguity is itself a symptom of two copies.
- Contributors don't know where to make a change, so some land in `vast.py`,
  some in `vastai/`, and the two drift further apart.

## Goal

**One source of truth: the `vastai` package.** `python vast.py …` must keep
working unchanged for existing users and scripts, but only as a **thin shim**
that delegates into `vastai.cli.main` — it contains no command logic of its own.

Non-goal: removing `python vast.py`. The team direction is
`pip install vastai`, but a hard break would strip the fallback people rely on
today. The shim keeps the invocation alive while collapsing the second
implementation.

## Why a shim, and why not just delete `vast.py`

- Both already produce identical output where covered — verified: `python3 vast.py --version` and `python3 -m vastai.cli.main --version` both print `1.0.13`.
- People (including us) type `python vast.py` as the "I know this works"
  fallback, and CI / docs / muscle memory reference it. Deleting it breaks them.
- A shim is ~10 lines. It cannot drift, because it holds no logic.

## Parity: already met

A shim is only safe once the package covers every *live* command in `vast.py`.
Command-coverage diff (command functions `xxx__yyy`, old vs. new):

- New package has **more** commands than legacy (e.g. `metrics gpu*`,
  `run benchmarks`, `*_price_increase`, `start/stop deployment`,
  `create instances`, `get endpt-workers`).
- The diff initially flagged three commands as "old-only" — `create account`
  (`create__account`), `generate pdf-invoices` (`generate__pdf_invoices`), and
  `vm copy` (`vm__copy`). On inspection **all three are already dead code in
  `vast.py`**: `create__account` and `generate__pdf_invoices` are
  commented-out, and `vm__copy` is wrapped in a `'''…'''` string literal. None
  is a registered command, so none is reachable from `python vast.py`.

There are therefore **no live commands** in `vast.py` that the package lacks.
The shim can land without porting anything.

## Plan

1. **(done) Confirm parity.** No live command exists in `vast.py` that the
   package lacks (the three apparent gaps are dead code — see above).
2. **(done) Replace `vast.py` with a shim** (see below). Preserves the
   `# PYTHON_ARGCOMPLETE_OK` marker so shell tab-completion via
   `register-python-argcomplete vast.py` keeps working, and preserves the
   `KeyboardInterrupt`/`BrokenPipeError` swallow in the `__main__` guard. The
   shim does `from vastai.cli.main import main` — the same import the `vastai`
   entry point uses — so the two invocations run identical code (and the shim
   is more correct than `python -m vastai.cli.main`, which hits the `-m`
   double-import gotcha and registers no commands).
3. **(done) No dangling references.** Nothing in `scripts/`, tests, or docs
   imports symbols *from* `vast.py`, so gutting the body breaks no callers.
4. **(follow-up) Docs.** README / `vastai/SKILL.md`: document `vastai` as
   canonical, note `python vast.py` is a supported compatibility shim.

## Proposed shim (`vast.py`)

```python
#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
#
# Compatibility shim. The CLI lives in the `vastai` package
# (vastai/cli/main.py); this file only exists so `python vast.py ...`
# keeps working. Do NOT add command logic here — there is one source
# of truth, and it is `vastai.cli.main`.
import os
import sys

# Run from a source checkout without an install: make the repo root importable
# so `import vastai` resolves to the in-tree package.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vastai.cli.main import main

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, BrokenPipeError):
        pass
```

Notes:
- The `sys.path.insert` makes the shim work in a bare `git clone` with no
  `pip install` — the exact "I know this'll work" case. When `vastai` is
  installed, the in-tree package still wins, which is what a checkout wants.
- `argcomplete` is driven inside `vastai.cli.main.main()` already, so the
  marker plus delegation is sufficient; no completer wiring belongs in the shim.

## Risks / open questions

- **Hidden importers of `vast.py`.** Anything doing `from vast import X` (tests,
  internal scripts, notebooks) breaks when the body is gutted. Must grep the
  org, not just this repo, before deleting the bodies.
- **The 3 missing commands** may be intentionally dead. Confirm with owners
  rather than porting blindly — `create account` in particular may be obsolete.
- **Tab-completion parity.** Legacy `vast.py` builds completers in its own
  `main()`; verify the package's `set_completers()` covers the same fields.

## Done when

- `vast.py` contains no command/argparse logic — only the delegation shim.
- Old command set ⊆ new command set (diff is empty in the old→new direction).
- `python vast.py <cmd>` and `vastai <cmd>` run the *same code* for every `cmd`.
