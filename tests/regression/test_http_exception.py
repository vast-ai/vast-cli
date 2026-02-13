"""Missing exception handling in http_request().

The bug: session.send() has no try/except. Network errors (DNS failure,
connection refused, timeout) crash with unhandled exceptions instead of
being retried.

The fix: Wrap session.send() in try/except RequestException. Retry on
transient failures, re-raise on final attempt.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import argparse
from unittest.mock import MagicMock, patch
import pytest
import requests.exceptions


def _make_args(retry=3):
    return argparse.Namespace(retry=retry, curl=False)


@patch('vast.time.sleep')
@patch('vast.requests.Session')
def test_retries_on_connection_error(mock_session_cls, mock_sleep):
    """http_request retries on ConnectionError before re-raising."""
    from vast import http_request

    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    # First two calls raise ConnectionError, third succeeds
    success_response = MagicMock()
    success_response.status_code = 200
    mock_session.send.side_effect = [
        requests.exceptions.ConnectionError("connection refused"),
        requests.exceptions.ConnectionError("connection refused"),
        success_response,
    ]
    mock_session.prepare_request.return_value = MagicMock()

    args = _make_args(retry=3)
    # Patch ARGS global to avoid curl path
    with patch('vast.ARGS', args):
        result = http_request('GET', args, 'http://test.example.com')

    assert result.status_code == 200
    assert mock_session.send.call_count == 3
    # Should have slept twice (after first two failures)
    assert mock_sleep.call_count == 2


@patch('vast.time.sleep')
@patch('vast.requests.Session')
def test_raises_on_final_retry(mock_session_cls, mock_sleep):
    """http_request re-raises if all retries exhausted."""
    from vast import http_request

    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    # All calls raise ConnectionError
    mock_session.send.side_effect = requests.exceptions.ConnectionError("fail")
    mock_session.prepare_request.return_value = MagicMock()

    args = _make_args(retry=2)
    with patch('vast.ARGS', args):
        with pytest.raises(requests.exceptions.ConnectionError):
            http_request('GET', args, 'http://test.example.com')

    assert mock_session.send.call_count == 2
