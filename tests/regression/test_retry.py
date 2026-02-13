"""Incomplete retry logic -- only retries on HTTP 429.

The bug: http_request() only retries when the server returns 429 (rate limit).
Transient 5xx errors (502, 503, 504) and connection failures cause immediate
command failure instead of being retried.

The fix: Expand retry to cover {429, 502, 503, 504} status codes and split
exception handling so ConnectionError/Timeout are retried while other
RequestException subclasses are raised immediately.
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
def test_retry_on_502(mock_session_cls, mock_sleep):
    """http_request retries on 502 Bad Gateway and recovers."""
    from vast import http_request

    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    response_502 = MagicMock()
    response_502.status_code = 502
    response_200 = MagicMock()
    response_200.status_code = 200

    mock_session.send.side_effect = [response_502, response_200]
    mock_session.prepare_request.return_value = MagicMock()

    args = _make_args(retry=3)
    with patch('vast.ARGS', args):
        result = http_request('GET', args, 'http://example.com/test')

    assert result.status_code == 200
    assert mock_session.send.call_count == 2


@patch('vast.time.sleep')
@patch('vast.requests.Session')
def test_retry_on_503(mock_session_cls, mock_sleep):
    """http_request retries on 503 Service Unavailable."""
    from vast import http_request

    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    response_503 = MagicMock()
    response_503.status_code = 503
    response_200 = MagicMock()
    response_200.status_code = 200

    mock_session.send.side_effect = [response_503, response_200]
    mock_session.prepare_request.return_value = MagicMock()

    args = _make_args(retry=3)
    with patch('vast.ARGS', args):
        result = http_request('GET', args, 'http://example.com/test')

    assert result.status_code == 200
    assert mock_session.send.call_count == 2


@patch('vast.time.sleep')
@patch('vast.requests.Session')
def test_retry_on_504(mock_session_cls, mock_sleep):
    """http_request retries on 504 Gateway Timeout."""
    from vast import http_request

    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    response_504 = MagicMock()
    response_504.status_code = 504
    response_200 = MagicMock()
    response_200.status_code = 200

    mock_session.send.side_effect = [response_504, response_200]
    mock_session.prepare_request.return_value = MagicMock()

    args = _make_args(retry=3)
    with patch('vast.ARGS', args):
        result = http_request('GET', args, 'http://example.com/test')

    assert result.status_code == 200
    assert mock_session.send.call_count == 2


@patch('vast.time.sleep')
@patch('vast.requests.Session')
def test_retry_on_429_still_works(mock_session_cls, mock_sleep):
    """Original 429 retry behavior is preserved."""
    from vast import http_request

    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    response_429 = MagicMock()
    response_429.status_code = 429
    response_200 = MagicMock()
    response_200.status_code = 200

    mock_session.send.side_effect = [response_429, response_200]
    mock_session.prepare_request.return_value = MagicMock()

    args = _make_args(retry=3)
    with patch('vast.ARGS', args):
        result = http_request('GET', args, 'http://example.com/test')

    assert result.status_code == 200
    assert mock_session.send.call_count == 2
    # Should have slept once (after the 429)
    assert mock_sleep.call_count == 1


@patch('vast.time.sleep')
@patch('vast.requests.Session')
def test_retry_on_connection_error(mock_session_cls, mock_sleep):
    """http_request retries on ConnectionError and recovers."""
    from vast import http_request

    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    response_200 = MagicMock()
    response_200.status_code = 200

    mock_session.send.side_effect = [
        requests.exceptions.ConnectionError("connection refused"),
        response_200,
    ]
    mock_session.prepare_request.return_value = MagicMock()

    args = _make_args(retry=3)
    with patch('vast.ARGS', args):
        result = http_request('GET', args, 'http://example.com/test')

    assert result.status_code == 200
    assert mock_session.send.call_count == 2


@patch('vast.time.sleep')
@patch('vast.requests.Session')
def test_retry_on_timeout_exception(mock_session_cls, mock_sleep):
    """http_request retries on Timeout exception and recovers."""
    from vast import http_request

    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    response_200 = MagicMock()
    response_200.status_code = 200

    mock_session.send.side_effect = [
        requests.exceptions.Timeout("read timed out"),
        response_200,
    ]
    mock_session.prepare_request.return_value = MagicMock()

    args = _make_args(retry=3)
    with patch('vast.ARGS', args):
        result = http_request('GET', args, 'http://example.com/test')

    assert result.status_code == 200
    assert mock_session.send.call_count == 2


@patch('vast.time.sleep')
@patch('vast.requests.Session')
def test_no_retry_on_non_retryable_exception(mock_session_cls, mock_sleep):
    """Non-retryable RequestException subclasses are raised immediately."""
    from vast import http_request

    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    # InvalidURL is a non-retryable error
    mock_session.send.side_effect = requests.exceptions.InvalidURL("bad url")
    mock_session.prepare_request.return_value = MagicMock()

    args = _make_args(retry=3)
    with patch('vast.ARGS', args):
        with pytest.raises(requests.exceptions.InvalidURL):
            http_request('GET', args, 'http://example.com/test')

    # Should NOT have retried -- only 1 call
    assert mock_session.send.call_count == 1
    # Should NOT have slept
    assert mock_sleep.call_count == 0


@patch('vast.time.sleep')
@patch('vast.requests.Session')
def test_no_retry_on_non_retryable_status(mock_session_cls, mock_sleep):
    """Non-retryable status codes (e.g., 400, 404, 500) break out immediately."""
    from vast import http_request

    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    response_400 = MagicMock()
    response_400.status_code = 400

    mock_session.send.return_value = response_400
    mock_session.prepare_request.return_value = MagicMock()

    args = _make_args(retry=3)
    with patch('vast.ARGS', args):
        result = http_request('GET', args, 'http://example.com/test')

    # Should return on first call without retrying
    assert result.status_code == 400
    assert mock_session.send.call_count == 1


@patch('vast.time.sleep')
@patch('vast.requests.Session')
def test_retryable_status_codes_constant(mock_session_cls, mock_sleep):
    """RETRYABLE_STATUS_CODES contains exactly {429, 502, 503, 504}."""
    from vast import RETRYABLE_STATUS_CODES

    assert RETRYABLE_STATUS_CODES == {429, 502, 503, 504}
