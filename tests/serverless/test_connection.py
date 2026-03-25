"""Unit tests for vastai.serverless.client.connection module.

Tests _retryable, _backoff_delay, _build_kwargs, _iter_sse_json,
_open_once, and _make_request. All network traffic is mocked.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vastai.serverless.client.connection import (
    _backoff_delay,
    _build_kwargs,
    _iter_sse_json,
    _make_request,
    _open_once,
    _retryable,
)


class TestRetryable:
    """Verify _retryable correctly identifies retryable HTTP status codes."""

    def test_retryable_returns_true_for_408(self) -> None:
        """
        Verifies that _retryable returns True for 408 Request Timeout.

        This test verifies by:
        1. Calling _retryable(408)
        2. Asserting result is True

        Assumptions:
        - 408 is a retryable status per implementation
        """
        assert _retryable(408) is True

    def test_retryable_returns_true_for_429(self) -> None:
        """
        Verifies that _retryable returns True for 429 Too Many Requests.

        This test verifies by:
        1. Calling _retryable(429)
        2. Asserting result is True

        Assumptions:
        - 429 is a retryable status per implementation
        """
        assert _retryable(429) is True

    def test_retryable_returns_true_for_5xx_status_codes(self) -> None:
        """
        Verifies that _retryable returns True for 5xx server errors.

        This test verifies by:
        1. Calling _retryable for 500, 502, 503, 504, 599
        2. Asserting each returns True

        Assumptions:
        - 500 <= status < 600 are retryable per implementation
        """
        for status in (500, 502, 503, 504, 599):
            assert _retryable(status) is True

    def test_retryable_returns_false_for_2xx_status_codes(self) -> None:
        """
        Verifies that _retryable returns False for 2xx success codes.

        This test verifies by:
        1. Calling _retryable for 200, 201, 204
        2. Asserting each returns False

        Assumptions:
        - 2xx codes are not retryable
        """
        for status in (200, 201, 204):
            assert _retryable(status) is False

    def test_retryable_returns_false_for_4xx_except_408_429(self) -> None:
        """
        Verifies that _retryable returns False for non-retryable 4xx codes.

        This test verifies by:
        1. Calling _retryable for 400, 401, 403, 404, 422
        2. Asserting each returns False

        Assumptions:
        - Only 408 and 429 are retryable among 4xx
        """
        for status in (400, 401, 403, 404, 422):
            assert _retryable(status) is False


class TestBackoffDelay:
    """Verify _backoff_delay returns capped exponential backoff with jitter."""

    def test_backoff_delay_increases_with_attempt(self) -> None:
        """
        Verifies that _backoff_delay increases as attempt increases.

        This test verifies by:
        1. Patching random.uniform to return 0.5 for deterministic output
        2. Calling _backoff_delay for attempt 0, 1, 2
        3. Asserting each delay is greater than the previous

        Assumptions:
        - Formula is min((2**attempt) + jitter, 5.0)
        """
        with patch("vastai.serverless.client.connection.random.uniform", return_value=0.5):
            d0 = _backoff_delay(0)
            d1 = _backoff_delay(1)
            d2 = _backoff_delay(2)
            assert d0 < d1 < d2

    def test_backoff_delay_includes_jitter(self) -> None:
        """
        Verifies that _backoff_delay includes jitter (random component).

        This test verifies by:
        1. Patching random.uniform to return 0.0
        2. Asserting delay equals base (2**attempt) for attempt 0
        3. Patching random.uniform to return 1.0
        4. Asserting delay is base + 1 when under cap

        Assumptions:
        - Jitter is random.uniform(0, 1) added to base
        """
        with patch("vastai.serverless.client.connection.random.uniform", return_value=0.0):
            assert _backoff_delay(0) == 1.0  # 2**0 + 0 = 1
        with patch("vastai.serverless.client.connection.random.uniform", return_value=1.0):
            assert _backoff_delay(0) == 2.0  # 2**0 + 1 = 2

    def test_backoff_delay_capped_at_five_seconds(self) -> None:
        """
        Verifies that _backoff_delay is capped at 5.0 seconds.

        This test verifies by:
        1. Patching random.uniform to return 1.0
        2. Calling _backoff_delay for attempt 5 (2**5 + 1 = 33 > 5)
        3. Asserting result is 5.0

        Assumptions:
        - Cap is 5.0 seconds per _JITTER_CAP_SECONDS
        """
        with patch("vastai.serverless.client.connection.random.uniform", return_value=1.0):
            delay = _backoff_delay(5)
            assert delay == 5.0


class TestBuildKwargs:
    """Verify _build_kwargs constructs correct request kwargs."""

    def test_build_kwargs_includes_headers_params_ssl(
        self, build_kwargs_defaults
    ) -> None:
        """
        Verifies that _build_kwargs includes headers, params, and ssl.

        This test verifies by:
        1. Calling _build_kwargs with known headers, params, ssl_context
        2. Asserting result contains those keys with correct values

        Assumptions:
        - All kwargs are passed through
        - build_kwargs_defaults fixture provides base kwargs
        """
        headers = {"Authorization": "Bearer x"}
        params = {"api_key": "x"}
        ssl_ctx = MagicMock()
        result = _build_kwargs(
            **{**build_kwargs_defaults, "headers": headers, "params": params, "ssl_context": ssl_ctx},
        )
        assert result["headers"] == headers
        assert result["params"] == params
        assert result["ssl"] is ssl_ctx

    def test_build_kwargs_stream_true_sets_timeout_none(
        self, build_kwargs_defaults
    ) -> None:
        """
        Verifies that _build_kwargs sets timeout=None when stream=True.

        This test verifies by:
        1. Calling _build_kwargs with stream=True and timeout=30
        2. Asserting result["timeout"].total is None

        Assumptions:
        - aiohttp.ClientTimeout(total=None) for streaming
        - build_kwargs_defaults fixture provides base kwargs
        """
        result = _build_kwargs(
            **{**build_kwargs_defaults, "stream": True},
        )
        assert result["timeout"].total is None

    def test_build_kwargs_stream_false_sets_timeout_value(
        self, build_kwargs_defaults
    ) -> None:
        """
        Verifies that _build_kwargs sets timeout when stream=False.

        This test verifies by:
        1. Calling _build_kwargs with stream=False and timeout=60.0
        2. Asserting result["timeout"].total == 60.0

        Assumptions:
        - Non-streaming uses explicit timeout
        - build_kwargs_defaults fixture provides base kwargs
        """
        result = _build_kwargs(
            **{**build_kwargs_defaults, "timeout": 60.0},
        )
        assert result["timeout"].total == 60.0

    def test_build_kwargs_get_method_omits_json_body(
        self, build_kwargs_defaults
    ) -> None:
        """
        Verifies that _build_kwargs does not include json for GET requests.

        This test verifies by:
        1. Calling _build_kwargs with method="GET" and body={"x": 1}
        2. Asserting "json" is not in result

        Assumptions:
        - GET requests do not send JSON body
        - build_kwargs_defaults fixture provides base kwargs
        """
        result = _build_kwargs(
            **{**build_kwargs_defaults, "body": {"x": 1}},
        )
        assert "json" not in result

    def test_build_kwargs_post_method_includes_json_body(
        self, build_kwargs_defaults
    ) -> None:
        """
        Verifies that _build_kwargs includes json for POST requests with body.

        This test verifies by:
        1. Calling _build_kwargs with method="POST" and body={"key": "val"}
        2. Asserting result["json"] == {"key": "val"}

        Assumptions:
        - POST with body adds json kwarg
        - build_kwargs_defaults fixture provides base kwargs
        """
        body = {"key": "val"}
        result = _build_kwargs(
            **{**build_kwargs_defaults, "method": "POST", "body": body},
        )
        assert result["json"] == body

    def test_build_kwargs_post_method_empty_body_omits_json(
        self, build_kwargs_defaults
    ) -> None:
        """
        Verifies that _build_kwargs omits json when body is empty for POST.

        This test verifies by:
        1. Calling _build_kwargs with method="POST" and body={}
        2. Asserting "json" is not in result (empty body is falsy)

        Assumptions:
        - body or {} is used; empty dict is falsy in "method != GET and body"
        - build_kwargs_defaults fixture provides base kwargs
        """
        result = _build_kwargs(
            **{**build_kwargs_defaults, "method": "POST", "body": {}},
        )
        assert "json" not in result


class TestIterSseJson:
    """Verify _iter_sse_json parses SSE stream into JSON objects."""

    async def test_iter_sse_json_yields_data_prefix_lines(
        self, make_sse_response
    ) -> None:
        """
        Verifies that _iter_sse_json parses lines with "data:" prefix.

        This test verifies by:
        1. Creating mock response with content "data: {"a":1}\\n"
        2. Consuming _iter_sse_json
        3. Asserting yielded object is {"a": 1}

        Assumptions:
        - SSE format "data: {...}" is stripped to JSON
        - make_sse_response fixture provides mock response factory
        """
        mock_resp = make_sse_response([b'data: {"a": 1}\n'])

        collected = []
        async for obj in _iter_sse_json(mock_resp):
            collected.append(obj)

        assert collected == [{"a": 1}]

    async def test_iter_sse_json_yields_raw_jsonl_lines(
        self, make_sse_response
    ) -> None:
        """
        Verifies that _iter_sse_json parses raw JSONL (no data: prefix).

        This test verifies by:
        1. Creating mock response with content '{"b": 2}\\n'
        2. Consuming _iter_sse_json
        3. Asserting yielded object is {"b": 2}

        Assumptions:
        - Raw JSONL lines are parsed directly
        - make_sse_response fixture provides mock response factory
        """
        mock_resp = make_sse_response([b'{"b": 2}\n'])

        collected = []
        async for obj in _iter_sse_json(mock_resp):
            collected.append(obj)

        assert collected == [{"b": 2}]

    async def test_iter_sse_json_ignores_malformed_lines(
        self, make_sse_response
    ) -> None:
        """
        Verifies that _iter_sse_json skips malformed lines without raising.

        This test verifies by:
        1. Creating mock response with valid JSON and invalid line
        2. Consuming _iter_sse_json
        3. Asserting only valid JSON is yielded

        Assumptions:
        - json.loads fails on invalid lines; exception is caught and skipped
        - make_sse_response fixture provides mock response factory
        """
        mock_resp = make_sse_response([
            b'{"ok": 1}\n',
            b'not valid json\n',
            b'{"ok": 2}\n',
        ])

        collected = []
        async for obj in _iter_sse_json(mock_resp):
            collected.append(obj)

        assert collected == [{"ok": 1}, {"ok": 2}]

    async def test_iter_sse_json_ignores_empty_lines(
        self, make_sse_response
    ) -> None:
        """
        Verifies that _iter_sse_json skips empty lines.

        This test verifies by:
        1. Creating mock response with empty lines and valid JSON
        2. Consuming _iter_sse_json
        3. Asserting only non-empty lines are parsed

        Assumptions:
        - Empty lines are skipped
        - make_sse_response fixture provides mock response factory
        """
        mock_resp = make_sse_response([
            b'\n',
            b'{"x": 1}\n',
            b'  \n',
        ])

        collected = []
        async for obj in _iter_sse_json(mock_resp):
            collected.append(obj)

        assert collected == [{"x": 1}]

    async def test_iter_sse_json_flushes_tail_buffer(
        self, make_sse_response
    ) -> None:
        """
        Verifies that _iter_sse_json yields tail content without newline.

        This test verifies by:
        1. Creating mock response with JSON at end without trailing newline
        2. Consuming _iter_sse_json
        3. Asserting tail is yielded

        Assumptions:
        - Buffer tail is flushed on stream end
        - make_sse_response fixture provides mock response factory
        """
        mock_resp = make_sse_response([b'{"tail": true}'])

        collected = []
        async for obj in _iter_sse_json(mock_resp):
            collected.append(obj)

        assert collected == [{"tail": True}]

    async def test_iter_sse_json_handles_multiple_chunks(
        self, make_sse_response
    ) -> None:
        """
        Verifies that _iter_sse_json assembles across chunk boundaries.

        This test verifies by:
        1. Yielding chunks that split a JSON line
        2. Asserting complete JSON objects are yielded

        Assumptions:
        - Buffer accumulates until newline
        - make_sse_response fixture provides mock response factory
        """
        mock_resp = make_sse_response([
            b'data: {"a": 1}\n{"b": ',
            b'2}\n',
        ])

        collected = []
        async for obj in _iter_sse_json(mock_resp):
            collected.append(obj)

        assert collected == [{"a": 1}, {"b": 2}]

    async def test_iter_sse_json_skips_empty_chunks(
        self, make_sse_response
    ) -> None:
        """
        Verifies that _iter_sse_json skips empty chunks from iter_any.

        This test verifies by:
        1. Yielding empty bytes, then valid JSON
        2. Asserting only valid JSON is yielded (empty chunks ignored)

        Assumptions:
        - Empty chunks trigger "if not chunk: continue"
        """
        async def mock_iter():
            yield b""
            yield b'{"a": 1}\n'
            yield b""

        mock_resp = MagicMock()
        mock_resp.content.iter_any = mock_iter

        collected = []
        async for obj in _iter_sse_json(mock_resp):
            collected.append(obj)

        assert collected == [{"a": 1}]

    async def test_iter_sse_json_tail_parse_failure_silent(
        self, make_sse_response
    ) -> None:
        """
        Verifies that _iter_sse_json silently skips tail that fails to parse.

        This test verifies by:
        1. Yielding valid JSON then invalid tail without newline
        2. Asserting only valid JSON is yielded; no exception raised

        Assumptions:
        - Tail parse exception is caught and ignored (pass)
        """
        async def mock_iter():
            yield b'{"ok": 1}\n'
            yield b"not valid json tail"

        mock_resp = MagicMock()
        mock_resp.content.iter_any = mock_iter

        collected = []
        async for obj in _iter_sse_json(mock_resp):
            collected.append(obj)

        assert collected == [{"ok": 1}]


class TestOpenOnce:
    """Verify _open_once executes single HTTP request."""

    async def test_open_once_uses_get_for_get_method(
        self, make_mock_session
    ) -> None:
        """
        Verifies that _open_once calls session.get when method is GET.

        This test verifies by:
        1. Creating mock session with AsyncMock get/post
        2. Calling _open_once with method="GET"
        3. Asserting session.get was called with url+route

        Assumptions:
        - GET uses session.get
        - make_mock_session fixture provides mock session factory
        """
        mock_session = make_mock_session(get_returns=MagicMock())

        await _open_once(
            session=mock_session,
            method="GET",
            url="https://example.com",
            route="/api/",
            kwargs={"headers": {}},
        )

        mock_session.get.assert_called_once_with("https://example.com/api/", headers={})
        mock_session.post.assert_not_called()

    async def test_open_once_uses_post_for_post_method(
        self, make_mock_session
    ) -> None:
        """
        Verifies that _open_once calls session.post when method is POST.

        This test verifies by:
        1. Creating mock session with AsyncMock get/post
        2. Calling _open_once with method="POST"
        3. Asserting session.post was called with url+route

        Assumptions:
        - POST uses session.post
        - make_mock_session fixture provides mock session factory
        """
        mock_session = make_mock_session(post_returns=MagicMock())

        kwargs = {"headers": {}, "json": {"x": 1}}
        await _open_once(
            session=mock_session,
            method="POST",
            url="https://example.com",
            route="/submit",
            kwargs=kwargs,
        )

        mock_session.post.assert_called_once_with("https://example.com/submit", **kwargs)
        mock_session.get.assert_not_called()


class TestMakeRequest:
    """Verify _make_request with mocked client and session."""

    async def test_make_request_success_returns_ok_result(
        self,
        make_mock_http_response,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that _make_request returns ok=True for 2xx response.

        This test verifies by:
        1. Mocking client._get_session and client.get_ssl_context
        2. Mocking session.get to return 200 with JSON body
        3. Calling _make_request
        4. Asserting result has ok=True, status=200, json

        Assumptions:
        - No real network; fixtures provide mocked client/session
        """
        mock_resp = make_mock_http_response(
            status=200,
            text='{"result": "ok"}',
            json_data={"result": "ok"},
        )
        _, mock_client = make_mock_make_request_client(mock_resp)

        result = await _make_request(
            client=mock_client,
            route="/test",
            api_key="sk-test",
            url="https://api.example.com",
            method="GET",
            retries=1,
        )

        assert result["ok"] is True
        assert result["status"] == 200
        assert result["json"] == {"result": "ok"}

    async def test_make_request_non_retryable_4xx_returns_ok_false(
        self,
        make_mock_http_response,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that _make_request returns ok=False for non-retryable 4xx.

        This test verifies by:
        1. Mocking client and session
        2. Returning 404 response
        3. Asserting result has ok=False, status=404, retryable=False

        Assumptions:
        - 404 is not retryable; no retries
        - Fixtures provide mocked client/session
        """
        mock_resp = make_mock_http_response(
            status=404,
            text="Not Found",
        )
        _, mock_client = make_mock_make_request_client(mock_resp)

        result = await _make_request(
            client=mock_client,
            route="/missing",
            api_key="sk-test",
            url="https://api.example.com",
            method="GET",
            retries=1,
        )

        assert result["ok"] is False
        assert result["status"] == 404
        assert result["retryable"] is False

    async def test_make_request_successful_json_parse_failure_raises(
        self,
        make_mock_http_response,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that _make_request raises for invalid JSON on 2xx response.

        This test verifies by:
        1. Mocking 200 response with non-JSON body
        2. Calling _make_request
        3. Asserting Exception is raised with "Invalid JSON"

        Assumptions:
        - 2xx with invalid JSON is a hard failure per implementation
        - Fixtures provide mocked client/session
        """
        mock_resp = make_mock_http_response(
            status=200,
            text="not json",
            json_side_effect=Exception("json decode error"),
        )
        _, mock_client = make_mock_make_request_client(mock_resp)

        with pytest.raises(Exception, match="Invalid JSON"):
            await _make_request(
                client=mock_client,
                route="/test",
                api_key="sk-test",
                url="https://api.example.com",
                method="GET",
                retries=1,
            )

    async def test_make_request_sets_full_url_in_result(
        self,
        make_mock_http_response,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that _make_request returns full_url as url + route.

        This test verifies by:
        1. Calling _make_request with url and route
        2. Asserting result["url"] == url + route

        Assumptions:
        - full_url is url + route
        - Fixtures provide mocked client/session
        """
        mock_resp = make_mock_http_response(
            status=200,
            text="{}",
            json_data={},
        )
        _, mock_client = make_mock_make_request_client(mock_resp)

        result = await _make_request(
            client=mock_client,
            route="/v1/endpoint",
            api_key="sk-test",
            url="https://api.example.com",
            method="GET",
            retries=1,
        )

        assert result["url"] == "https://api.example.com/v1/endpoint"

    async def test_make_request_stream_success_returns_stream_iterator(
        self,
        make_mock_make_request_client,
        make_sse_response,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that _make_request with stream=True returns stream iterator on 2xx.

        This test verifies by:
        1. Mocking response with status 200 and content.iter_any
        2. Calling _make_request with stream=True
        3. Asserting result has ok=True and consumable stream

        Assumptions:
        - Stream path uses _open_once; mock returns response with iter_any
        """
        mock_resp = make_sse_response([b'{"x": 1}\n', b'{"x": 2}\n'])
        mock_resp.status = 200
        mock_resp.headers = {}
        mock_resp.release = MagicMock()

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_resp)
        mock_session.post = AsyncMock()

        mock_client = MagicMock()
        mock_client._get_session = AsyncMock(return_value=mock_session)
        mock_client.get_ssl_context = AsyncMock(return_value=None)

        result = await _make_request(
            client=mock_client,
            route="/stream",
            api_key="sk-test",
            url="https://api.example.com",
            method="GET",
            retries=1,
            stream=True,
        )

        assert result["ok"] is True
        assert result["status"] == 200
        assert "stream" in result
        collected = []
        async for obj in result["stream"]:
            collected.append(obj)
        assert collected == [{"x": 1}, {"x": 2}]

    async def test_make_request_stream_non_2xx_returns_ok_false(
        self,
        make_mock_http_response,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that _make_request with stream=True returns ok=False for non-2xx.

        This test verifies by:
        1. Mocking 500 response (retryable but retries=1)
        2. Calling _make_request with stream=True
        3. Asserting result has ok=False, retryable=True

        Assumptions:
        - Stream path handles non-2xx same as non-stream
        """
        mock_resp = make_mock_http_response(
            status=500,
            text="Internal Server Error",
        )
        mock_resp.release = MagicMock()
        _, mock_client = make_mock_make_request_client(mock_resp)

        result = await _make_request(
            client=mock_client,
            route="/stream",
            api_key="sk-test",
            url="https://api.example.com",
            method="GET",
            retries=1,
            stream=True,
        )

        assert result["ok"] is False
        assert result["status"] == 500
        assert result["retryable"] is True

    async def test_make_request_non_2xx_with_json_body_parses_best_effort(
        self,
        make_mock_http_response,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that _make_request parses JSON from non-2xx when body looks like JSON.

        This test verifies by:
        1. Returning 400 with body '{"error": "bad request"}'
        2. Asserting result["json"] contains parsed JSON

        Assumptions:
        - Best-effort JSON parse for non-2xx when text starts with { or [
        """
        mock_resp = make_mock_http_response(
            status=400,
            text='{"error": "bad request"}',
        )
        _, mock_client = make_mock_make_request_client(mock_resp)

        result = await _make_request(
            client=mock_client,
            route="/bad",
            api_key="sk-test",
            url="https://api.example.com",
            method="GET",
            retries=1,
        )

        assert result["ok"] is False
        assert result["json"] == {"error": "bad request"}

    async def test_make_request_timeout_on_last_attempt_raises(
        self,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that _make_request raises TimeoutError on last retry.

        This test verifies by:
        1. Mocking session.get to raise asyncio.TimeoutError
        2. Calling _make_request with retries=1
        3. Asserting TimeoutError is raised with message

        Assumptions:
        - Timeout on final attempt propagates as TimeoutError
        """
        mock_session = MagicMock()
        mock_session.get = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_session.post = AsyncMock()

        mock_client = MagicMock()
        mock_client._get_session = AsyncMock(return_value=mock_session)
        mock_client.get_ssl_context = AsyncMock(return_value=None)

        with pytest.raises(TimeoutError, match="timed out after"):
            await _make_request(
                client=mock_client,
                route="/slow",
                api_key="sk-test",
                url="https://api.example.com",
                method="GET",
                retries=1,
                timeout=30.0,
            )

    async def test_make_request_stream_timeout_on_last_attempt_raises(
        self,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that stream path raises TimeoutError on last retry.

        This test verifies by:
        1. Mocking session.get to raise asyncio.TimeoutError (stream path)
        2. Calling _make_request with stream=True, retries=1
        3. Asserting TimeoutError is raised

        Assumptions:
        - Stream path TimeoutError on final attempt propagates
        """
        mock_session = MagicMock()
        mock_session.get = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_session.post = AsyncMock()

        mock_client = MagicMock()
        mock_client._get_session = AsyncMock(return_value=mock_session)
        mock_client.get_ssl_context = AsyncMock(return_value=None)

        with pytest.raises(TimeoutError, match="timed out after"):
            await _make_request(
                client=mock_client,
                route="/stream",
                api_key="sk-test",
                url="https://api.example.com",
                method="GET",
                retries=1,
                stream=True,
            )

    async def test_make_request_stream_non_2xx_json_parse_fails_silent(
        self,
        make_mock_http_response,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that stream path silently skips JSON parse when text is invalid.

        This test verifies by:
        1. Returning 500 with body that starts with { but is invalid JSON
        2. Asserting result["json"] is None (parse fails in except, pass)

        Assumptions:
        - json.loads exception in best-effort parse is caught and ignored
        """
        mock_resp = make_mock_http_response(
            status=500,
            text='{ invalid json }',
        )
        mock_resp.release = MagicMock()
        _, mock_client = make_mock_make_request_client(mock_resp)

        result = await _make_request(
            client=mock_client,
            route="/stream",
            api_key="sk-test",
            url="https://api.example.com",
            method="GET",
            retries=1,
            stream=True,
        )

        assert result["ok"] is False
        assert result["json"] is None

    async def test_make_request_exception_on_last_attempt_raises(
        self,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that _make_request raises on last retry for generic exception.

        This test verifies by:
        1. Mocking session.get to raise ConnectionError
        2. Calling _make_request with retries=1
        3. Asserting ConnectionError is raised

        Assumptions:
        - Generic exception on final attempt propagates
        """
        mock_session = MagicMock()
        mock_session.get = AsyncMock(side_effect=ConnectionError("refused"))
        mock_session.post = AsyncMock()

        mock_client = MagicMock()
        mock_client._get_session = AsyncMock(return_value=mock_session)
        mock_client.get_ssl_context = AsyncMock(return_value=None)

        with pytest.raises(ConnectionError, match="refused"):
            await _make_request(
                client=mock_client,
                route="/fail",
                api_key="sk-test",
                url="https://api.example.com",
                method="GET",
                retries=1,
            )

    async def test_make_request_client_with_logger_logs_on_success(
        self,
        make_mock_http_response,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that _make_request calls client.logger.debug when client has logger.

        This test verifies by:
        1. Adding logger to mock_client
        2. Calling _make_request with success response
        3. Asserting logger.debug was called

        Assumptions:
        - hasattr(client, 'logger') triggers debug log on success
        """
        mock_resp = make_mock_http_response(
            status=200,
            text='{"ok": true}',
            json_data={"ok": True},
        )
        _, mock_client = make_mock_make_request_client(mock_resp)
        mock_client.logger = MagicMock()

        await _make_request(
            client=mock_client,
            route="/test",
            api_key="sk-test",
            url="https://api.example.com",
            method="GET",
            retries=1,
        )

        mock_client.logger.debug.assert_called()

    async def test_make_request_method_uppercased(
        self,
        make_mock_http_response,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that _make_request uppercases method (e.g. post -> POST).

        This test verifies by:
        1. Calling _make_request with method="post"
        2. Asserting session.post was used (not get)

        Assumptions:
        - method.upper() normalizes to POST for aiohttp
        """
        mock_resp = make_mock_http_response(
            status=200,
            text="{}",
            json_data={},
        )
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_resp)

        mock_client = MagicMock()
        mock_client._get_session = AsyncMock(return_value=mock_session)
        mock_client.get_ssl_context = AsyncMock(return_value=None)

        with patch("vastai.serverless.client.connection._build_kwargs") as mock_build:
            mock_build.return_value = {
                "headers": {},
                "params": {},
                "timeout": MagicMock(),
                "json": {},
            }

            await _make_request(
                client=mock_client,
                route="/submit",
                api_key="sk-test",
                url="https://api.example.com",
                method="post",
                retries=1,
            )

        mock_session.post.assert_called()
        mock_session.get.assert_not_called()

    async def test_make_request_stream_non_2xx_with_json_parses_best_effort(
        self,
        make_mock_http_response,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that stream path parses JSON from non-2xx when body looks like JSON.

        This test verifies by:
        1. Returning 500 with body '{"error": "server"}'
        2. Asserting result["json"] contains parsed JSON

        Assumptions:
        - Stream path best-effort JSON parse when text starts with { or [
        """
        mock_resp = make_mock_http_response(
            status=500,
            text='{"error": "server"}',
        )
        mock_resp.release = MagicMock()
        _, mock_client = make_mock_make_request_client(mock_resp)

        result = await _make_request(
            client=mock_client,
            route="/stream",
            api_key="sk-test",
            url="https://api.example.com",
            method="GET",
            retries=1,
            stream=True,
        )

        assert result["ok"] is False
        assert result["json"] == {"error": "server"}

    async def test_make_request_stream_retryable_retries_then_returns(
        self,
        make_mock_http_response,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that stream path retries on retryable status then returns.

        This test verifies by:
        1. First attempt returns 503, second returns 404 (non-retryable)
        2. Patching asyncio.sleep to avoid delay
        3. Asserting result from final attempt

        Assumptions:
        - retryable + attempt < retries triggers sleep and continue
        """
        mock_resp_503 = make_mock_http_response(status=503, text="Unavailable")
        mock_resp_503.release = MagicMock()
        mock_resp_404 = make_mock_http_response(status=404, text="Not Found")
        mock_resp_404.release = MagicMock()

        mock_session = MagicMock()
        mock_session.get = AsyncMock(
            side_effect=[mock_resp_503, mock_resp_404]
        )
        mock_session.post = AsyncMock()

        mock_client = MagicMock()
        mock_client._get_session = AsyncMock(return_value=mock_session)
        mock_client.get_ssl_context = AsyncMock(return_value=None)

        with patch(
            "vastai.serverless.client.connection.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await _make_request(
                client=mock_client,
                route="/stream",
                api_key="sk-test",
                url="https://api.example.com",
                method="GET",
                retries=2,
                stream=True,
            )

        assert result["ok"] is False
        assert result["status"] == 404
        assert result["attempt"] == 2

    async def test_make_request_stream_timeout_retries_then_succeeds(
        self,
        make_mock_http_response,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that stream path retries after TimeoutError then succeeds.

        This test verifies by:
        1. First attempt raises TimeoutError, second returns 200
        2. Patching asyncio.sleep
        3. Asserting success on second attempt

        Assumptions:
        - TimeoutError triggers sleep and retry when attempts remain
        """
        mock_resp = make_mock_http_response(
            status=200,
            text='{"ok": true}',
            json_data={"ok": True},
        )

        mock_session = MagicMock()
        mock_session.get = AsyncMock(
            side_effect=[asyncio.TimeoutError(), mock_resp]
        )
        mock_session.post = AsyncMock()

        mock_client = MagicMock()
        mock_client._get_session = AsyncMock(return_value=mock_session)
        mock_client.get_ssl_context = AsyncMock(return_value=None)

        with patch(
            "vastai.serverless.client.connection.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await _make_request(
                client=mock_client,
                route="/stream",
                api_key="sk-test",
                url="https://api.example.com",
                method="GET",
                retries=2,
                stream=True,
            )

        assert result["ok"] is True
        assert result["status"] == 200

    async def test_make_request_stream_exception_retries_then_succeeds(
        self,
        make_mock_http_response,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that stream path retries after generic exception then succeeds.

        This test verifies by:
        1. First attempt raises ConnectionError, second returns 200
        2. Patching asyncio.sleep
        3. Asserting success on second attempt

        Assumptions:
        - Generic exception triggers sleep and retry when attempts remain
        """
        mock_resp = make_mock_http_response(
            status=200,
            text='{"ok": true}',
            json_data={"ok": True},
        )

        mock_session = MagicMock()
        mock_session.get = AsyncMock(
            side_effect=[ConnectionError("reset"), mock_resp]
        )
        mock_session.post = AsyncMock()

        mock_client = MagicMock()
        mock_client._get_session = AsyncMock(return_value=mock_session)
        mock_client.get_ssl_context = AsyncMock(return_value=None)

        with patch(
            "vastai.serverless.client.connection.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await _make_request(
                client=mock_client,
                route="/stream",
                api_key="sk-test",
                url="https://api.example.com",
                method="GET",
                retries=2,
                stream=True,
            )

        assert result["ok"] is True
        assert result["status"] == 200

    async def test_make_request_stream_exception_on_last_attempt_raises(
        self,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that stream path raises when last attempt raises exception.

        This test verifies by:
        1. All attempts raise ConnectionError (retries=2)
        2. Asserting ConnectionError propagates

        Assumptions:
        - Exception on final attempt is re-raised
        """
        mock_session = MagicMock()
        mock_session.get = AsyncMock(side_effect=ConnectionError("fail"))
        mock_session.post = AsyncMock()

        mock_client = MagicMock()
        mock_client._get_session = AsyncMock(return_value=mock_session)
        mock_client.get_ssl_context = AsyncMock(return_value=None)

        with patch(
            "vastai.serverless.client.connection.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            with pytest.raises(ConnectionError, match="fail"):
                await _make_request(
                    client=mock_client,
                    route="/stream",
                    api_key="sk-test",
                    url="https://api.example.com",
                    method="GET",
                    retries=2,
                    stream=True,
                )

    async def test_make_request_client_with_logger_logs_on_non_2xx(
        self,
        make_mock_http_response,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that _make_request calls client.logger.debug on non-2xx.

        This test verifies by:
        1. Adding logger to mock_client
        2. Returning 404 response
        3. Asserting logger.debug was called

        Assumptions:
        - hasattr(client, 'logger') triggers debug log on non-2xx
        """
        mock_resp = make_mock_http_response(
            status=404,
            text="Not Found",
        )
        _, mock_client = make_mock_make_request_client(mock_resp)
        mock_client.logger = MagicMock()

        await _make_request(
            client=mock_client,
            route="/missing",
            api_key="sk-test",
            url="https://api.example.com",
            method="GET",
            retries=1,
        )

        mock_client.logger.debug.assert_called()

    async def test_make_request_non_stream_retryable_retries_then_returns(
        self,
        make_mock_http_response,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that non-stream path retries on retryable status then returns.

        This test verifies by:
        1. First attempt returns 429, second returns 400
        2. Patching asyncio.sleep
        3. Asserting result from final attempt

        Assumptions:
        - Retryable triggers sleep and continue; final non-retryable returns
        """
        mock_resp_429 = make_mock_http_response(status=429, text="Too Many")
        mock_resp_400 = make_mock_http_response(status=400, text="Bad")

        mock_session = MagicMock()
        mock_session.get = AsyncMock(
            side_effect=[mock_resp_429, mock_resp_400]
        )
        mock_session.post = AsyncMock()

        mock_client = MagicMock()
        mock_client._get_session = AsyncMock(return_value=mock_session)
        mock_client.get_ssl_context = AsyncMock(return_value=None)

        with patch(
            "vastai.serverless.client.connection.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await _make_request(
                client=mock_client,
                route="/rate",
                api_key="sk-test",
                url="https://api.example.com",
                method="GET",
                retries=2,
            )

        assert result["ok"] is False
        assert result["status"] == 400
        assert result["attempt"] == 2

    async def test_make_request_non_stream_exception_retries_then_raises(
        self,
        make_mock_make_request_client,
        patch_build_kwargs,
    ) -> None:
        """
        Verifies that non-stream path retries on exception then raises on last.

        This test verifies by:
        1. First attempt raises, second raises
        2. Asserting exception propagates on last attempt

        Assumptions:
        - Exception triggers sleep and retry; last attempt raises
        """
        mock_session = MagicMock()
        mock_session.get = AsyncMock(side_effect=OSError("network"))
        mock_session.post = AsyncMock()

        mock_client = MagicMock()
        mock_client._get_session = AsyncMock(return_value=mock_session)
        mock_client.get_ssl_context = AsyncMock(return_value=None)

        with patch(
            "vastai.serverless.client.connection.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            with pytest.raises(OSError, match="network"):
                await _make_request(
                    client=mock_client,
                    route="/fail",
                    api_key="sk-test",
                    url="https://api.example.com",
                    method="GET",
                    retries=2,
                )
