"""Unit tests for vastai.serverless.client.session.Session.

All endpoint I/O is mocked; no real network or API calls.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from vastai.serverless.client.session import Session


class TestSessionInit:
    """Verify Session constructor validation and attribute assignment."""

    def test_init_raises_when_endpoint_is_none(self) -> None:
        """
        Verifies that Session rejects a None endpoint.

        This test verifies by:
        1. Calling Session.__init__ with endpoint=None and other valid fields
        2. Asserting ValueError with the expected message

        Assumptions:
        - Validation order checks endpoint before other fields
        """
        with pytest.raises(ValueError, match="empty endpoint"):
            Session(
                endpoint=None,
                session_id="s",
                lifetime=1.0,
                expiration="e",
                url="https://u",
                auth_data={},
            )

    def test_init_raises_when_session_id_is_none(
        self, make_mock_endpoint_for_session
    ) -> None:
        """
        Verifies that Session rejects a None session_id.

        This test verifies by:
        1. Calling Session with a mock endpoint and session_id=None
        2. Asserting ValueError with the expected message

        Assumptions:
        - Mock endpoint satisfies non-None endpoint check
        """
        with pytest.raises(ValueError, match="empty session_id"):
            Session(
                endpoint=make_mock_endpoint_for_session(),
                session_id=None,
                lifetime=1.0,
                expiration="e",
                url="https://u",
                auth_data={},
            )

    def test_init_accepts_empty_string_session_id_documents_contract(
        self, make_mock_endpoint_for_session, make_client_session
    ) -> None:
        """
        Documents that only ``session_id is None`` is rejected; falsy strings are allowed.

        Callers cannot infer from the ``None`` check alone that ``""`` is invalid.
        """
        ep = make_mock_endpoint_for_session()
        session = make_client_session(endpoint=ep, session_id="")
        assert session.session_id == ""

    def test_init_raises_when_url_is_none(self, make_mock_endpoint_for_session) -> None:
        """
        Verifies that Session rejects a None url.

        This test verifies by:
        1. Calling Session with valid endpoint and session_id but url=None
        2. Asserting ValueError with the expected message

        Assumptions:
        - Endpoint and session_id are valid so url validation is reached
        """
        with pytest.raises(ValueError, match="empty url"):
            Session(
                endpoint=make_mock_endpoint_for_session(),
                session_id="s",
                lifetime=1.0,
                expiration="e",
                url=None,
                auth_data={},
            )

    def test_init_sets_attributes_and_open_state(
        self, make_mock_endpoint_for_session, make_client_session
    ) -> None:
        """
        Verifies that a valid Session stores constructor arguments and starts open.

        This test verifies by:
        1. Building a Session with known endpoint, ids, lifetime, expiration, url, auth
        2. Asserting fields match and open is True; optional on_close_* defaults

        Assumptions:
        - Mock endpoint is non-None; on_close_route/payload omitted default to None
        """
        ep = make_mock_endpoint_for_session()
        session = make_client_session(
            endpoint=ep,
            session_id="abc",
            lifetime=120.5,
            expiration="exp",
            url="https://x",
            auth_data={"k": "v"},
        )
        assert session.endpoint is ep
        assert session.session_id == "abc"
        assert session.lifetime == 120.5
        assert session.expiration == "exp"
        assert session.url == "https://x"
        assert session.auth_data == {"k": "v"}
        assert session.open is True
        assert session.on_close_route is None
        assert session.on_close_payload is None

    def test_init_sets_on_close_route_and_payload(
        self, make_mock_endpoint_for_session, make_client_session
    ) -> None:
        """Optional teardown hints from ``start_endpoint_session`` are stored on Session."""
        ep = make_mock_endpoint_for_session()
        session = make_client_session(
            endpoint=ep,
            on_close_route="/cleanup",
            on_close_payload={"reason": "idle"},
        )
        assert session.on_close_route == "/cleanup"
        assert session.on_close_payload == {"reason": "idle"}


class TestSessionAsyncContext:
    """Verify async context manager behavior."""

    @pytest.mark.asyncio
    async def test_aenter_returns_self(self, make_client_session) -> None:
        """
        Verifies that __aenter__ returns the Session instance.

        This test verifies by:
        1. Calling __aenter__ on a Session
        2. Asserting the return value is the same object

        Assumptions:
        - No I/O occurs in __aenter__
        """
        session = make_client_session()
        entered = await session.__aenter__()
        assert entered is session

    @pytest.mark.asyncio
    async def test_aexit_returns_false_so_exceptions_propagate(
        self, make_client_session
    ) -> None:
        """``__aexit__`` must not swallow exceptions from the ``async with`` body."""
        session = make_client_session()
        await session.__aenter__()
        assert await session.__aexit__(None, None, None) is False

    @pytest.mark.asyncio
    async def test_aexit_awaits_close(self, session_on_mock_endpoint) -> None:
        """
        Verifies that __aexit__ invokes close so the session is shut down.

        This test verifies by:
        1. Using a mock endpoint with AsyncMock close_session
        2. Awaiting __aexit__(None, None, None)
        3. Asserting close_session was awaited and session.open is False

        Assumptions:
        - close() delegates to endpoint.close_session as implemented
        """
        ep, session = session_on_mock_endpoint
        await session.__aexit__(None, None, None)
        ep.close_session.assert_awaited_once_with(session)
        assert session.open is False


class TestSessionIsOpen:
    """Verify session_healthcheck integration."""

    @pytest.mark.asyncio
    async def test_is_open_returns_true_and_sets_open_when_healthcheck_true(
        self, session_on_mock_endpoint
    ) -> None:
        """
        Verifies is_open delegates to endpoint.session_healthcheck and updates open.

        This test verifies by:
        1. Configuring session_healthcheck to return True
        2. Calling await session.is_open()
        3. Asserting return value True and session.open is True

        Assumptions:
        - session_healthcheck receives the Session instance as argument
        """
        ep, session = session_on_mock_endpoint
        ep.session_healthcheck = AsyncMock(return_value=True)
        result = await session.is_open()
        assert result is True
        assert session.open is True
        ep.session_healthcheck.assert_awaited_once_with(session)

    @pytest.mark.asyncio
    async def test_is_open_returns_false_and_sets_open_when_healthcheck_false(
        self, session_on_mock_endpoint
    ) -> None:
        """
        Verifies is_open reflects a failed health check.

        This test verifies by:
        1. Configuring session_healthcheck to return False
        2. Calling await session.is_open()
        3. Asserting return value False and session.open is False

        Assumptions:
        - Implementation assigns self.open from the healthcheck result
        """
        ep, session = session_on_mock_endpoint
        ep.session_healthcheck = AsyncMock(return_value=False)
        result = await session.is_open()
        assert result is False
        assert session.open is False


class TestSessionClose:
    """Verify close() idempotency and error handling."""

    @pytest.mark.asyncio
    async def test_close_returns_none_when_already_closed(
        self, session_on_mock_endpoint
    ) -> None:
        """
        Verifies close is a no-op when the session is already marked closed.

        This test verifies by:
        1. Setting session.open to False
        2. Awaiting close()
        3. Asserting None return and close_session not called

        Assumptions:
        - Early return uses self.open before touching _closing
        """
        ep, session = session_on_mock_endpoint
        session.open = False
        out = await session.close()
        assert out is None
        ep.close_session.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_close_awaits_endpoint_close_session_and_clears_open(
        self, session_on_mock_endpoint
    ) -> None:
        """
        Verifies close calls endpoint.close_session and sets open to False.

        This test verifies by:
        1. Awaiting close() on an open session
        2. Asserting close_session awaited once with session and open is False

        Assumptions:
        - close_session completes without raising
        """
        ep, session = session_on_mock_endpoint
        await session.close()
        ep.close_session.assert_awaited_once_with(session)
        assert session.open is False

    @pytest.mark.asyncio
    async def test_close_sets_open_false_when_close_session_raises(
        self, session_on_mock_endpoint, caplog
    ) -> None:
        """
        Verifies close still clears open if endpoint.close_session fails.

        This test verifies by:
        1. Making close_session raise RuntimeError
        2. Awaiting close() and asserting session.open is False
        3. Asserting a warning was logged so logging regressions are visible

        Assumptions:
        - finally block in close() always sets open False
        """
        ep, session = session_on_mock_endpoint
        ep.close_session = AsyncMock(side_effect=RuntimeError("network"))
        logging.getLogger("vastai").propagate = True
        with caplog.at_level(
            logging.WARNING, logger="vastai.serverless.client.session"
        ):
            await session.close()
        assert session.open is False
        assert any(
            "Error closing session" in r.message and "network" in r.message
            for r in caplog.records
        )

    @pytest.mark.asyncio
    async def test_close_second_call_does_not_await_close_session_again(
        self, session_on_mock_endpoint
    ) -> None:
        """
        Verifies sequential close calls only hit the endpoint once.

        This test verifies by:
        1. Awaiting close() twice
        2. Asserting close_session await count is 1

        Assumptions:
        - After first close, open is False so second call returns immediately
        """
        ep, session = session_on_mock_endpoint
        await session.close()
        await session.close()
        assert ep.close_session.await_count == 1

    @pytest.mark.asyncio
    async def test_close_skips_when_closing_guard_set(
        self, session_on_mock_endpoint
    ) -> None:
        """
        Verifies a second close while _closing is True does not call close_session again.

        This test verifies by:
        1. Setting _closing True while open remains True (simulates in-flight close)
        2. Awaiting close()
        3. Asserting close_session was not invoked

        Assumptions:
        - Guard check uses _closing before starting work; used for re-entrancy
        """
        ep, session = session_on_mock_endpoint
        session._closing = True
        await session.close()
        ep.close_session.assert_not_awaited()


class TestSessionRequest:
    """Verify request() forwards to the endpoint and handles 410."""

    def test_request_raises_when_session_closed(self, make_client_session) -> None:
        """
        Verifies request refuses immediately when the session is closed.

        This test verifies by:
        1. Setting session.open to False
        2. Calling request() synchronously
        3. Asserting ValueError before any await

        Assumptions:
        - Closed check runs before building the inner coroutine
        """
        session = make_client_session()
        session.open = False
        with pytest.raises(ValueError, match="closed session"):
            session.request("/r", {"a": 1})

    @pytest.mark.asyncio
    async def test_request_awaitable_returns_endpoint_result(
        self, session_on_mock_endpoint
    ) -> None:
        """
        Verifies awaiting request() returns the JSON dict from endpoint.request.

        This test verifies by:
        1. Configuring endpoint.request AsyncMock to return a known dict
        2. Awaiting session.request(...)

        Assumptions:
        - endpoint.request is awaitable in tests via AsyncMock
        """
        ep, session = session_on_mock_endpoint
        ep.request = AsyncMock(return_value={"status": 200, "data": 42})
        coro = session.request("/path", {"x": 1}, cost=50, retry=False, stream=True)
        result = await coro
        assert result == {"status": 200, "data": 42}
        ep.request.assert_awaited_once()
        call_kw = ep.request.await_args.kwargs
        assert call_kw["route"] == "/path"
        assert call_kw["payload"] == {"x": 1}
        assert call_kw["cost"] == 50
        assert call_kw["retry"] is False
        assert call_kw["stream"] is True
        assert call_kw["session"] is session
        assert call_kw["serverless_request"] is None

    @pytest.mark.asyncio
    async def test_request_passes_serverless_request_through(
        self, session_on_mock_endpoint
    ) -> None:
        """
        Verifies request forwards serverless_request to endpoint.request.

        This test verifies by:
        1. Passing a sentinel object as serverless_request
        2. Awaiting the returned coroutine
        3. Asserting the same object appears in endpoint.request kwargs

        Assumptions:
        - Session does not wrap or replace serverless_request
        """
        ep, session = session_on_mock_endpoint
        sr = MagicMock(name="serverless_request")
        await session.request("/r", {}, serverless_request=sr)
        assert ep.request.await_args.kwargs["serverless_request"] is sr

    @pytest.mark.asyncio
    async def test_request_status_410_marks_closed_and_raises(
        self, session_on_mock_endpoint
    ) -> None:
        """
        Verifies a 410 response marks the session closed and raises ValueError.

        This test verifies by:
        1. Returning {"status": 410} from endpoint.request
        2. Awaiting session.request(...)
        3. Asserting ValueError and session.open is False

        Assumptions:
        - Wrapped handler treats HTTP gone (status 410) as a closed session
        """
        ep, session = session_on_mock_endpoint
        ep.request = AsyncMock(return_value={"status": 410})
        with pytest.raises(ValueError, match="closed session"):
            await session.request("/r", {})
        assert session.open is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_result", [None, "not-a-dict", 404])
    async def test_request_propagates_attribute_error_when_result_not_mapping(
        self, session_on_mock_endpoint, bad_result
    ) -> None:
        """
        ``_wrapped_request`` uses ``result.get``; non-mapping results surface as AttributeError.

        Endpoint.request is expected to return a mapping with optional ``status``.
        This documents current behavior; a stricter API might raise ``ValueError`` instead.
        """
        ep, session = session_on_mock_endpoint
        ep.request = AsyncMock(return_value=bad_result)
        with pytest.raises(AttributeError):
            await session.request("/r", {})
