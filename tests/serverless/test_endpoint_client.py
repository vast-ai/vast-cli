"""Unit tests for vastai.serverless.client.endpoint (Endpoint, RouteResponse).

Uses ``mock_serverless_client`` / ``make_delegate_endpoint`` for fast delegation-only checks.
``test_client_endpoint.py`` exercises the same surface with the real ``client`` fixture and
HTTP/route patches; keep the split to avoid duplicating heavy setup in every delegation test.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vastai.serverless.client.endpoint import Endpoint, RouteResponse


class TestEndpointInit:
    """Endpoint constructor validation and repr."""

    def test_init_raises_without_client(self) -> None:
        """
        Verifies Endpoint requires a client reference.

        This test verifies by:
        1. Passing client=None
        2. Asserting ValueError

        Assumptions:
        - Validation message mentions client reference
        """
        with pytest.raises(ValueError):
            Endpoint(None, "n", 1, "k")

    def test_init_raises_on_empty_name(self, make_delegate_endpoint) -> None:
        """
        Verifies Endpoint rejects an empty name.

        This test verifies by:
        1. Passing name=""
        2. Asserting ValueError

        Assumptions:
        - Falsy string names are rejected
        """
        with pytest.raises(ValueError):
            make_delegate_endpoint(name=None, api_key="k")

    def test_init_raises_on_none_id(self, make_delegate_endpoint) -> None:
        """
        Verifies Endpoint rejects a None id.

        This test verifies by:
        1. Passing id=None
        2. Asserting ValueError

        Assumptions:
        - id must be non-None (including 0 is valid if passed explicitly)
        """
        with pytest.raises(ValueError):
            make_delegate_endpoint(name="n", endpoint_id=None, api_key="k")

    def test_repr_contains_name_and_id(self, make_delegate_endpoint) -> None:
        """
        Verifies __repr__ includes endpoint name and id.

        This test verifies by:
        1. Constructing Endpoint
        2. Asserting repr substrings

        Assumptions:
        - __repr__ format matches endpoint.py implementation
        """
        ep = make_delegate_endpoint(name="my-ep", endpoint_id=42, api_key="k")
        r = repr(ep)
        assert "my-ep" in r
        assert "42" in r


class TestEndpointDelegatesToClient:
    """Endpoint methods forward to the Serverless client."""

    def test_request_forwards_to_queue_endpoint_request(
        self, mock_serverless_client, make_delegate_endpoint, make_session_mock
    ) -> None:
        """
        Verifies request passes route, payload, and options to client.queue_endpoint_request.

        This test verifies by:
        1. Calling ep.request with known arguments including session sentinel
        2. Asserting queue_endpoint_request kwargs

        Assumptions:
        - client.queue_endpoint_request is synchronous and returns the mock return value
        """
        ep = make_delegate_endpoint()
        sess = make_session_mock()
        out = ep.request(
            "/do",
            {"x": 1},
            serverless_request="sr",
            cost=10,
            retry=False,
            stream=True,
            timeout=5.0,
            session=sess,
        )
        assert out == "queued"
        mock_serverless_client.queue_endpoint_request.assert_called_once()
        kw = mock_serverless_client.queue_endpoint_request.call_args.kwargs
        assert kw["endpoint"] is ep
        assert kw["worker_route"] == "/do"
        assert kw["worker_payload"] == {"x": 1}
        assert kw["serverless_request"] == "sr"
        assert kw["cost"] == 10
        assert kw["retry"] is False
        assert kw["stream"] is True
        assert kw["timeout"] == 5.0
        assert kw["session"] is sess

    def test_request_uses_defaults_for_optional_queue_kwargs(
        self, mock_serverless_client, make_delegate_endpoint
    ) -> None:
        """Default ``cost``, ``retry``, ``stream``, ``timeout``, ``session``, ``serverless_request``."""
        ep = make_delegate_endpoint()
        ep.request("/r", {})
        mock_serverless_client.queue_endpoint_request.assert_called_once()
        kw = mock_serverless_client.queue_endpoint_request.call_args.kwargs
        assert kw["cost"] == 100
        assert kw["retry"] is True
        assert kw["stream"] is False
        assert kw["timeout"] is None
        assert kw["session"] is None
        assert kw["serverless_request"] is None

    @pytest.mark.asyncio
    async def test_close_session_forwards_to_client(
        self, mock_serverless_client, make_delegate_endpoint, make_session_mock
    ) -> None:
        """
        Verifies close_session delegates to client.end_endpoint_session.

        This test verifies by:
        1. Calling ep.close_session(session) and awaiting the result
        2. Asserting end_endpoint_session was awaited with session=

        Assumptions:
        - close_session returns the awaitable from end_endpoint_session
        """
        ep = make_delegate_endpoint()
        sess = make_session_mock()
        await ep.close_session(sess)
        mock_serverless_client.end_endpoint_session.assert_awaited_once_with(
            session=sess
        )

    @pytest.mark.asyncio
    async def test_get_session_forwards_kwargs(
        self, mock_serverless_client, make_delegate_endpoint
    ) -> None:
        """
        Verifies get_session passes session_id, session_auth, timeout to client.

        This test verifies by:
        1. Awaiting ep.get_session with known values
        2. Asserting get_endpoint_session await args

        Assumptions:
        - get_session returns the coroutine from client.get_endpoint_session
        """
        ep = make_delegate_endpoint()
        auth = {"url": "https://x"}
        await ep.get_session(9, auth, timeout=3.0)
        mock_serverless_client.get_endpoint_session.assert_awaited_once_with(
            endpoint=ep, session_id=9, session_auth=auth, timeout=3.0
        )

    @pytest.mark.asyncio
    async def test_get_session_default_timeout_is_ten(
        self, mock_serverless_client, make_delegate_endpoint
    ) -> None:
        ep = make_delegate_endpoint()
        await ep.get_session(1, {"k": "v"})
        mock_serverless_client.get_endpoint_session.assert_awaited_once_with(
            endpoint=ep,
            session_id=1,
            session_auth={"k": "v"},
            timeout=10.0,
        )

    @pytest.mark.asyncio
    async def test_session_forwards_to_start_endpoint_session(
        self, mock_serverless_client, make_delegate_endpoint
    ) -> None:
        """
        Verifies session() awaits client.start_endpoint_session (coroutine from real client).

        This test verifies by:
        1. Awaiting ep.session with cost, lifetime, on_close_* , timeout
        2. Asserting start_endpoint_session await kwargs

        Assumptions:
        - ``Endpoint.session`` returns the coroutine from ``start_endpoint_session``
        """
        ep = make_delegate_endpoint()
        out = await ep.session(
            cost=20,
            lifetime=45.0,
            on_close_route="/bye",
            on_close_payload={"a": 1},
            timeout=99.0,
        )
        assert out == "started"
        mock_serverless_client.start_endpoint_session.assert_awaited_once_with(
            endpoint=ep,
            cost=20,
            lifetime=45.0,
            on_close_route="/bye",
            on_close_payload={"a": 1},
            timeout=99.0,
        )

    @pytest.mark.asyncio
    async def test_session_uses_defaults_for_optional_start_kwargs(
        self, mock_serverless_client, make_delegate_endpoint
    ) -> None:
        ep = make_delegate_endpoint()
        await ep.session()
        mock_serverless_client.start_endpoint_session.assert_awaited_once_with(
            endpoint=ep,
            cost=100,
            lifetime=60,
            on_close_route=None,
            on_close_payload=None,
            timeout=None,
        )

    @pytest.mark.asyncio
    async def test_get_workers_forwards_self(
        self, mock_serverless_client, make_delegate_endpoint
    ) -> None:
        """
        Verifies get_workers calls client.get_endpoint_workers with this endpoint.

        This test verifies by:
        1. Awaiting ep.get_workers()

        Assumptions:
        - get_endpoint_workers is async on the client mock
        """
        ep = make_delegate_endpoint()
        await ep.get_workers()
        mock_serverless_client.get_endpoint_workers.assert_awaited_once_with(ep)


@pytest.mark.asyncio
class TestEndpointSessionHealthcheck:
    async def test_session_healthcheck_true_when_session_exists(
        self, mock_serverless_client, make_delegate_endpoint, make_session_mock
    ) -> None:
        """
        Verifies session_healthcheck returns True when get_endpoint_session returns non-None.

        This test verifies by:
        1. Configuring get_endpoint_session to return an object
        2. Awaiting session_healthcheck
        3. Asserting True

        Assumptions:
        - Health is defined as result is not None
        """
        mock_serverless_client.get_endpoint_session = AsyncMock(
            return_value=MagicMock()
        )
        ep = make_delegate_endpoint()
        sess = make_session_mock(session_id="sid", auth_data={"t": 1})
        ok = await ep.session_healthcheck(sess)
        assert ok is True

    async def test_session_healthcheck_false_when_no_session(
        self, mock_serverless_client, make_delegate_endpoint, make_session_mock
    ) -> None:
        """
        Verifies session_healthcheck returns False when get_endpoint_session returns None.

        This test verifies by:
        1. Configuring get_endpoint_session to return None
        2. Awaiting session_healthcheck

        Assumptions:
        - Client returns None for missing/expired session
        """
        mock_serverless_client.get_endpoint_session = AsyncMock(return_value=None)
        ep = make_delegate_endpoint()
        sess = make_session_mock(session_id="sid", auth_data={})
        ok = await ep.session_healthcheck(sess)
        assert ok is False


@pytest.mark.asyncio
class TestEndpointRoute:
    async def test_route_passes_default_body_fields_to_make_request(
        self, mock_serverless_client, make_delegate_endpoint
    ) -> None:
        """No-arg ``_route()`` uses cost 0, request_idx 0, replay_timeout 60."""
        ep = make_delegate_endpoint()
        fake = {"ok": True, "json": {"url": "https://w"}}
        with patch(
            "vastai.serverless.client.endpoint._make_request",
            new_callable=AsyncMock,
            return_value=fake,
        ) as m:
            await ep._route()
        body = m.call_args.kwargs["body"]
        assert body["cost"] == 0.0
        assert body["request_idx"] == 0
        assert body["replay_timeout"] == 60.0

    async def test_route_returns_waiting_when_json_payload_missing(
        self, mock_serverless_client, make_delegate_endpoint
    ) -> None:
        """``ok`` with no ``json`` key → empty body → WAITING (no ``url``)."""
        ep = make_delegate_endpoint()
        with patch(
            "vastai.serverless.client.endpoint._make_request",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ):
            route = await ep._route()
        assert route.status == "WAITING"
        assert route.get_url() is None

    async def test_route_returns_waiting_when_json_is_none(
        self, mock_serverless_client, make_delegate_endpoint
    ) -> None:
        """``json: None`` normalizes to ``{}`` → WAITING."""
        ep = make_delegate_endpoint()
        with patch(
            "vastai.serverless.client.endpoint._make_request",
            new_callable=AsyncMock,
            return_value={"ok": True, "json": None},
        ):
            route = await ep._route()
        assert route.status == "WAITING"
        assert route.get_url() is None

    async def test_route_http_error_truncates_response_text_in_message(
        self, mock_serverless_client, make_delegate_endpoint
    ) -> None:
        long = "E" * 700
        ep = make_delegate_endpoint()
        with patch(
            "vastai.serverless.client.endpoint._make_request",
            new_callable=AsyncMock,
            return_value={"ok": False, "status": 503, "text": long},
        ):
            with pytest.raises(RuntimeError, match="HTTP 503") as ei:
                await ep._route()
        msg = str(ei.value)
        assert "E" * 512 in msg
        assert "E" * 513 not in msg

    async def test_route_returns_ready_route_response(
        self, mock_serverless_client, make_delegate_endpoint
    ) -> None:
        """
        Verifies _route returns RouteResponse with READY when JSON includes url.

        This test verifies by:
        1. Patching endpoint module _make_request with ok json containing url
        2. Awaiting _route
        3. Asserting status READY and get_url()

        Assumptions:
        - Patch applied where endpoint.py resolves _make_request
        """
        ep = make_delegate_endpoint()
        fake = {"ok": True, "json": {"request_idx": 3, "url": "https://w"}}
        with patch(
            "vastai.serverless.client.endpoint._make_request",
            new_callable=AsyncMock,
            return_value=fake,
        ):
            route = await ep._route(cost=1.0, req_idx=0, timeout=30.0)
        assert route.status == "READY"
        assert route.request_idx == 3
        assert route.get_url() == "https://w"

    async def test_route_wraps_make_request_failure_as_runtime_error(
        self, mock_serverless_client, make_delegate_endpoint
    ) -> None:
        """
        Verifies _route wraps _make_request exceptions in RuntimeError.

        This test verifies by:
        1. Making _make_request raise OSError
        2. Asserting RuntimeError chain

        Assumptions:
        - Outer message mentions failed to route
        """
        ep = make_delegate_endpoint()
        with patch(
            "vastai.serverless.client.endpoint._make_request",
            new_callable=AsyncMock,
            side_effect=OSError("boom"),
        ):
            with pytest.raises(RuntimeError, match="Failed to route endpoint"):
                await ep._route()

    async def test_route_raises_when_http_not_ok(
        self, mock_serverless_client, make_delegate_endpoint
    ) -> None:
        """
        Verifies _route raises RuntimeError when result ok is False.

        This test verifies by:
        1. Returning ok=False from _make_request
        2. Awaiting _route

        Assumptions:
        - Error text includes HTTP status
        """
        ep = make_delegate_endpoint()
        with patch(
            "vastai.serverless.client.endpoint._make_request",
            new_callable=AsyncMock,
            return_value={"ok": False, "status": 502, "text": "bad"},
        ):
            with pytest.raises(RuntimeError, match="502"):
                await ep._route()


class TestRouteResponse:
    """RouteResponse parsing helpers."""

    def test_waiting_status_when_no_url(self) -> None:
        """
        Verifies RouteResponse uses WAITING when body has no url key.

        This test verifies by:
        1. Constructing RouteResponse from body without url
        2. Asserting status WAITING and default request_idx 0

        Assumptions:
        - READY requires url in body per endpoint.py
        """
        r = RouteResponse({"request_idx": 0})
        assert r.status == "WAITING"
        assert r.request_idx == 0

    def test_request_idx_defaults_when_absent(self) -> None:
        """
        Verifies request_idx defaults to 0 when missing.

        This test verifies by:
        1. Passing empty dict
        2. Asserting request_idx == 0

        Assumptions:
        - Branch in RouteResponse.__init__ for missing request_idx
        """
        r = RouteResponse({})
        assert r.request_idx == 0

    def test_repr_contains_status(self) -> None:
        """
        Verifies RouteResponse __repr__ includes status.

        This test verifies by:
        1. Building READY response
        2. Asserting repr substring

        Assumptions:
        - __repr__ format stable for debugging
        """
        r = RouteResponse({"url": "u"})
        assert "READY" in repr(r)

    def test_ready_with_url_defaults_request_idx_when_absent(self) -> None:
        """URL present implies READY; missing ``request_idx`` uses 0."""
        r = RouteResponse({"url": "https://worker"})
        assert r.status == "READY"
        assert r.request_idx == 0
        assert r.get_url() == "https://worker"

    def test_waiting_repr_contains_status(self) -> None:
        assert "WAITING" in repr(RouteResponse({"pending": True}))
