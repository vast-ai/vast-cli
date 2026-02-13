"""JSONDecodeError handling in api_call().

The bug: api_call() calls r.json() without protection. When the API returns
non-JSON content (HTML error pages, empty responses, proxy errors), this
raises JSONDecodeError and crashes the CLI.

The fix: Wrap r.json() in try/except JSONDecodeError. On failure, return
a fallback dict {"_raw_text": r.text} so callers can detect and handle
the non-JSON response gracefully.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import argparse
from unittest.mock import MagicMock, patch
import pytest


def _make_args(retry=1):
    return argparse.Namespace(
        retry=retry,
        curl=False,
        api_key="test-key",
        url="https://console.vast.ai",
        explain=False,
        raw=False,
    )


@patch('vast.http_get')
def test_api_call_returns_fallback_on_json_decode_error(mock_http_get):
    """api_call() returns {"_raw_text": ...} when .json() raises JSONDecodeError."""
    from vast import api_call, JSONDecodeError

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"<html>Bad Gateway</html>"
    mock_response.text = "<html>Bad Gateway</html>"
    mock_response.json.side_effect = JSONDecodeError("msg", "doc", 0)
    mock_response.raise_for_status.return_value = None
    mock_http_get.return_value = mock_response

    args = _make_args()
    result = api_call(args, "GET", "/test/")

    assert result is not None
    assert "_raw_text" in result
    assert result["_raw_text"] == "<html>Bad Gateway</html>"


@patch('vast.http_get')
def test_api_call_returns_json_on_valid_response(mock_http_get):
    """api_call() returns parsed JSON normally when response is valid."""
    from vast import api_call

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b'{"success": true}'
    mock_response.json.return_value = {"success": True}
    mock_response.raise_for_status.return_value = None
    mock_http_get.return_value = mock_response

    args = _make_args()
    result = api_call(args, "GET", "/test/")

    assert result == {"success": True}


@patch('vast.http_get')
def test_api_call_returns_none_for_empty_response(mock_http_get):
    """api_call() returns None when response has no content."""
    from vast import api_call

    mock_response = MagicMock()
    mock_response.status_code = 204
    mock_response.content = b""
    mock_response.raise_for_status.return_value = None
    mock_http_get.return_value = mock_response

    args = _make_args()
    result = api_call(args, "GET", "/test/")

    assert result is None


@patch('vast.http_get')
def test_api_call_no_exception_raised_on_html_response(mock_http_get):
    """api_call() does NOT raise an exception when API returns HTML."""
    from vast import api_call, JSONDecodeError

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"<html><body>502 Bad Gateway</body></html>"
    mock_response.text = "<html><body>502 Bad Gateway</body></html>"
    mock_response.json.side_effect = JSONDecodeError("Expecting value", "<html>", 0)
    mock_response.raise_for_status.return_value = None
    mock_http_get.return_value = mock_response

    args = _make_args()

    # This should NOT raise - the whole point of the fix
    try:
        result = api_call(args, "GET", "/instances/")
    except JSONDecodeError:
        pytest.fail("api_call() should not raise JSONDecodeError")

    assert "_raw_text" in result


@patch('vast.http_post')
def test_api_call_post_handles_json_decode_error(mock_http_post):
    """api_call() handles JSONDecodeError for POST requests too."""
    from vast import api_call, JSONDecodeError

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"Internal Server Error"
    mock_response.text = "Internal Server Error"
    mock_response.json.side_effect = JSONDecodeError("msg", "doc", 0)
    mock_response.raise_for_status.return_value = None
    mock_http_post.return_value = mock_response

    args = _make_args()
    result = api_call(args, "POST", "/instances/", json_body={"test": True})

    assert result is not None
    assert result["_raw_text"] == "Internal Server Error"
