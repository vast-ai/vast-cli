#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
#
# Compatibility shim. The CLI lives in the `vastai` package
# (see vastai/cli/main.py); this file exists only so that `python vast.py ...`
# keeps working for existing users and scripts.
#
# There is ONE source of truth for the CLI, and it is `vastai.cli.main`.
# Do NOT add command logic here.
import os
import sys

# Allow running from a bare source checkout (no `pip install vastai`): make the
# repo root importable so `import vastai` resolves to the in-tree package.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vastai.cli.main import main

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, BrokenPipeError):
        pass
