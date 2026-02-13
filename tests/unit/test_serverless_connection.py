"""Unit tests for vastai.serverless.client.connection module helper functions.

Tests cover:
- _retryable: status code retry determination
- _backoff_delay: exponential backoff with jitter calculation
- _build_kwargs: HTTP request argument construction
"""
import pytest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add vast-cli to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vastai.serverless.client.connection import (
    _retryable,
    _backoff_delay,
    _build_kwargs,
    _JITTER_CAP_SECONDS,
)


class TestRetryable:
    """Tests for _retryable() function."""

    def test_retryable_408_request_timeout(self):
        """408 Request Timeout is retryable."""
        assert _retryable(408) is True

    def test_retryable_429_too_many_requests(self):
        """429 Too Many Requests is retryable."""
        assert _retryable(429) is True

    def test_retryable_500_internal_server_error(self):
        """500 Internal Server Error is retryable."""
        assert _retryable(500) is True

    def test_retryable_501_not_implemented(self):
        """501 Not Implemented is retryable (5xx range)."""
        assert _retryable(501) is True

    def test_retryable_502_bad_gateway(self):
        """502 Bad Gateway is retryable."""
        assert _retryable(502) is True

    def test_retryable_503_service_unavailable(self):
        """503 Service Unavailable is retryable."""
        assert _retryable(503) is True

    def test_retryable_504_gateway_timeout(self):
        """504 Gateway Timeout is retryable."""
        assert _retryable(504) is True

    def test_retryable_599_max_5xx(self):
        """599 (max 5xx) is retryable."""
        assert _retryable(599) is True

    def test_not_retryable_200_ok(self):
        """200 OK is not retryable."""
        assert _retryable(200) is False

    def test_not_retryable_201_created(self):
        """201 Created is not retryable."""
        assert _retryable(201) is False

    def test_not_retryable_400_bad_request(self):
        """400 Bad Request is not retryable."""
        assert _retryable(400) is False

    def test_not_retryable_401_unauthorized(self):
        """401 Unauthorized is not retryable."""
        assert _retryable(401) is False

    def test_not_retryable_403_forbidden(self):
        """403 Forbidden is not retryable."""
        assert _retryable(403) is False

    def test_not_retryable_404_not_found(self):
        """404 Not Found is not retryable."""
        assert _retryable(404) is False

    def test_not_retryable_600_boundary(self):
        """600 is not retryable (beyond 5xx range)."""
        assert _retryable(600) is False


class TestBackoffDelay:
    """Tests for _backoff_delay() function."""

    def test_backoff_attempt_1(self):
        """Attempt 1 returns delay between 2.0 and 3.0."""
        delay = _backoff_delay(1)
        # 2^1 + random.uniform(0, 1) = 2.0 to 3.0
        assert 2.0 <= delay <= 3.0

    def test_backoff_attempt_2(self):
        """Attempt 2 returns delay between 4.0 and 5.0."""
        delay = _backoff_delay(2)
        # 2^2 + random.uniform(0, 1) = 4.0 to 5.0 (capped at 5.0)
        assert 4.0 <= delay <= 5.0

    def test_backoff_capped_at_jitter_cap(self):
        """Large attempts are capped at _JITTER_CAP_SECONDS (5.0)."""
        delay = _backoff_delay(10)  # 2^10 = 1024 >> 5
        assert delay <= _JITTER_CAP_SECONDS
        assert delay <= 5.0

    def test_backoff_attempt_0(self):
        """Attempt 0 returns delay between 1.0 and 2.0."""
        delay = _backoff_delay(0)
        # 2^0 + random.uniform(0, 1) = 1.0 to 2.0
        assert 1.0 <= delay <= 2.0

    def test_backoff_always_positive(self):
        """All backoff delays are positive."""
        for attempt in range(10):
            delay = _backoff_delay(attempt)
            assert delay > 0

    @patch('vastai.serverless.client.connection.random.uniform')
    def test_backoff_uses_random_uniform(self, mock_uniform):
        """_backoff_delay uses random.uniform for jitter."""
        mock_uniform.return_value = 0.5
        delay = _backoff_delay(1)
        # 2^1 + 0.5 = 2.5 (not capped)
        assert delay == 2.5
        mock_uniform.assert_called_once_with(0, 1)


class TestBuildKwargs:
    """Tests for _build_kwargs() function."""

    def test_includes_body_for_post(self):
        """_build_kwargs includes json body for POST requests."""
        result = _build_kwargs(
            headers={"Authorization": "Bearer test"},
            params={"key": "val"},
            ssl_context=None,
            timeout=30,
            body={"data": "test"},
            method="POST",
            stream=False,
        )
        assert "json" in result
        assert result["json"] == {"data": "test"}

    def test_includes_body_for_put(self):
        """_build_kwargs includes json body for PUT requests."""
        result = _build_kwargs(
            headers={},
            params={},
            ssl_context=None,
            timeout=30,
            body={"data": "update"},
            method="PUT",
            stream=False,
        )
        assert "json" in result
        assert result["json"] == {"data": "update"}

    def test_includes_body_for_delete(self):
        """_build_kwargs includes json body for DELETE requests."""
        result = _build_kwargs(
            headers={},
            params={},
            ssl_context=None,
            timeout=30,
            body={"id": 123},
            method="DELETE",
            stream=False,
        )
        assert "json" in result
        assert result["json"] == {"id": 123}

    def test_excludes_body_for_get(self):
        """_build_kwargs excludes body for GET requests."""
        result = _build_kwargs(
            headers={},
            params={},
            ssl_context=None,
            timeout=30,
            body={"data": "test"},
            method="GET",
            stream=False,
        )
        assert "json" not in result

    def test_excludes_body_when_none(self):
        """_build_kwargs excludes json when body is None."""
        result = _build_kwargs(
            headers={},
            params={},
            ssl_context=None,
            timeout=30,
            body=None,
            method="POST",
            stream=False,
        )
        assert "json" not in result

    def test_includes_headers(self):
        """_build_kwargs includes headers in result."""
        headers = {"Authorization": "Bearer token", "Content-Type": "application/json"}
        result = _build_kwargs(
            headers=headers,
            params={},
            ssl_context=None,
            timeout=30,
            body=None,
            method="GET",
            stream=False,
        )
        assert result["headers"] == headers

    def test_includes_params(self):
        """_build_kwargs includes params in result."""
        params = {"api_key": "abc123", "limit": "10"}
        result = _build_kwargs(
            headers={},
            params=params,
            ssl_context=None,
            timeout=30,
            body=None,
            method="GET",
            stream=False,
        )
        assert result["params"] == params

    def test_includes_ssl_context(self):
        """_build_kwargs includes ssl context in result."""
        mock_ssl = MagicMock()
        result = _build_kwargs(
            headers={},
            params={},
            ssl_context=mock_ssl,
            timeout=30,
            body=None,
            method="GET",
            stream=False,
        )
        assert result["ssl"] == mock_ssl

    def test_timeout_non_stream(self):
        """_build_kwargs sets timeout for non-streaming requests."""
        result = _build_kwargs(
            headers={},
            params={},
            ssl_context=None,
            timeout=30,
            body=None,
            method="GET",
            stream=False,
        )
        assert result["timeout"].total == 30

    def test_timeout_stream(self):
        """_build_kwargs sets timeout to None for streaming requests."""
        result = _build_kwargs(
            headers={},
            params={},
            ssl_context=None,
            timeout=30,
            body=None,
            method="GET",
            stream=True,
        )
        assert result["timeout"].total is None

    def test_all_keys_present(self):
        """_build_kwargs always includes headers, params, ssl, timeout."""
        result = _build_kwargs(
            headers={},
            params={},
            ssl_context=None,
            timeout=60,
            body=None,
            method="GET",
            stream=False,
        )
        assert "headers" in result
        assert "params" in result
        assert "ssl" in result
        assert "timeout" in result
