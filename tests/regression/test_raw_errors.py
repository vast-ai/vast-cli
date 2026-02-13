"""Error messages in --raw mode must be valid JSON.

The bug: When --raw mode is active and an HTTPError or ValueError occurs,
the error handler prints plain text (e.g., "failed with error 500: ...").
Scripts and automation tools parsing JSON output get broken by mixed
text/JSON output.

The fix: Check args.raw in the HTTPError and ValueError exception handlers
in main(), and output a JSON object with error/status_code/msg fields.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import json
import argparse
import pytest
from unittest import mock
from io import StringIO

import requests


class TestHTTPErrorRawMode:
    """Verify HTTPError in --raw mode produces valid JSON."""

    def _make_mock_response(self, status_code, json_body=None):
        """Create a mock response for HTTPError."""
        resp = mock.MagicMock()
        resp.status_code = status_code
        if json_body is not None:
            resp.json.return_value = json_body
        else:
            resp.json.side_effect = json.JSONDecodeError("No JSON", "", 0)
        return resp

    def _run_main_with_error(self, args):
        """Run vast.main() with proper mocking, return captured stdout."""
        import vast

        captured = StringIO()
        with mock.patch.object(vast, 'ARGS', args):
            with mock.patch('vast.parser') as mock_parser:
                mock_parser.parse_args.return_value = args
                mock_parser.add_argument = mock.MagicMock()
                mock_parser.parser = mock.MagicMock()
                with mock.patch('vast.should_check_for_update', False):
                    with mock.patch('vast.TABCOMPLETE', False):
                        with mock.patch('vast.api_key_guard', 'GUARD'):
                            with mock.patch('sys.stdout', captured):
                                try:
                                    vast.main()
                                except SystemExit:
                                    pass
        return captured.getvalue().strip()

    def test_http_error_raw_mode_produces_json(self):
        """HTTPError with --raw should output valid JSON with error/status_code/msg."""
        mock_resp = self._make_mock_response(500, {"msg": "Internal server error"})
        http_error = requests.exceptions.HTTPError(response=mock_resp)

        args = argparse.Namespace(
            raw=True, func=mock.MagicMock(side_effect=http_error),
            api_key="test", url="https://test.com", explain=False,
            retry=3, full=False, curl=False, no_color=False,
        )

        output = self._run_main_with_error(args)
        parsed = json.loads(output)
        assert parsed["error"] is True
        assert parsed["status_code"] == 500
        assert parsed["msg"] == "Internal server error"

    def test_http_error_raw_mode_401_produces_json(self):
        """HTTPError 401 with --raw should output JSON with login message."""
        mock_resp = self._make_mock_response(401, json_body=None)
        http_error = requests.exceptions.HTTPError(response=mock_resp)

        args = argparse.Namespace(
            raw=True, func=mock.MagicMock(side_effect=http_error),
            api_key="test", url="https://test.com", explain=False,
            retry=3, full=False, curl=False, no_color=False,
        )

        output = self._run_main_with_error(args)
        parsed = json.loads(output)
        assert parsed["error"] is True
        assert parsed["status_code"] == 401
        assert "log in" in parsed["msg"].lower() or "sign up" in parsed["msg"].lower()

    def test_http_error_non_raw_mode_produces_text(self):
        """HTTPError without --raw should output human-readable text."""
        mock_resp = self._make_mock_response(500, {"msg": "Server error"})
        http_error = requests.exceptions.HTTPError(response=mock_resp)

        args = argparse.Namespace(
            raw=False, func=mock.MagicMock(side_effect=http_error),
            api_key="test", url="https://test.com", explain=False,
            retry=3, full=False, curl=False, no_color=False,
        )

        output = self._run_main_with_error(args)
        # Non-raw should NOT be valid JSON with error key
        assert "failed with error" in output.lower()


class TestValueErrorRawMode:
    """Verify ValueError in --raw mode produces valid JSON."""

    def _run_main_with_error(self, args):
        """Run vast.main() with proper mocking, return captured stdout."""
        import vast

        captured = StringIO()
        with mock.patch.object(vast, 'ARGS', args):
            with mock.patch('vast.parser') as mock_parser:
                mock_parser.parse_args.return_value = args
                mock_parser.add_argument = mock.MagicMock()
                mock_parser.parser = mock.MagicMock()
                with mock.patch('vast.should_check_for_update', False):
                    with mock.patch('vast.TABCOMPLETE', False):
                        with mock.patch('vast.api_key_guard', 'GUARD'):
                            with mock.patch('sys.stdout', captured):
                                try:
                                    vast.main()
                                except SystemExit:
                                    pass
        return captured.getvalue().strip()

    def test_value_error_raw_mode_produces_json(self):
        """ValueError with --raw should output valid JSON with error/msg."""
        args = argparse.Namespace(
            raw=True, func=mock.MagicMock(side_effect=ValueError("bad value")),
            api_key="test", url="https://test.com", explain=False,
            retry=3, full=False, curl=False, no_color=False,
        )

        output = self._run_main_with_error(args)
        parsed = json.loads(output)
        assert parsed["error"] is True
        assert parsed["msg"] == "bad value"

    def test_value_error_non_raw_mode_produces_text(self):
        """ValueError without --raw should print the error message as text."""
        args = argparse.Namespace(
            raw=False, func=mock.MagicMock(side_effect=ValueError("bad value")),
            api_key="test", url="https://test.com", explain=False,
            retry=3, full=False, curl=False, no_color=False,
        )

        output = self._run_main_with_error(args)
        assert output == "bad value"


class TestRawErrorHandlerLintChecks:
    """Lint-style tests to verify raw error handling exists in main()."""

    def test_httperror_handler_checks_args_raw(self):
        """The HTTPError handler in main() must check args.raw."""
        VAST_PY_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'vast.py')
        with open(VAST_PY_PATH, encoding='utf-8') as f:
            content = f.read()

        # Find the HTTPError handler section
        assert 'HTTPError' in content, "HTTPError handler must exist"
        # Find args.raw in the context of error handling
        import re
        # Look for args.raw near HTTPError handling
        http_error_section = content[content.index('HTTPError'):]
        # Limit to the next except or end of function
        next_section = http_error_section[:http_error_section.index('except ValueError')]
        assert 'args.raw' in next_section, (
            "HTTPError handler must check args.raw for JSON output"
        )

    def test_valueerror_handler_checks_args_raw(self):
        """The ValueError handler in main() must check args.raw."""
        VAST_PY_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'vast.py')
        with open(VAST_PY_PATH, encoding='utf-8') as f:
            content = f.read()

        # Find the ValueError handler in main() - the one near end of file
        # Look for the last 'except ValueError' which is in main()
        last_ve_idx = content.rindex('except ValueError')
        ve_section = content[last_ve_idx:last_ve_idx + 300]
        assert 'args.raw' in ve_section, (
            "ValueError handler in main() must check args.raw for JSON output"
        )
