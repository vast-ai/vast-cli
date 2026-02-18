"""Unit tests for HTTP helper functions (api_call, http_*, retry logic).

TEST-02: Unit tests for HTTP helper functions with mocked responses.

These tests verify the helper functions in isolation, complementing the
regression tests that focus on specific bug fixes.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import argparse
import json
import pytest
from unittest.mock import MagicMock, patch, call
from requests.exceptions import ConnectionError, Timeout, HTTPError


def _make_args(retry=3, raw=False, explain=False, curl=False):
    """Create minimal args namespace for testing."""
    return argparse.Namespace(
        api_key="test-key",
        url="https://console.vast.ai",
        retry=retry,
        raw=raw,
        explain=explain,
        quiet=False,
        curl=curl,
    )


class TestApiCall:
    """Tests for the api_call() helper function."""

    @patch('vast.http_get')
    def test_api_call_get_request(self, mock_http_get):
        """api_call makes GET request and returns parsed JSON."""
        from vast import api_call

        mock_response = MagicMock()
        mock_response.json.return_value = {"offers": [{"id": 1}]}
        mock_http_get.return_value = mock_response

        args = _make_args()
        # api_call signature: api_call(args, method, path, *, json_body=None, query_args=None)
        result = api_call(args, "GET", "/api/v0/bundles")

        assert result == {"offers": [{"id": 1}]}
        mock_http_get.assert_called_once()

    @patch('vast.http_post')
    def test_api_call_post_request(self, mock_http_post):
        """api_call makes POST request with JSON body."""
        from vast import api_call

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_http_post.return_value = mock_response

        args = _make_args()
        # api_call signature: api_call(args, method, path, *, json_body=None, query_args=None)
        result = api_call(args, "POST", "/api/v0/instances/123/", json_body={"action": "start"})

        assert result == {"success": True}
        mock_http_post.assert_called_once()

    @patch('vast.http_get')
    def test_api_call_handles_http_error(self, mock_http_get):
        """api_call propagates HTTPError from response."""
        from vast import api_call

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPError("404 Not Found")
        mock_http_get.return_value = mock_response

        args = _make_args()
        with pytest.raises(HTTPError):
            # api_call signature: api_call(args, method, path, *, json_body=None, query_args=None)
            api_call(args, "GET", "/api/v0/nonexistent")


class TestHttpHelpers:
    """Tests for http_get, http_post, http_put, http_del functions."""

    @patch('vast.http_request')
    def test_http_get_constructs_correct_request(self, mock_http_request):
        """http_get passes correct method and URL to http_request."""
        from vast import http_get

        mock_http_request.return_value = MagicMock(status_code=200)
        args = _make_args()

        http_get(args, "https://example.com/api/test")

        mock_http_request.assert_called_once()
        call_args = mock_http_request.call_args
        assert call_args[0][0] == "GET"  # method
        assert call_args[0][2] == "https://example.com/api/test"  # url

    @patch('vast.http_request')
    def test_http_post_sends_json_body(self, mock_http_request):
        """http_post includes JSON body in request."""
        from vast import http_post

        mock_http_request.return_value = MagicMock(status_code=200)
        args = _make_args()
        body = {"key": "value"}

        # http_post signature: http_post(args, req_url, headers=None, json=None, timeout=DEFAULT_TIMEOUT)
        http_post(args, "https://example.com/api/test", json=body)

        # http_request is called as: http_request('POST', args, req_url, headers, json, timeout=timeout)
        # json is passed as positional arg at index 4
        call_args = mock_http_request.call_args[0]
        assert call_args[4] == body  # json is 5th positional arg (index 4)

    @patch('vast.http_request')
    def test_http_put_sends_json_body(self, mock_http_request):
        """http_put includes JSON body in request."""
        from vast import http_put

        mock_http_request.return_value = MagicMock(status_code=200)
        args = _make_args()
        body = {"update": "data"}

        # http_put signature: http_put(args, req_url, headers=None, json=None, timeout=DEFAULT_TIMEOUT)
        http_put(args, "https://example.com/api/test", json=body)

        # http_request is called as: http_request('PUT', args, req_url, headers, json, timeout=timeout)
        # json is passed as positional arg at index 4
        call_args = mock_http_request.call_args[0]
        assert call_args[4] == body  # json is 5th positional arg (index 4)

    @patch('vast.http_request')
    def test_http_del_makes_delete_request(self, mock_http_request):
        """http_del uses DELETE method."""
        from vast import http_del

        mock_http_request.return_value = MagicMock(status_code=200)
        args = _make_args()

        http_del(args, "https://example.com/api/resource/123")

        call_args = mock_http_request.call_args
        assert call_args[0][0] == "DELETE"


class TestHttpRequestRetry:
    """Tests for retry logic in http_request."""

    @patch('vast.time.sleep')
    @patch('vast.requests.Session')
    def test_retry_on_connection_error(self, mock_session_cls, mock_sleep):
        """http_request retries on ConnectionError."""
        from vast import http_request

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        # First call fails, second succeeds
        success_response = MagicMock(status_code=200)
        mock_session.send.side_effect = [
            ConnectionError("Connection refused"),
            success_response
        ]
        mock_session.prepare_request.return_value = MagicMock()

        args = _make_args(retry=3)
        with patch('vast.ARGS', args):
            result = http_request('GET', args, 'http://example.com/test')

        assert result.status_code == 200
        assert mock_session.send.call_count == 2

    @patch('vast.time.sleep')
    @patch('vast.requests.Session')
    def test_retry_on_timeout(self, mock_session_cls, mock_sleep):
        """http_request retries on Timeout."""
        from vast import http_request

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        success_response = MagicMock(status_code=200)
        mock_session.send.side_effect = [
            Timeout("Request timed out"),
            success_response
        ]
        mock_session.prepare_request.return_value = MagicMock()

        args = _make_args(retry=3)
        with patch('vast.ARGS', args):
            result = http_request('GET', args, 'http://example.com/test')

        assert result.status_code == 200
        assert mock_session.send.call_count == 2

    @patch('vast.time.sleep')
    @patch('vast.requests.Session')
    def test_retry_on_503_status(self, mock_session_cls, mock_sleep):
        """http_request retries on 503 Service Unavailable."""
        from vast import http_request, RETRYABLE_STATUS_CODES

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        error_response = MagicMock(status_code=503)
        success_response = MagicMock(status_code=200)
        mock_session.send.side_effect = [error_response, success_response]
        mock_session.prepare_request.return_value = MagicMock()

        assert 503 in RETRYABLE_STATUS_CODES

        args = _make_args(retry=3)
        with patch('vast.ARGS', args):
            result = http_request('GET', args, 'http://example.com/test')

        assert result.status_code == 200
        assert mock_session.send.call_count == 2

    @patch('vast.time.sleep')
    @patch('vast.requests.Session')
    def test_no_retry_on_400_status(self, mock_session_cls, mock_sleep):
        """http_request does not retry on 400 Bad Request."""
        from vast import http_request

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        error_response = MagicMock(status_code=400)
        mock_session.send.return_value = error_response
        mock_session.prepare_request.return_value = MagicMock()

        args = _make_args(retry=3)
        with patch('vast.ARGS', args):
            result = http_request('GET', args, 'http://example.com/test')

        assert result.status_code == 400
        assert mock_session.send.call_count == 1  # No retry


class TestTimeoutConstants:
    """Tests for timeout constant values."""

    def test_default_timeout_defined(self):
        """DEFAULT_TIMEOUT constant is defined and reasonable."""
        from vast import DEFAULT_TIMEOUT

        assert DEFAULT_TIMEOUT == 30
        assert isinstance(DEFAULT_TIMEOUT, (int, float))

    def test_long_timeout_defined(self):
        """LONG_TIMEOUT constant is defined for file operations."""
        from vast import LONG_TIMEOUT

        assert LONG_TIMEOUT == 120
        assert LONG_TIMEOUT > 30  # Should be longer than default

    def test_retryable_status_codes_defined(self):
        """RETRYABLE_STATUS_CODES contains expected HTTP statuses."""
        from vast import RETRYABLE_STATUS_CODES

        assert 429 in RETRYABLE_STATUS_CODES  # Too Many Requests
        assert 502 in RETRYABLE_STATUS_CODES  # Bad Gateway
        assert 503 in RETRYABLE_STATUS_CODES  # Service Unavailable
        assert 504 in RETRYABLE_STATUS_CODES  # Gateway Timeout
        assert 500 not in RETRYABLE_STATUS_CODES  # 500 not retried (may have side effects)
