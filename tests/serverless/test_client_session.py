"""Unit tests for vastai.serverless.client.session Session class.

Tests Session initialization, validation, async context manager,
is_open healthcheck, close idempotency, and request forwarding.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from vastai.serverless.client.client import ServerlessRequest
from vastai.serverless.client.session import Session


# ---------------------------------------------------------------------------
# Session.__init__ validation
# ---------------------------------------------------------------------------


class TestSessionInit:
    """Verify Session creation and validation."""

    def test_valid_creation(self, sample_endpoint) -> None:
        """
        Verifies that Session is created with all valid parameters.

        This test verifies by:
        1. Creating Session with all required args
        2. Asserting attributes are set correctly including defaults

        Assumptions:
        - Session sets open=True and _closing=False on creation
        """
        session = Session(
            endpoint=sample_endpoint,
            session_id="sess-1",
            lifetime=120.0,
            expiration="2026-12-31T00:00:00Z",
            url="https://worker.vast.ai",
            auth_data={"url": "https://worker.vast.ai"},
        )
        assert session.endpoint is sample_endpoint
        assert session.session_id == "sess-1"
        assert session.lifetime == 120.0
        assert session.expiration == "2026-12-31T00:00:00Z"
        assert session.url == "https://worker.vast.ai"
        assert session.auth_data == {"url": "https://worker.vast.ai"}
        assert session.open is True
        assert session._closing is False
        assert session.on_close_route is None
        assert session.on_close_payload is None

    def test_creation_with_on_close_params(self, sample_endpoint) -> None:
        """
        Verifies that Session stores on_close_route and on_close_payload.

        This test verifies by:
        1. Creating Session with on_close_route and on_close_payload
        2. Asserting they are stored correctly

        Assumptions:
        - on_close_route and on_close_payload are optional kwargs
        """
        session = Session(
            endpoint=sample_endpoint,
            session_id="sess-2",
            lifetime=60.0,
            expiration="2026-12-31",
            url="https://w.vast.ai",
            auth_data={},
            on_close_route="/cleanup",
            on_close_payload={"action": "release"},
        )
        assert session.on_close_route == "/cleanup"
        assert session.on_close_payload == {"action": "release"}

    def test_raises_when_endpoint_is_none(self) -> None:
        """
        Verifies that Session raises ValueError when endpoint is None.

        This test verifies by:
        1. Calling Session(endpoint=None, ...)
        2. Asserting ValueError with expected message

        Assumptions:
        - __init__ checks endpoint is not None
        """
        with pytest.raises(ValueError, match="empty endpoint"):
            Session(
                endpoint=None,
                session_id="s1",
                lifetime=60,
                expiration="x",
                url="https://w.vast.ai",
                auth_data={},
            )

    def test_raises_when_session_id_is_none(self, sample_endpoint) -> None:
        """
        Verifies that Session raises ValueError when session_id is None.

        This test verifies by:
        1. Calling Session with session_id=None
        2. Asserting ValueError with expected message

        Assumptions:
        - __init__ checks session_id is not None
        """
        with pytest.raises(ValueError, match="empty session_id"):
            Session(
                endpoint=sample_endpoint,
                session_id=None,
                lifetime=60,
                expiration="x",
                url="https://w.vast.ai",
                auth_data={},
            )

    def test_raises_when_url_is_none(self, sample_endpoint) -> None:
        """
        Verifies that Session raises ValueError when url is None.

        This test verifies by:
        1. Calling Session with url=None
        2. Asserting ValueError with expected message

        Assumptions:
        - __init__ checks url is not None
        """
        with pytest.raises(ValueError, match="empty url"):
            Session(
                endpoint=sample_endpoint,
                session_id="s1",
                lifetime=60,
                expiration="x",
                url=None,
                auth_data={},
            )

    def test_accepts_empty_string_session_id(self, sample_endpoint) -> None:
        """Documents that only ``None`` is rejected for ``session_id``, not ``""``."""
        s = Session(
            endpoint=sample_endpoint,
            session_id="",
            lifetime=60,
            expiration="x",
            url="https://w.vast.ai",
            auth_data={},
        )
        assert s.session_id == ""

    def test_accepts_empty_string_url(self, sample_endpoint) -> None:
        """Documents that only ``None`` is rejected for ``url``, not ``""``."""
        s = Session(
            endpoint=sample_endpoint,
            session_id="s1",
            lifetime=60,
            expiration="x",
            url="",
            auth_data={},
        )
        assert s.url == ""


# ---------------------------------------------------------------------------
# Session async context manager
# ---------------------------------------------------------------------------


class TestSessionContextManager:
    """Verify Session works as an async context manager."""

    async def test_aenter_returns_self(self, sample_session) -> None:
        """
        Verifies that __aenter__ returns the session itself.

        This test verifies by:
        1. Using async with on session
        2. Asserting yielded value is the session

        Assumptions:
        - __aenter__ returns self
        """
        # We need to mock close to avoid actual close logic
        sample_session.endpoint.close_session = AsyncMock()
        async with sample_session as s:
            assert s is sample_session

    async def test_aexit_calls_close(self, sample_session) -> None:
        """
        Verifies that __aexit__ calls close on the session.

        This test verifies by:
        1. Mocking endpoint.close_session
        2. Using async with
        3. After exit, asserting session.open is False

        Assumptions:
        - __aexit__ calls self.close() which calls endpoint.close_session
        """
        sample_session.endpoint.close_session = AsyncMock()
        async with sample_session:
            assert sample_session.open is True
        assert sample_session.open is False

    async def test_aexit_returns_false(self, sample_session) -> None:
        """
        Verifies that __aexit__ returns False (does not suppress exceptions).

        This test verifies by:
        1. Calling __aexit__ directly
        2. Asserting return is False

        Assumptions:
        - __aexit__ returns False per implementation
        """
        sample_session.endpoint.close_session = AsyncMock()
        result = await sample_session.__aexit__(None, None, None)
        assert result is False


# ---------------------------------------------------------------------------
# Session.is_open
# ---------------------------------------------------------------------------


class TestSessionIsOpen:
    """Verify Session.is_open checks healthcheck and updates state."""

    async def test_is_open_returns_true_when_healthcheck_passes(
        self, sample_session, mock_serverless_client
    ) -> None:
        """
        Verifies that is_open returns True when healthcheck succeeds.

        This test verifies by:
        1. Configuring ``mock_serverless_client.get_endpoint_session`` to return a session
           object (what :meth:`~Endpoint.session_healthcheck` awaits internally)
        2. Calling is_open
        3. Asserting result is True and session.open is True

        Assumptions:
        - is_open delegates to endpoint.session_healthcheck → get_endpoint_session
        """
        mock_serverless_client.get_endpoint_session.return_value = MagicMock()
        result = await sample_session.is_open()
        assert result is True
        assert sample_session.open is True

    async def test_is_open_returns_false_when_healthcheck_fails(
        self, sample_session, mock_serverless_client
    ) -> None:
        """
        Verifies that is_open returns False and updates open when healthcheck fails.

        This test verifies by:
        1. Configuring ``mock_serverless_client.get_endpoint_session`` to return ``None``
        2. Calling is_open
        3. Asserting result is False and session.open is False

        Assumptions:
        - is_open sets self.open from session_healthcheck (non-None → healthy)
        """
        mock_serverless_client.get_endpoint_session.return_value = None
        result = await sample_session.is_open()
        assert result is False
        assert sample_session.open is False


# ---------------------------------------------------------------------------
# Session.close
# ---------------------------------------------------------------------------


class TestSessionClose:
    """Verify Session.close calls endpoint and is idempotent."""

    async def test_close_calls_endpoint_close_session(
        self, sample_session, mock_serverless_client
    ) -> None:
        """
        Verifies that close calls endpoint.close_session with self.

        This test verifies by:
        1. Calling close
        2. Asserting endpoint.close_session was called
        3. Asserting session.open is False

        Assumptions:
        - close delegates to endpoint.close_session(self)
        """
        await sample_session.close()
        mock_serverless_client.end_endpoint_session.assert_called_once_with(session=sample_session)
        assert sample_session.open is False

    async def test_close_is_idempotent(
        self, sample_session, mock_serverless_client
    ) -> None:
        """
        Verifies that calling close multiple times only closes once.

        This test verifies by:
        1. Calling close twice
        2. Asserting endpoint.close_session called only once

        Assumptions:
        - _closing guard prevents re-entry
        """
        await sample_session.close()
        await sample_session.close()
        mock_serverless_client.end_endpoint_session.assert_called_once()

    async def test_close_noop_when_already_closed(
        self, sample_session, mock_serverless_client
    ) -> None:
        """
        Verifies that close returns None when session already not open.

        This test verifies by:
        1. Setting session.open = False
        2. Calling close
        3. Asserting result is None and endpoint.close_session not called

        Assumptions:
        - close checks self.open first
        """
        sample_session.open = False
        result = await sample_session.close()
        assert result is None
        mock_serverless_client.end_endpoint_session.assert_not_called()

    async def test_close_sets_open_false_even_on_error(
        self, sample_session, mock_serverless_client
    ) -> None:
        """
        Verifies that close sets open=False even when endpoint.close_session raises.

        This test verifies by:
        1. Mocking endpoint.close_session to raise
        2. Calling close
        3. Asserting session.open is False (finally block)

        Assumptions:
        - close has finally block that sets open=False
        """
        mock_serverless_client.end_endpoint_session.side_effect = Exception("network error")
        await sample_session.close()
        assert sample_session.open is False


# ---------------------------------------------------------------------------
# Session.request
# ---------------------------------------------------------------------------


class TestSessionRequest:
    """Verify Session.request forwards to endpoint and checks open state."""

    def test_request_raises_when_session_closed(self, sample_session) -> None:
        """
        Verifies that request raises ValueError when session is closed.

        This test verifies by:
        1. Setting session.open = False
        2. Calling request
        3. Asserting ValueError raised

        Assumptions:
        - request checks self.open before proceeding
        """
        sample_session.open = False
        with pytest.raises(ValueError, match="closed session"):
            sample_session.request(route="/predict", payload={"input": "test"})

    def test_request_returns_awaitable_when_open(
        self, sample_session, mock_serverless_client
    ) -> None:
        """
        Verifies that request returns a coroutine when session is open.

        This test verifies by:
        1. Calling request on an open session
        2. Asserting result is a coroutine (awaitable)

        Assumptions:
        - request returns _wrapped_request() which is a coroutine
        """
        mock_serverless_client.queue_endpoint_request = MagicMock(return_value=MagicMock())
        result = sample_session.request(route="/predict", payload={"input": "test"})
        assert asyncio.iscoroutine(result)
        # Clean up the coroutine
        result.close()

    async def test_request_delegates_to_endpoint_request(
        self, sample_session, mock_serverless_client
    ) -> None:
        """
        Verifies that request forwards to the client via ``queue_endpoint_request``.

        This test verifies by:
        1. Stubbing ``queue_endpoint_request`` with a resolved :class:`ServerlessRequest`
           (sync API on :class:`Serverless`; return value is awaitable as a Future)
        2. Awaiting ``session.request(...)``
        3. Asserting ``queue_endpoint_request`` kwargs (worker_route, payload, session, …)

        Assumptions:
        - _wrapped_request awaits the object returned by ``endpoint.request`` (a Future)
        """
        resolved = ServerlessRequest()
        resolved.set_result(
            {"ok": True, "status": 200, "response": {"result": "ok"}}
        )
        mock_serverless_client.queue_endpoint_request = MagicMock(return_value=resolved)
        result = await sample_session.request(
            route="/predict",
            payload={"input": "test"},
            cost=75,
            retry=False,
            stream=True,
        )
        mock_serverless_client.queue_endpoint_request.assert_called_once()
        call_kwargs = mock_serverless_client.queue_endpoint_request.call_args[1]
        assert call_kwargs["worker_route"] == "/predict"
        assert call_kwargs["worker_payload"] == {"input": "test"}
        assert call_kwargs["cost"] == 75
        assert call_kwargs["retry"] is False
        assert call_kwargs["stream"] is True
        assert call_kwargs["session"] is sample_session

    async def test_request_closes_session_on_410_status(
        self, sample_session, mock_serverless_client
    ) -> None:
        """
        Verifies that request sets session.open=False and raises on HTTP 410.

        This test verifies by:
        1. Mocking queue_endpoint_request to return status=410
        2. Awaiting request
        3. Asserting ValueError raised and session.open is False

        Assumptions:
        - _wrapped_request checks status == 410 and closes session
        """
        mock_serverless_client.queue_endpoint_request = AsyncMock(
            return_value={"ok": False, "status": 410, "response": None}
        )
        with pytest.raises(ValueError, match="closed session"):
            await sample_session.request(route="/predict", payload={})
        assert sample_session.open is False
