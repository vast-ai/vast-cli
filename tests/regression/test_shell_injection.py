"""No shell=True subprocess calls in vast.py.

The bug: subprocess calls with shell=True are vulnerable to command injection
(CWE-78). User-controlled data (paths, instance IDs, addresses) could be
injected into shell commands. Additionally, subprocess.getoutput() implicitly
uses shell=True.

The fix: Convert all shell=True calls to argument lists. Replace
subprocess.getoutput("echo $HOME") with os.path.expanduser("~"). Convert
get_update_command() to return a list instead of a string.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import re
import pytest


VAST_PY_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'vast.py')


class TestNoShellTrue:
    """Lint-style tests verifying no shell=True remains in vast.py."""

    def test_no_shell_true(self):
        """No shell=True subprocess calls should exist in vast.py.

        shell=True enables command injection when user-controlled data
        is passed to subprocess calls.
        """
        with open(VAST_PY_PATH, encoding='utf-8') as f:
            content = f.read()
        assert 'shell=True' not in content, (
            "Found shell=True in vast.py. All subprocess calls must use "
            "argument lists instead of shell command strings."
        )

    def test_no_subprocess_getoutput(self):
        """No subprocess.getoutput() calls should exist in vast.py.

        subprocess.getoutput() implicitly uses shell=True and is
        vulnerable to command injection.
        """
        with open(VAST_PY_PATH, encoding='utf-8') as f:
            content = f.read()
        assert 'subprocess.getoutput' not in content, (
            "Found subprocess.getoutput in vast.py. Use os.path.expanduser "
            "or subprocess.run with argument lists instead."
        )


class TestGetUpdateCommand:
    """Verify get_update_command() returns a list, not a string."""

    def test_returns_list_for_pip(self):
        """get_update_command() should return a list when is_pip_package."""
        import vast
        from unittest.mock import patch

        with patch.object(vast, 'is_pip_package', return_value=True):
            result = vast.get_update_command("1.2.3")
        assert isinstance(result, list), (
            f"get_update_command() returned {type(result).__name__}, expected list"
        )
        assert all(isinstance(item, str) for item in result), (
            "All elements of the command list must be strings"
        )
        assert "vastai==1.2.3" in result, (
            "Command list should include version-pinned package name"
        )

    def test_returns_list_for_git(self):
        """get_update_command() should return a list when not pip."""
        import vast
        from unittest.mock import patch

        with patch.object(vast, 'is_pip_package', return_value=False):
            result = vast.get_update_command("1.2.3")
        assert isinstance(result, list), (
            f"get_update_command() returned {type(result).__name__}, expected list"
        )
        assert all(isinstance(item, str) for item in result), (
            "All elements of the command list must be strings"
        )
        assert "git" in result, "Git command list should contain 'git'"

    def test_pip_command_has_no_shell_operators(self):
        """The pip command list should not contain shell operators."""
        import vast
        from unittest.mock import patch

        # Shell operators that indicate command chaining/injection
        shell_operators = ['&&', '||', '|', ';', '>', '<', '$(', '`']
        with patch.object(vast, 'is_pip_package', return_value=True):
            result = vast.get_update_command("1.2.3")
        combined = " ".join(result)
        for op in shell_operators:
            assert op not in combined, (
                f"Shell operator {op!r} found in pip command: {combined!r}"
            )

    def test_git_command_has_no_shell_operators(self):
        """The git command list should not contain && or | operators."""
        import vast
        from unittest.mock import patch

        with patch.object(vast, 'is_pip_package', return_value=False):
            result = vast.get_update_command("1.2.3")
        combined = " ".join(result)
        assert "&&" not in combined, (
            "Git command should not contain '&&' -- use separate subprocess calls"
        )
        assert "|" not in combined, (
            "Git command should not contain pipe operators"
        )
