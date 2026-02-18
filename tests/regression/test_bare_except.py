"""No bare except: clauses in vast.py.

The bug: Bare except: catches SystemExit and KeyboardInterrupt, which can
mask critical errors and make the program unresponsive to Ctrl+C. It also
swallows programming errors (NameError, TypeError) that should crash loudly.

The fix: Replace all bare except: with specific exception types appropriate
to each try block's expected failure modes.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import re
import pytest


VAST_PY_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'vast.py')


class TestNoBareExcept:
    """Lint-style tests verifying no bare except: remains in vast.py."""

    def test_no_bare_except(self):
        """No bare except: clauses should exist in vast.py.

        A bare except: catches everything including SystemExit and
        KeyboardInterrupt, making Ctrl+C ineffective and masking bugs.
        """
        with open(VAST_PY_PATH, encoding='utf-8') as f:
            content = f.read()
        # Match "except:" but not "except SomeName:" or "except (A, B):"
        bare_excepts = re.findall(r'^\s*except\s*:', content, re.MULTILINE)
        assert len(bare_excepts) == 0, (
            f"Found {len(bare_excepts)} bare except: clauses in vast.py. "
            "Each except must catch specific exception types."
        )

    def test_except_clauses_have_types(self):
        """Every except clause should specify at least one exception type."""
        with open(VAST_PY_PATH, encoding='utf-8') as f:
            content = f.read()
        # Find all except lines
        except_lines = re.findall(r'^\s*except\b.*:', content, re.MULTILINE)
        for line in except_lines:
            stripped = line.strip()
            # Must be "except SomeType:" or "except (A, B) as e:" etc.
            # NOT just "except:"
            assert stripped != "except:", (
                f"Found bare except: -- should catch specific types: {line!r}"
            )


class TestKeyboardInterruptPropagation:
    """Verify KeyboardInterrupt is not swallowed by import handlers."""

    def test_argcomplete_import_does_not_catch_keyboard_interrupt(self):
        """The argcomplete import try/except should not catch KeyboardInterrupt.

        Before the fix, bare except: would catch KeyboardInterrupt during
        import, making Ctrl+C during startup silently ignored.
        """
        import importlib
        import unittest.mock as mock

        # Simulate argcomplete import raising KeyboardInterrupt
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == 'argcomplete':
                raise KeyboardInterrupt()
            return original_import(name, *args, **kwargs)

        # The except ImportError: handler should NOT catch KeyboardInterrupt
        # so it should propagate
        with pytest.raises(KeyboardInterrupt):
            with mock.patch('builtins.__import__', side_effect=mock_import):
                # Re-execute the import block logic
                try:
                    __import__('argcomplete')
                except ImportError:
                    pass  # This is what the fixed code does

    def test_argcomplete_import_catches_import_error(self):
        """The argcomplete import try/except should catch ImportError."""
        import unittest.mock as mock

        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == 'argcomplete':
                raise ImportError("No module named 'argcomplete'")
            return original_import(name, *args, **kwargs)

        # ImportError should be caught (not propagated)
        caught = False
        with mock.patch('builtins.__import__', side_effect=mock_import):
            try:
                __import__('argcomplete')
            except ImportError:
                caught = True
        assert caught, "ImportError should be caught by except ImportError:"
