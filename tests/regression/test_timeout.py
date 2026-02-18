"""Missing timeout on HTTP requests.

The bug: session.send() has no timeout parameter. Requests can hang
indefinitely if the server never responds or the connection stalls.

The fix: Add timeout=DEFAULT_TIMEOUT (30s) to http_request() and forward
it to session.send(). All wrapper functions (http_get, http_post, http_put,
http_del) accept and forward the timeout parameter.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import argparse
from unittest.mock import MagicMock, patch, call
import pytest


def _make_args(retry=1):
    return argparse.Namespace(retry=retry, curl=False)


@patch('vast.time.sleep')
@patch('vast.requests.Session')
def test_default_timeout_forwarded(mock_session_cls, mock_sleep):
    """http_request passes timeout=30 (DEFAULT_TIMEOUT) to session.send by default."""
    from vast import http_request, DEFAULT_TIMEOUT

    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    success_response = MagicMock()
    success_response.status_code = 200
    mock_session.send.return_value = success_response
    mock_session.prepare_request.return_value = MagicMock()

    args = _make_args(retry=1)
    with patch('vast.ARGS', args):
        result = http_request('GET', args, 'http://example.com/test')

    assert result.status_code == 200
    # Verify timeout was passed to session.send
    mock_session.send.assert_called_once()
    _, kwargs = mock_session.send.call_args
    assert kwargs.get('timeout') == DEFAULT_TIMEOUT
    assert kwargs.get('timeout') == 30


@patch('vast.time.sleep')
@patch('vast.requests.Session')
def test_custom_timeout_forwarded(mock_session_cls, mock_sleep):
    """http_request forwards a custom timeout value to session.send."""
    from vast import http_request

    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    success_response = MagicMock()
    success_response.status_code = 200
    mock_session.send.return_value = success_response
    mock_session.prepare_request.return_value = MagicMock()

    args = _make_args(retry=1)
    with patch('vast.ARGS', args):
        result = http_request('GET', args, 'http://example.com/test', timeout=120)

    assert result.status_code == 200
    _, kwargs = mock_session.send.call_args
    assert kwargs.get('timeout') == 120


@patch('vast.http_request')
def test_http_get_forwards_timeout(mock_http_request):
    """http_get forwards timeout parameter to http_request."""
    from vast import http_get

    mock_http_request.return_value = MagicMock(status_code=200)
    args = _make_args()

    http_get(args, 'http://example.com/test', timeout=60)

    mock_http_request.assert_called_once()
    _, kwargs = mock_http_request.call_args
    assert kwargs.get('timeout') == 60


@patch('vast.http_request')
def test_http_post_forwards_timeout(mock_http_request):
    """http_post forwards timeout parameter to http_request."""
    from vast import http_post

    mock_http_request.return_value = MagicMock(status_code=200)
    args = _make_args()

    http_post(args, 'http://example.com/test', timeout=90)

    mock_http_request.assert_called_once()
    _, kwargs = mock_http_request.call_args
    assert kwargs.get('timeout') == 90


@patch('vast.http_request')
def test_http_put_forwards_timeout(mock_http_request):
    """http_put forwards timeout parameter to http_request."""
    from vast import http_put

    mock_http_request.return_value = MagicMock(status_code=200)
    args = _make_args()

    http_put(args, 'http://example.com/test', timeout=45)

    mock_http_request.assert_called_once()
    _, kwargs = mock_http_request.call_args
    assert kwargs.get('timeout') == 45


@patch('vast.http_request')
def test_http_del_forwards_timeout(mock_http_request):
    """http_del forwards timeout parameter to http_request."""
    from vast import http_del

    mock_http_request.return_value = MagicMock(status_code=200)
    args = _make_args()

    http_del(args, 'http://example.com/test', timeout=15)

    mock_http_request.assert_called_once()
    _, kwargs = mock_http_request.call_args
    assert kwargs.get('timeout') == 15
