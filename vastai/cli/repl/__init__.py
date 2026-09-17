"""Interactive shell for the vast CLI (`vastai repl`).

One process, the same commands: `session.py` owns the loop, `bridge.py` runs a
line through the real parser, `completion.py` stages Tab completion and
`catalog.py` indexes the command tree for both.
"""
from vastai.cli.repl.session import run_repl  # noqa: F401
