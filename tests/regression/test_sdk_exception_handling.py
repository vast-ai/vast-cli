"""Regression test: SDK wrapper must not use bare `except: pass`.

The bug: The SDK wrapper at sdk.py has `except: pass` which catches
SystemExit (preventing CLI functions from exiting), KeyboardInterrupt
(preventing Ctrl+C), and all errors (returning empty string '').

The fix: Catch SystemExit separately (capture exit code), catch Exception
with logging, let KeyboardInterrupt propagate.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import re


def test_no_bare_except_in_sdk():
    """sdk.py should not contain bare `except:` clauses."""
    sdk_path = os.path.join(os.path.dirname(__file__), '..', '..', 'vastai', 'sdk.py')
    with open(sdk_path, 'r') as f:
        lines = f.readlines()

    bare_excepts = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Match `except:` but not `except SomeException:` or `except (A, B):`
        if re.match(r'^except\s*:\s*$', stripped):
            bare_excepts.append(f"Line {i}: {stripped}")

    assert not bare_excepts, (
        f"Found {len(bare_excepts)} bare except: clause(s) in sdk.py:\n"
        + "\n".join(bare_excepts)
        + "\nUse specific exception types instead."
    )


def test_sdk_catches_system_exit():
    """sdk.py catches SystemExit separately from other exceptions."""
    sdk_path = os.path.join(os.path.dirname(__file__), '..', '..', 'vastai', 'sdk.py')
    with open(sdk_path, 'r') as f:
        source = f.read()

    assert 'except SystemExit' in source, (
        "sdk.py should catch SystemExit separately to handle CLI sys.exit() calls. "
        "Expected: `except SystemExit as e:`"
    )


def test_sdk_does_not_catch_keyboard_interrupt():
    """sdk.py should NOT catch KeyboardInterrupt (Ctrl+C must work)."""
    sdk_path = os.path.join(os.path.dirname(__file__), '..', '..', 'vastai', 'sdk.py')
    with open(sdk_path, 'r') as f:
        source = f.read()

    # If it catches BaseException, that would include KeyboardInterrupt
    assert 'except BaseException' not in source, (
        "sdk.py catches BaseException which includes KeyboardInterrupt. "
        "Use `except Exception` instead to allow Ctrl+C to work."
    )
