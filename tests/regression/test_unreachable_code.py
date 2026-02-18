"""No unreachable code after raise_for_status().

The bug: 19 functions had `if (r.status_code == 200):` guards immediately
after `r.raise_for_status()`. Since raise_for_status() raises HTTPError for
non-2xx responses, the status_code check was always True and the `else` branch
(printing "failed with error {r.status_code}") was unreachable dead code.

The fix: Remove the redundant status_code == 200 wrapper, de-indent the
success path, and remove the unreachable else branches. API-level success
checks (rj.get("success")) are preserved since those check the JSON body,
not the HTTP status.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import re
import argparse
import pytest
from unittest import mock
from unittest.mock import MagicMock, patch
from io import StringIO

VAST_PY_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'vast.py')


# --------------------------------------------------------------------------- #
# Lint-style tests #
# --------------------------------------------------------------------------- #

class TestNoUnreachableStatusCheck:
    """Ensure no status_code == 200 checks follow raise_for_status()."""

    def test_no_status_check_after_raise_for_status(self):
        """Pattern: raise_for_status() followed within 3 lines by status_code == 200."""
        with open(VAST_PY_PATH, encoding='utf-8') as f:
            content = f.read()
        # Match raise_for_status() followed (within a few lines) by status_code == 200
        pattern = r'raise_for_status\(\)\s*\n(?:\s*\n)*\s*if\s*\(?r\.status_code\s*==\s*200'
        matches = re.findall(pattern, content)
        assert len(matches) == 0, (
            f"Found {len(matches)} unreachable status_code == 200 checks after "
            f"raise_for_status(). These are unreachable and should be removed."
        )

    def test_no_status_check_after_raise_for_status_response_var(self):
        """Same pattern but with 'response' variable name."""
        with open(VAST_PY_PATH, encoding='utf-8') as f:
            content = f.read()
        pattern = r'raise_for_status\(\)\s*\n(?:\s*\n)*\s*if\s*\(?response\.status_code\s*==\s*200'
        matches = re.findall(pattern, content)
        assert len(matches) == 0, (
            f"Found {len(matches)} unreachable status_code == 200 checks (response var) "
            f"after raise_for_status()."
        )

    def test_no_unreachable_failed_with_error_after_unconditional_raise(self):
        """The 'failed with error' message should not appear after an
        *unconditional* raise_for_status() call (same indentation as function body).
        Conditional raise_for_status() calls (inside if blocks) are excluded."""
        with open(VAST_PY_PATH, encoding='utf-8') as f:
            lines = f.readlines()

        # Find unconditional raise_for_status lines (indented exactly 4 spaces,
        # i.e., at function-body level, not nested inside an if/else)
        rfs_indices = []
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            if 'raise_for_status()' in stripped and not stripped.lstrip().startswith('#'):
                # Check indentation: unconditional means base function indent (4 spaces)
                indent = len(line) - len(line.lstrip())
                if indent == 4:
                    rfs_indices.append(i)

        for rfs_idx in rfs_indices:
            # Check within 20 lines after raise_for_status for the dead pattern
            for offset in range(1, 20):
                check_idx = rfs_idx + offset
                if check_idx >= len(lines):
                    break
                line = lines[check_idx]
                # If we hit a new function def or decorator, stop scanning
                if re.match(r'^def\s+', line) or re.match(r'^@', line):
                    break
                if 'failed with error {r.status_code}' in line:
                    assert False, (
                        f"Line {check_idx + 1}: Found unreachable 'failed with error' "
                        f"message after unconditional raise_for_status() at line {rfs_idx + 1}"
                    )


# --------------------------------------------------------------------------- #
# Functional tests #
# --------------------------------------------------------------------------- #

class TestStartInstanceBehavior:
    """Verify start_instance works correctly after unreachable code removal."""

    @patch('vast.http_put')
    def test_success_prints_message(self, mock_put, capsys):
        """When API returns 200 with success=True, print starting message."""
        import vast

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_put.return_value = mock_response

        args = argparse.Namespace(
            api_key="test-key", url="https://console.vast.ai",
            retry=3, raw=False, explain=False
        )

        result = vast.start_instance(12345, args)

        assert result is True
        captured = capsys.readouterr()
        assert "starting instance" in captured.out

    @patch('vast.http_put')
    def test_api_failure_prints_msg(self, mock_put, capsys):
        """When API returns 200 with success=False, print the error msg."""
        import vast

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"success": False, "msg": "instance not found"}
        mock_put.return_value = mock_response

        args = argparse.Namespace(
            api_key="test-key", url="https://console.vast.ai",
            retry=3, raw=False, explain=False
        )

        result = vast.start_instance(12345, args)

        assert result is True
        captured = capsys.readouterr()
        assert "instance not found" in captured.out

    @patch('vast.http_put')
    def test_http_error_raises(self, mock_put):
        """When API returns 500, raise_for_status raises HTTPError."""
        import vast
        import requests

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500 Server Error"
        )
        mock_put.return_value = mock_response

        args = argparse.Namespace(
            api_key="test-key", url="https://console.vast.ai",
            retry=3, raw=False, explain=False
        )

        with pytest.raises(requests.exceptions.HTTPError):
            vast.start_instance(12345, args)

    @patch('vast.http_put')
    def test_missing_msg_uses_default(self, mock_put, capsys):
        """When API returns success=False without msg, use default error."""
        import vast

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"success": False}
        mock_put.return_value = mock_response

        args = argparse.Namespace(
            api_key="test-key", url="https://console.vast.ai",
            retry=3, raw=False, explain=False
        )

        vast.start_instance(12345, args)

        captured = capsys.readouterr()
        assert "Unknown error" in captured.out


class TestDestroyInstanceBehavior:
    """Verify destroy_instance preserves raw mode path after refactor."""

    @patch('vast.http_del')
    def test_raw_mode_returns_json(self, mock_del):
        """In raw mode, destroy_instance returns parsed JSON."""
        import vast

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_del.return_value = mock_response

        args = argparse.Namespace(
            api_key="test-key", url="https://console.vast.ai",
            retry=3, raw=True, explain=False
        )

        result = vast.destroy_instance(12345, args)
        assert result == {"success": True}

    @patch('vast.http_del')
    def test_non_raw_prints_destroying(self, mock_del, capsys):
        """In non-raw mode, destroy_instance prints 'destroying instance'."""
        import vast

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_del.return_value = mock_response

        args = argparse.Namespace(
            api_key="test-key", url="https://console.vast.ai",
            retry=3, raw=False, explain=False
        )

        vast.destroy_instance(12345, args)

        captured = capsys.readouterr()
        assert "destroying instance" in captured.out
