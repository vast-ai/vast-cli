"""Unit tests for vastai.serverless.client.client Serverless and ServerlessRequest classes.

Tests Serverless initialization (API key validation, instance URL mapping, debug logging),
connection lifecycle (is_open, close), endpoint retrieval, worker retrieval,
session management, and ServerlessRequest future behavior.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from vastai.serverless.client.client import Serverless, ServerlessRequest
from vastai.serverless.client.endpoint import Endpoint
from vastai.serverless.client.worker import Worker
from vastai.serverless.client.session import Session


# ---------------------------------------------------------------------------
# ServerlessRequest
# ---------------------------------------------------------------------------


class TestServerlessRequest:
    """Verify ServerlessRequest is an asyncio.Future with status tracking."""

    def test_initial_status_is_new(self) -> None:
        """
        Verifies that a new ServerlessRequest has status "New".

        This test verifies by:
        1. Creating a ServerlessRequest
        2. Asserting status == "New"

        Assumptions:
        - __init__ sets status to "New"
        """
        req = ServerlessRequest()
        assert req.status == "New"
        assert req.start_time is None
        assert req.complete_time is None
        assert req.req_idx == 0

    async def test_then_registers_callback(self) -> None:
        """
        Verifies that .then() registers a done callback.

        This test verifies by:
        1. Creating a ServerlessRequest inside running event loop
        2. Calling .then(callback)
        3. Setting result and yielding to let callbacks fire
        4. Asserting callback was called with the result

        Assumptions:
        - then uses add_done_callback internally
        - Callbacks fire on the event loop after set_result
        """
        req = ServerlessRequest()
        results = []
        req.then(lambda r: results.append(r))
        req.set_result({"data": "hello"})
        # Yield control so done callbacks can fire
        await asyncio.sleep(0)
        assert results == [{"data": "hello"}]

    def test_then_returns_self_for_chaining(self) -> None:
        """
        Verifies that .then() returns self for chaining.

        This test verifies by:
        1. Calling .then()
        2. Asserting return value is the same request

        Assumptions:
        - then returns self
        """
        req = ServerlessRequest()
        result = req.then(lambda r: None)
        assert result is req

    async def test_then_callback_not_called_on_exception(self) -> None:
        """
        Verifies that .then() callback is not called when future has an exception.

        This test verifies by:
        1. Registering a then callback
        2. Setting exception on the future
        3. Yielding to let callbacks fire
        4. Asserting callback was NOT called with a result

        Assumptions:
        - _done checks fut.exception() is not None and returns early
        """
        req = ServerlessRequest()
        results = []
        req.then(lambda r: results.append(r))
        req.set_exception(RuntimeError("fail"))
        await asyncio.sleep(0)
        assert results == []


# ---------------------------------------------------------------------------
# Serverless.__init__
# ---------------------------------------------------------------------------


class TestServerlessInit:
    """Verify Serverless client initialization and configuration."""

    def test_raises_when_api_key_missing(self) -> None:
        """
        Verifies that Serverless raises AttributeError when api_key is None.

        This test verifies by:
        1. Creating Serverless with api_key=None
        2. Asserting AttributeError raised

        Assumptions:
        - __init__ checks api_key is not None or empty
        """
        with pytest.raises(AttributeError, match="API key missing"):
            Serverless(api_key=None)

    def test_raises_when_api_key_empty(self) -> None:
        """
        Verifies that Serverless raises AttributeError when api_key is empty string.

        This test verifies by:
        1. Creating Serverless with api_key=""
        2. Asserting AttributeError raised

        Assumptions:
        - __init__ checks api_key == ""
        """
        with pytest.raises(AttributeError, match="API key missing"):
            Serverless(api_key="")

    def test_prod_instance_urls(self) -> None:
        """
        Verifies that instance="prod" sets correct autoscaler and web URLs.

        This test verifies by:
        1. Creating Serverless with instance="prod"
        2. Asserting URLs match production

        Assumptions:
        - prod maps to run.vast.ai and console.vast.ai
        """
        client = Serverless(api_key="test-key", instance="prod")
        assert client.autoscaler_url == "https://run.vast.ai"

    def test_alpha_instance_urls(self) -> None:
        """
        Verifies that instance="alpha" sets correct URLs.

        This test verifies by:
        1. Creating Serverless with instance="alpha"
        2. Asserting URLs match alpha environment

        Assumptions:
        - alpha maps to run-alpha.vast.ai and alpha.vast.ai
        """
        client = Serverless(api_key="test-key", instance="alpha")
        assert client.autoscaler_url == "https://run-alpha.vast.ai"

    def test_candidate_instance_urls(self) -> None:
        """
        Verifies that instance="candidate" sets correct URLs.

        This test verifies by:
        1. Creating Serverless with instance="candidate"
        2. Asserting URLs match candidate environment

        Assumptions:
        - candidate maps to run-candidate.vast.ai and candidate.vast.ai
        """
        client = Serverless(api_key="test-key", instance="candidate")
        assert client.autoscaler_url == "https://run-candidate.vast.ai"

    def test_local_instance_urls(self) -> None:
        """
        Verifies that instance="local" sets correct URLs.

        This test verifies by:
        1. Creating Serverless with instance="local"
        2. Asserting autoscaler is localhost

        Assumptions:
        - local maps to localhost:8080 for autoscaler
        """
        client = Serverless(api_key="test-key", instance="local")
        assert client.autoscaler_url == "http://localhost:8080"

    def test_unknown_instance_defaults_to_prod(self) -> None:
        """
        Verifies that unknown instance defaults to production URLs.

        This test verifies by:
        1. Creating Serverless with instance="foobar"
        2. Asserting URLs match production

        Assumptions:
        - match/case _ branch defaults to prod URLs
        """
        client = Serverless(api_key="test-key", instance="foobar")
        assert client.autoscaler_url == "https://run.vast.ai"
        assert client.vast_web_url == "https://console.vast.ai"

    def test_default_config_values(self) -> None:
        """
        Verifies that Serverless has expected default configuration.

        This test verifies by:
        1. Creating Serverless with minimal args
        2. Asserting defaults for timeout, poll_interval, connection_limit

        Assumptions:
        - Defaults: timeout=600, max_poll_interval=5, connection_limit=500
        """
        client = Serverless(api_key="test-key")
        assert client.default_request_timeout == 600.0
        assert client.max_poll_interval == 5.0
        assert client.connection_limit == 500
        assert client.debug is False

    def test_custom_config_values(self) -> None:
        """
        Verifies that Serverless accepts custom configuration.

        This test verifies by:
        1. Creating Serverless with custom values
        2. Asserting all custom values are stored

        Assumptions:
        - All config params are stored as instance attributes
        """
        client = Serverless(
            api_key="test-key",
            debug=True,
            connection_limit=100,
            default_request_timeout=300.0,
            max_poll_interval=10.0,
        )
        assert client.debug is True
        assert client.connection_limit == 100
        assert client.default_request_timeout == 300.0
        assert client.max_poll_interval == 10.0

    def test_debug_mode_configures_logging(self) -> None:
        """
        Verifies that debug=True adds a StreamHandler and sets DEBUG level.

        This test verifies by:
        1. Creating Serverless with debug=True
        2. Asserting logger has StreamHandler and DEBUG level

        Assumptions:
        - debug adds StreamHandler and sets level to DEBUG
        """
        client = Serverless(api_key="test-key", debug=True)
        assert client.logger.level == logging.DEBUG
        stream_handlers = [
            h
            for h in client.logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        ]
        assert len(stream_handlers) >= 1
        assert client.logger.propagate is False

    def test_non_debug_mode_uses_null_handler(self) -> None:
        """
        Verifies that debug=False adds NullHandler and allows propagation.

        This test verifies by:
        1. Creating Serverless with debug=False
        2. Asserting logger has NullHandler and propagate=True

        Assumptions:
        - Non-debug adds NullHandler and sets propagate=True
        """
        client = Serverless(api_key="test-key", debug=False)
        null_handlers = [
            h for h in client.logger.handlers if isinstance(h, logging.NullHandler)
        ]
        assert len(null_handlers) >= 1
        assert client.logger.propagate is True

    def test_session_starts_as_none(self) -> None:
        """
        Verifies that _session is None before any connection.

        This test verifies by:
        1. Creating Serverless
        2. Asserting _session is None

        Assumptions:
        - _session is lazily initialized
        """
        client = Serverless(api_key="test-key")
        assert client._session is None
        assert client._ssl_context is None


# ---------------------------------------------------------------------------
# Serverless.is_open / close
# ---------------------------------------------------------------------------


class TestServerlessConnection:
    """Verify Serverless connection lifecycle."""

    def test_is_open_returns_false_when_no_session(self) -> None:
        """
        Verifies that is_open returns False when _session is None.

        This test verifies by:
        1. Creating Serverless (session starts as None)
        2. Asserting is_open() is False

        Assumptions:
        - is_open checks _session is not None and not closed
        """
        client = Serverless(api_key="test-key")
        assert client.is_open() is False

    def test_is_open_returns_true_when_session_active(self) -> None:
        """
        Verifies that is_open returns True when _session exists and not closed.

        This test verifies by:
        1. Setting _session to a mock with closed=False
        2. Asserting is_open() is True

        Assumptions:
        - is_open checks session.closed
        """
        client = Serverless(api_key="test-key")
        mock_session = MagicMock()
        mock_session.closed = False
        client._session = mock_session
        assert client.is_open() is True

    def test_is_open_returns_false_when_session_closed(self) -> None:
        """
        Verifies that is_open returns False when _session.closed is True.

        This test verifies by:
        1. Setting _session with closed=True
        2. Asserting is_open() is False

        Assumptions:
        - is_open checks not _session.closed
        """
        client = Serverless(api_key="test-key")
        mock_session = MagicMock()
        mock_session.closed = True
        client._session = mock_session
        assert client.is_open() is False

    async def test_close_closes_session(self) -> None:
        """
        Verifies that close() closes the aiohttp session.

        This test verifies by:
        1. Setting _session to a mock
        2. Calling close
        3. Asserting session.close was called

        Assumptions:
        - close calls _session.close()
        """
        client = Serverless(api_key="test-key")
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.close = AsyncMock()
        client._session = mock_session
        await client.close()
        mock_session.close.assert_called_once()

    async def test_close_noop_when_no_session(self) -> None:
        """
        Verifies that close() is safe when _session is None.

        This test verifies by:
        1. Calling close with _session=None
        2. Asserting no error raised

        Assumptions:
        - close checks _session exists before closing
        """
        client = Serverless(api_key="test-key")
        await client.close()  # Should not raise


# ---------------------------------------------------------------------------
# Serverless async context manager
# ---------------------------------------------------------------------------


class TestServerlessContextManager:
    """Verify Serverless works as an async context manager."""

    async def test_aenter_returns_self(self) -> None:
        """
        Verifies that __aenter__ initializes session and returns self.

        This test verifies by:
        1. Patching _get_session
        2. Using async with
        3. Asserting yielded value is the client

        Assumptions:
        - __aenter__ calls _get_session and returns self
        """
        client = Serverless(api_key="test-key")
        client._get_session = AsyncMock()
        client.close = AsyncMock()
        async with client as c:
            assert c is client

    async def test_aexit_calls_close(self) -> None:
        """
        Verifies that __aexit__ calls close.

        This test verifies by:
        1. Patching _get_session and close
        2. Exiting context
        3. Asserting close was called

        Assumptions:
        - __aexit__ calls self.close()
        """
        client = Serverless(api_key="test-key")
        client._get_session = AsyncMock()
        client.close = AsyncMock()
        async with client:
            pass
        client.close.assert_called_once()


# ---------------------------------------------------------------------------
# Serverless.get_endpoints / get_endpoint
# ---------------------------------------------------------------------------


class TestServerlessEndpoints:
    """Verify Serverless endpoint retrieval methods."""

    async def test_get_endpoints_returns_endpoint_list(self) -> None:
        """
        Verifies that get_endpoints parses API response into Endpoint objects.

        This test verifies by:
        1. Patching _make_request to return endpoint results
        2. Calling get_endpoints
        3. Asserting Endpoint objects created with correct attributes

        Assumptions:
        - get_endpoints calls /api/v0/endptjobs/ and parses results
        """
        client = Serverless(api_key="test-key")
        with patch(
            "vastai.serverless.client.client._make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = {
                "ok": True,
                "json": {
                    "results": [
                        {
                            "endpoint_name": "a",
                            "id": 1,
                            "api_key": "ek1",
                            "cold_workers": 1,
                            "max_workers": 20,
                            "min_load": 100,
                            "target_util": 0.9,
                            "cold_mult": 1.5,
                            "max_queue_time": 30,
                            "target_queue_time": 5,
                            "endpoint_state": "running",
                            "inactivity_timeout": 600,
                            "user_id": 5,
                            "created_at": 129401,
                        },
                        {
                            "endpoint_name": "b",
                            "id": 2,
                            "api_key": "ek2",
                            "cold_workers": 1,
                            "max_workers": 20,
                            "min_load": 100,
                            "target_util": 0.9,
                            "cold_mult": 1.5,
                            "max_queue_time": 30,
                            "target_queue_time": 5,
                            "endpoint_state": "running",
                            "inactivity_timeout": 600,
                            "user_id": 5,
                            "created_at": 129401,
                        },
                    ]
                },
            }
            endpoints = await client.get_endpoints()
            assert len(endpoints) == 2
            assert isinstance(endpoints[0], Endpoint)
            assert endpoints[0].name == "a"
            assert endpoints[0].id == 1
            assert endpoints[0].api_key == "ek1"
            assert endpoints[1].name == "b"

    async def test_get_endpoints_raises_on_http_failure(self) -> None:
        """
        Verifies that get_endpoints raises when API returns not ok.

        This test verifies by:
        1. Patching _make_request to return ok=False
        2. Calling get_endpoints
        3. Asserting Exception raised

        Assumptions:
        - get_endpoints checks result["ok"]
        """
        client = Serverless(api_key="test-key")
        with patch(
            "vastai.serverless.client.client._make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = {"ok": False, "status": 401, "text": "Unauthorized"}
            with pytest.raises(Exception, match="Failed to get endpoints"):
                await client.get_endpoints()

    async def test_get_endpoints_raises_on_transport_error(self) -> None:
        """
        Verifies that get_endpoints wraps transport errors.

        This test verifies by:
        1. Patching _make_request to raise ConnectionError
        2. Asserting Exception raised

        Assumptions:
        - get_endpoints catches and re-raises with context
        """
        client = Serverless(api_key="test-key")
        with patch(
            "vastai.serverless.client.client._make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.side_effect = ConnectionError("connection refused")
            with pytest.raises(Exception, match="Failed to get endpoints"):
                await client.get_endpoints()

    async def test_get_endpoints_returns_empty_when_no_results(self) -> None:
        """
        Verifies that get_endpoints returns empty list when no endpoints exist.

        This test verifies by:
        1. Patching _make_request to return empty results
        2. Asserting empty list returned

        Assumptions:
        - Empty results array results in empty endpoint list
        """
        client = Serverless(api_key="test-key")
        with patch(
            "vastai.serverless.client.client._make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = {"ok": True, "json": {"results": []}}
            endpoints = await client.get_endpoints()
            assert endpoints == []

    async def test_get_endpoint_returns_matching_endpoint(self) -> None:
        """
        Verifies that get_endpoint returns the endpoint matching by name.

        This test verifies by:
        1. Patching get_endpoints to return multiple endpoints
        2. Calling get_endpoint("ep2")
        3. Asserting returned endpoint has name "ep2"

        Assumptions:
        - get_endpoint iterates endpoints and matches by name
        """
        client = Serverless(api_key="test-key")
        ep1 = Endpoint(client=client, name="ep1", id=1, api_key="k1")
        ep2 = Endpoint(client=client, name="ep2", id=2, api_key="k2")
        client.get_endpoints = AsyncMock(return_value=[ep1, ep2])
        result = await client.get_endpoint("ep2")
        assert result is ep2

    async def test_get_endpoint_raises_when_not_found(self) -> None:
        """
        Verifies that get_endpoint raises when no endpoint matches.

        This test verifies by:
        1. Patching get_endpoints to return endpoints that don't match
        2. Asserting Exception raised

        Assumptions:
        - get_endpoint raises if no match found
        """
        client = Serverless(api_key="test-key")
        client.get_endpoints = AsyncMock(return_value=[])
        with pytest.raises(Exception, match="could not be found"):
            await client.get_endpoint("missing")


# ---------------------------------------------------------------------------
# Serverless.get_endpoint_workers
# ---------------------------------------------------------------------------


class TestServerlessWorkers:
    """Verify Serverless.get_endpoint_workers."""

    async def test_get_endpoint_workers_returns_worker_list(self) -> None:
        """
        Verifies that get_endpoint_workers parses response into Worker objects.

        This test verifies by:
        1. Creating client with mock session
        2. Mocking POST to return worker data list
        3. Asserting Worker objects returned

        Assumptions:
        - Response is list of dicts parsed by Worker.from_dict
        """
        client = Serverless(api_key="test-key")
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value=[
                {"id": 1, "status": "RUNNING", "cur_load": 0.5},
                {"id": 2, "status": "IDLE", "cur_load": 0.0},
            ]
        )
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        client._session = mock_session

        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        workers = await client.get_endpoint_workers(ep)
        assert len(workers) == 2
        assert isinstance(workers[0], Worker)
        assert workers[0].id == 1
        assert workers[1].status == "IDLE"

    async def test_get_endpoint_workers_raises_on_non_endpoint(self) -> None:
        """
        Verifies that get_endpoint_workers raises ValueError for non-Endpoint arg.

        This test verifies by:
        1. Calling with a non-Endpoint object
        2. Asserting ValueError raised

        Assumptions:
        - isinstance check at top of method
        """
        client = Serverless(api_key="test-key")
        with pytest.raises(ValueError, match="must be an Endpoint"):
            await client.get_endpoint_workers("not-an-endpoint")

    async def test_get_endpoint_workers_returns_empty_on_error_msg(self) -> None:
        """
        Verifies that get_endpoint_workers returns empty list on error_msg response.

        This test verifies by:
        1. Mocking response as dict with error_msg
        2. Asserting empty list returned

        Assumptions:
        - Dict response with error_msg triggers warning and empty return
        """
        client = Serverless(api_key="test-key")
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"error_msg": "not ready"})
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        client._session = mock_session

        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        workers = await client.get_endpoint_workers(ep)
        assert workers == []

    async def test_get_endpoint_workers_raises_on_http_error(self) -> None:
        """
        Verifies that get_endpoint_workers raises RuntimeError on non-200 status.

        This test verifies by:
        1. Mocking response with status 500
        2. Asserting RuntimeError raised

        Assumptions:
        - Non-200 status triggers RuntimeError
        """
        client = Serverless(api_key="test-key")
        mock_resp = AsyncMock()
        mock_resp.status = 500
        mock_resp.text = AsyncMock(return_value="Internal Server Error")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        client._session = mock_session

        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        with pytest.raises(RuntimeError, match="get_endpoint_workers failed"):
            await client.get_endpoint_workers(ep)

    async def test_get_endpoint_workers_raises_on_unexpected_type(self) -> None:
        """
        Verifies that get_endpoint_workers raises on non-list response.

        This test verifies by:
        1. Mocking response as a string
        2. Asserting RuntimeError raised

        Assumptions:
        - Non-list, non-error-dict response triggers RuntimeError
        """
        client = Serverless(api_key="test-key")
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value="unexpected string")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        client._session = mock_session

        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        with pytest.raises(RuntimeError, match="Unexpected response type"):
            await client.get_endpoint_workers(ep)


# ---------------------------------------------------------------------------
# Serverless session management
# ---------------------------------------------------------------------------


class TestServerlessSessionManagement:
    """Verify Serverless session CRUD methods."""

    async def test_get_endpoint_session_returns_session(self) -> None:
        """
        Verifies that get_endpoint_session creates Session from worker response.

        This test verifies by:
        1. Patching _make_request to return session data with auth_data
        2. Calling get_endpoint_session
        3. Asserting Session created with correct fields

        Assumptions:
        - Response contains auth_data, lifetime, expiration
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        with patch(
            "vastai.serverless.client.client._make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = {
                "ok": True,
                "json": {
                    "auth_data": {"url": "https://w.vast.ai", "signature": "sig"},
                    "lifetime": 120.0,
                    "expiration": "2026-12-31T00:00:00Z",
                },
            }
            session = await client.get_endpoint_session(
                endpoint=ep,
                session_id=42,
                session_auth={"url": "https://w.vast.ai"},
            )
            assert isinstance(session, Session)
            assert session.session_id == 42
            assert session.lifetime == 120.0
            assert session.url == "https://w.vast.ai"

    async def test_get_endpoint_session_raises_on_not_ok(self) -> None:
        """
        Verifies that get_endpoint_session raises when response is not ok.

        This test verifies by:
        1. Patching _make_request to return ok=False
        2. Asserting Exception raised

        Assumptions:
        - Not-ok response triggers exception
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        with patch(
            "vastai.serverless.client.client._make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = {
                "ok": False,
                "json": {"error": "not found"},
                "text": "",
            }
            with pytest.raises(Exception, match="Failed to get session"):
                await client.get_endpoint_session(
                    endpoint=ep,
                    session_id=42,
                    session_auth={"url": "https://w.vast.ai"},
                )

    async def test_get_endpoint_session_raises_on_missing_auth_data(self) -> None:
        """
        Verifies that get_endpoint_session raises when auth_data is missing.

        This test verifies by:
        1. Patching _make_request to return ok=True but no auth_data
        2. Asserting Exception raised

        Assumptions:
        - Missing auth_data triggers "Missing auth_data" exception
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        with patch(
            "vastai.serverless.client.client._make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = {
                "ok": True,
                "json": {"lifetime": 60.0},
            }
            with pytest.raises(Exception, match="Missing auth_data"):
                await client.get_endpoint_session(
                    endpoint=ep,
                    session_id=42,
                    session_auth={"url": "https://w.vast.ai"},
                )

    async def test_get_endpoint_session_reraises_timeout(self) -> None:
        """
        Verifies that get_endpoint_session re-raises asyncio.TimeoutError.

        This test verifies by:
        1. Patching _make_request to raise TimeoutError
        2. Asserting asyncio.TimeoutError propagates

        Assumptions:
        - TimeoutError is caught and re-raised directly
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        with patch(
            "vastai.serverless.client.client._make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.side_effect = asyncio.TimeoutError()
            with pytest.raises(asyncio.TimeoutError):
                await client.get_endpoint_session(
                    endpoint=ep,
                    session_id=42,
                    session_auth={"url": "https://w.vast.ai"},
                )

    async def test_end_endpoint_session_success(self) -> None:
        """
        Verifies that end_endpoint_session calls /session/end and returns.

        This test verifies by:
        1. Patching _make_request to return ok=True
        2. Calling end_endpoint_session
        3. Asserting no exception raised

        Assumptions:
        - end_endpoint_session POSTs to /session/end
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        session = Session(
            endpoint=ep,
            session_id="s1",
            lifetime=60,
            expiration="x",
            url="https://w.vast.ai",
            auth_data={"url": "https://w.vast.ai"},
        )
        with patch(
            "vastai.serverless.client.client._make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = {"ok": True, "json": {}}
            await client.end_endpoint_session(session=session)
            mock_req.assert_called_once()
            call_kwargs = mock_req.call_args[1]
            assert call_kwargs["route"] == "/session/end"
            assert call_kwargs["body"]["session_id"] == "s1"

    async def test_end_endpoint_session_raises_on_failure(self) -> None:
        """
        Verifies that end_endpoint_session raises on not-ok response.

        This test verifies by:
        1. Patching _make_request to return ok=False
        2. Asserting Exception raised

        Assumptions:
        - Not-ok triggers error path
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        session = Session(
            endpoint=ep,
            session_id="s1",
            lifetime=60,
            expiration="x",
            url="https://w.vast.ai",
            auth_data={"url": "https://w.vast.ai"},
        )
        with patch(
            "vastai.serverless.client.client._make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = {"ok": False, "json": {"error": "fail"}, "text": ""}
            with pytest.raises(Exception, match="Failed to end session"):
                await client.end_endpoint_session(session=session)


# ---------------------------------------------------------------------------
# Serverless.start_endpoint_session
# ---------------------------------------------------------------------------


class TestServerlessStartEndpointSession:
    """Verify Serverless.start_endpoint_session creates Session from queue response."""

    async def test_start_session_success_returns_session(self) -> None:
        """
        Verifies that start_endpoint_session returns a Session on success.

        This test verifies by:
        1. Mocking queue_endpoint_request to return a full success response
        2. Calling start_endpoint_session
        3. Asserting Session is created with correct fields

        Assumptions:
        - Response contains ok, response.session_id, response.expiration, url, auth_data
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        client.queue_endpoint_request = AsyncMock(
            return_value={
                "ok": True,
                "response": {"session_id": "sess-42", "expiration": "2026-12-31"},
                "url": "https://w.vast.ai",
                "auth_data": {"url": "https://w.vast.ai", "sig": "abc"},
                "status": 200,
            }
        )
        session = await client.start_endpoint_session(
            endpoint=ep, cost=100, lifetime=120
        )
        assert isinstance(session, Session)
        assert session.session_id == "sess-42"
        assert session.lifetime == 120
        assert session.url == "https://w.vast.ai"

    async def test_start_session_raises_on_not_ok(self) -> None:
        """
        Verifies that start_endpoint_session raises when response is not ok.

        This test verifies by:
        1. Mocking queue_endpoint_request to return ok=False
        2. Asserting Exception raised with error message

        Assumptions:
        - Not-ok triggers "Error on /session/create" then wraps in "Failed to create session"
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        client.queue_endpoint_request = AsyncMock(
            return_value={
                "ok": False,
                "json": {"error": "quota exceeded"},
                "text": "quota exceeded",
                "status": 429,
            }
        )
        with pytest.raises(Exception, match="Failed to create session"):
            await client.start_endpoint_session(endpoint=ep)

    async def test_start_session_raises_on_none_response(self) -> None:
        """
        Verifies that start_endpoint_session raises when response is None.

        This test verifies by:
        1. Mocking queue_endpoint_request with response=None
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        client.queue_endpoint_request = AsyncMock(
            return_value={
                "ok": True,
                "response": None,
                "status": 200,
            }
        )
        with pytest.raises(Exception, match="No response from /session/create"):
            await client.start_endpoint_session(endpoint=ep)

    async def test_start_session_raises_on_missing_session_id(self) -> None:
        """
        Verifies that start_endpoint_session raises when session_id is missing.

        This test verifies by:
        1. Mocking response without session_id
        2. Asserting Exception raised

        Assumptions:
        - Missing session_id triggers "Missing session id"
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        client.queue_endpoint_request = AsyncMock(
            return_value={
                "ok": True,
                "response": {"expiration": "2026-12-31"},
                "url": "https://w.vast.ai",
                "auth_data": {"url": "https://w.vast.ai"},
                "status": 200,
            }
        )
        with pytest.raises(Exception, match="Missing session id"):
            await client.start_endpoint_session(endpoint=ep)

    async def test_start_session_raises_on_missing_url(self) -> None:
        """
        Verifies that start_endpoint_session raises when url is missing.

        This test verifies by:
        1. Mocking response without url
        2. Asserting Exception raised

        Assumptions:
        - Missing url triggers "Missing URL"
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        client.queue_endpoint_request = AsyncMock(
            return_value={
                "ok": True,
                "response": {"session_id": "s1", "expiration": "x"},
                "url": None,
                "auth_data": {"url": "https://w.vast.ai"},
                "status": 200,
            }
        )
        with pytest.raises(Exception, match="Missing URL"):
            await client.start_endpoint_session(endpoint=ep)

    async def test_start_session_raises_on_missing_auth_data(self) -> None:
        """
        Verifies that start_endpoint_session raises when auth_data is missing.

        This test verifies by:
        1. Mocking response without auth_data
        2. Asserting Exception raised

        Assumptions:
        - Missing auth_data triggers "Missing auth data"
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        client.queue_endpoint_request = AsyncMock(
            return_value={
                "ok": True,
                "response": {"session_id": "s1", "expiration": "x"},
                "url": "https://w.vast.ai",
                "auth_data": None,
                "status": 200,
            }
        )
        with pytest.raises(Exception, match="Missing auth data"):
            await client.start_endpoint_session(endpoint=ep)

    async def test_start_session_reraises_timeout(self) -> None:
        """
        Verifies that start_endpoint_session re-raises asyncio.TimeoutError.

        This test verifies by:
        1. Mocking queue_endpoint_request to raise TimeoutError
        2. Asserting asyncio.TimeoutError propagates directly

        Assumptions:
        - TimeoutError is caught and re-raised without wrapping
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        client.queue_endpoint_request = AsyncMock(side_effect=asyncio.TimeoutError())
        with pytest.raises(asyncio.TimeoutError):
            await client.start_endpoint_session(endpoint=ep)

    async def test_start_session_passes_correct_payload(self) -> None:
        """
        Verifies that start_endpoint_session sends correct worker_payload.

        This test verifies by:
        1. Calling with lifetime, on_close_route, on_close_payload
        2. Asserting queue_endpoint_request called with correct payload

        Assumptions:
        - Payload includes lifetime, on_close_route, on_close_payload
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        client.queue_endpoint_request = AsyncMock(
            return_value={
                "ok": True,
                "response": {"session_id": "s1", "expiration": "x"},
                "url": "https://w.vast.ai",
                "auth_data": {"url": "https://w.vast.ai"},
                "status": 200,
            }
        )
        await client.start_endpoint_session(
            endpoint=ep,
            cost=50,
            lifetime=300,
            on_close_route="/cleanup",
            on_close_payload={"key": "val"},
            timeout=30.0,
        )
        call_kwargs = client.queue_endpoint_request.call_args.kwargs
        assert call_kwargs["worker_route"] == "/session/create"
        assert call_kwargs["worker_payload"] == {
            "lifetime": 300,
            "on_close_route": "/cleanup",
            "on_close_payload": {"key": "val"},
        }
        assert call_kwargs["cost"] == 50
        assert call_kwargs["timeout"] == 30.0
        assert call_kwargs["worker_timeout"] == 10.0


# ---------------------------------------------------------------------------
# Serverless.queue_endpoint_request
# ---------------------------------------------------------------------------


class TestServerlessQueueEndpointRequest:
    """Verify Serverless.queue_endpoint_request returns a managed Future."""

    async def test_returns_serverless_request(self) -> None:
        """
        Verifies that queue_endpoint_request returns a ServerlessRequest.

        This test verifies by:
        1. Creating client and endpoint with mocked internals
        2. Calling queue_endpoint_request inside a running event loop
        3. Asserting result is ServerlessRequest

        Assumptions:
        - queue_endpoint_request wraps async work in ServerlessRequest future
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        client._get_session = AsyncMock()
        client.get_ssl_context = AsyncMock(return_value=None)

        with patch.object(ep, "_route", new_callable=AsyncMock) as mock_route:
            mock_route.return_value = MagicMock(
                status="READY",
                request_idx=1,
                get_url=MagicMock(return_value="https://w.vast.ai"),
                body={"url": "https://w.vast.ai"},
            )
            with patch(
                "vastai.serverless.client.client._make_request", new_callable=AsyncMock
            ) as mock_req:
                mock_req.return_value = {
                    "ok": True,
                    "json": {"result": "done"},
                    "status": 200,
                    "text": "",
                }
                req = client.queue_endpoint_request(
                    endpoint=ep,
                    worker_route="/predict",
                    worker_payload={"input": "test"},
                )
                assert isinstance(req, ServerlessRequest)
                # Await the background task to avoid orphaned task warnings
                result = await req
                assert result["ok"] is True

    async def test_accepts_custom_serverless_request(self) -> None:
        """
        Verifies that queue_endpoint_request uses provided ServerlessRequest.

        This test verifies by:
        1. Creating a custom ServerlessRequest
        2. Passing it to queue_endpoint_request
        3. Asserting the same object is returned

        Assumptions:
        - If serverless_request is provided, it's used instead of creating new one
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        custom_req = ServerlessRequest()
        client._get_session = AsyncMock()
        client.get_ssl_context = AsyncMock(return_value=None)

        with patch.object(ep, "_route", new_callable=AsyncMock) as mock_route:
            mock_route.return_value = MagicMock(
                status="READY",
                request_idx=1,
                get_url=MagicMock(return_value="https://w.vast.ai"),
                body={"url": "https://w.vast.ai"},
            )
            with patch(
                "vastai.serverless.client.client._make_request", new_callable=AsyncMock
            ) as mock_req:
                mock_req.return_value = {
                    "ok": True,
                    "json": {"result": "done"},
                    "status": 200,
                    "text": "",
                }
                req = client.queue_endpoint_request(
                    endpoint=ep,
                    worker_route="/predict",
                    worker_payload={},
                    serverless_request=custom_req,
                )
                assert req is custom_req
                await req


# ---------------------------------------------------------------------------
# Serverless.queue_endpoint_request — async task behavior
# ---------------------------------------------------------------------------


class TestQueueEndpointRequestTaskBehavior:
    """Verify the async task logic inside queue_endpoint_request."""

    async def test_session_based_routing_skips_route_call(self) -> None:
        """
        Verifies that providing a session bypasses _route and uses session.url directly.

        This test verifies by:
        1. Creating a session with url and auth_data
        2. Calling queue_endpoint_request with session param
        3. Asserting _route was NOT called
        4. Asserting _make_request was called with session.url

        Assumptions:
        - When session is provided, worker_url = session.url, auth_data = session.auth_data
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        session = Session(
            endpoint=ep,
            session_id="s1",
            lifetime=60,
            expiration="x",
            url="https://session-worker.vast.ai",
            auth_data={"sig": "abc"},
        )
        client._get_session = AsyncMock()
        client.get_ssl_context = AsyncMock(return_value=None)

        with patch.object(ep, "_route", new_callable=AsyncMock) as mock_route:
            with patch(
                "vastai.serverless.client.client._make_request", new_callable=AsyncMock
            ) as mock_req:
                mock_req.return_value = {
                    "ok": True,
                    "json": {"result": "done"},
                    "status": 200,
                    "text": "",
                }
                req = client.queue_endpoint_request(
                    endpoint=ep,
                    worker_route="/predict",
                    worker_payload={"input": "test"},
                    session=session,
                )
                result = await req
                mock_route.assert_not_called()
                assert result["ok"] is True
                # Verify _make_request was called with the session's URL
                call_kwargs = mock_req.call_args.kwargs
                assert call_kwargs["url"] == "https://session-worker.vast.ai"
                assert call_kwargs["body"]["session_id"] == "s1"
                assert call_kwargs["body"]["auth_data"] == {"sig": "abc"}

    async def test_polling_loop_when_route_returns_waiting(self) -> None:
        """
        Verifies that queue_endpoint_request polls when route status is WAITING.

        This test verifies by:
        1. Mocking _route to return WAITING first, then READY
        2. Asserting _route was called multiple times
        3. Asserting final result is successful

        Assumptions:
        - While route.status != READY, the task polls with asyncio.sleep
        - max_poll_interval=0.001 keeps real sleeps negligible
        """
        client = Serverless(api_key="test-key", max_poll_interval=0.001)
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        client._get_session = AsyncMock()
        client.get_ssl_context = AsyncMock(return_value=None)

        waiting_response = MagicMock(
            status="WAITING",
            request_idx=5,
            get_url=MagicMock(return_value=None),
            body={},
        )
        ready_response = MagicMock(
            status="READY",
            request_idx=5,
            get_url=MagicMock(return_value="https://w.vast.ai"),
            body={"url": "https://w.vast.ai"},
        )

        with patch.object(ep, "_route", new_callable=AsyncMock) as mock_route:
            mock_route.side_effect = [
                waiting_response,
                waiting_response,
                ready_response,
            ]
            with patch(
                "vastai.serverless.client.client._make_request", new_callable=AsyncMock
            ) as mock_req:
                mock_req.return_value = {
                    "ok": True,
                    "json": {"result": "ok"},
                    "status": 200,
                    "text": "",
                }
                req = client.queue_endpoint_request(
                    endpoint=ep,
                    worker_route="/predict",
                    worker_payload={},
                )
                result = await req
                assert result["ok"] is True
                # Initial route + 2 polls (WAITING, WAITING) + READY not polled again
                assert mock_route.call_count == 3

    async def test_retry_on_retryable_http_error(self) -> None:
        """
        Verifies that queue_endpoint_request retries on retryable HTTP errors.

        This test verifies by:
        1. Mocking _make_request to return retryable=True first, then ok=True
        2. Asserting the request succeeds after retry

        Assumptions:
        - Retryable non-ok responses trigger retry with backoff
        - max_poll_interval=0.001 keeps retry sleep negligible
        """
        client = Serverless(api_key="test-key", max_poll_interval=0.001)
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        client._get_session = AsyncMock()
        client.get_ssl_context = AsyncMock(return_value=None)

        with patch.object(ep, "_route", new_callable=AsyncMock) as mock_route:
            mock_route.return_value = MagicMock(
                status="READY",
                request_idx=1,
                get_url=MagicMock(return_value="https://w.vast.ai"),
                body={"url": "https://w.vast.ai"},
            )
            with patch(
                "vastai.serverless.client.client._make_request", new_callable=AsyncMock
            ) as mock_req:
                mock_req.side_effect = [
                    {
                        "ok": False,
                        "retryable": True,
                        "status": 503,
                        "text": "Service Unavailable",
                        "json": None,
                    },
                    {"ok": True, "json": {"result": "ok"}, "status": 200, "text": ""},
                ]
                req = client.queue_endpoint_request(
                    endpoint=ep,
                    worker_route="/predict",
                    worker_payload={},
                    retry=True,
                )
                result = await req
                assert result["ok"] is True
                assert mock_req.call_count == 2

    async def test_non_retryable_error_returns_result(self) -> None:
        """
        Verifies that non-retryable HTTP errors return the result without retrying.

        This test verifies by:
        1. Mocking _make_request to return retryable=False, ok=False
        2. Asserting result returned directly with ok=False

        Assumptions:
        - Non-retryable errors are returned to the caller immediately
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        client._get_session = AsyncMock()
        client.get_ssl_context = AsyncMock(return_value=None)

        with patch.object(ep, "_route", new_callable=AsyncMock) as mock_route:
            mock_route.return_value = MagicMock(
                status="READY",
                request_idx=1,
                get_url=MagicMock(return_value="https://w.vast.ai"),
                body={"url": "https://w.vast.ai"},
            )
            with patch(
                "vastai.serverless.client.client._make_request", new_callable=AsyncMock
            ) as mock_req:
                mock_req.return_value = {
                    "ok": False,
                    "retryable": False,
                    "status": 400,
                    "text": "Bad Request",
                    "json": {"error": "invalid"},
                }
                req = client.queue_endpoint_request(
                    endpoint=ep,
                    worker_route="/predict",
                    worker_payload={},
                )
                result = await req
                assert result["ok"] is False
                assert result["status"] == 400
                mock_req.assert_called_once()

    async def test_stream_mode_returns_stream(self) -> None:
        """
        Verifies that stream=True uses result.get("stream") instead of result.get("json").

        This test verifies by:
        1. Mocking _make_request with stream result
        2. Calling with stream=True
        3. Asserting response contains the stream object

        Assumptions:
        - Stream mode extracts result["stream"] as response
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        client._get_session = AsyncMock()
        client.get_ssl_context = AsyncMock(return_value=None)
        mock_stream = MagicMock()

        with patch.object(ep, "_route", new_callable=AsyncMock) as mock_route:
            mock_route.return_value = MagicMock(
                status="READY",
                request_idx=1,
                get_url=MagicMock(return_value="https://w.vast.ai"),
                body={"url": "https://w.vast.ai"},
            )
            with patch(
                "vastai.serverless.client.client._make_request", new_callable=AsyncMock
            ) as mock_req:
                mock_req.return_value = {
                    "ok": True,
                    "stream": mock_stream,
                    "json": None,
                    "status": 200,
                    "text": "",
                }
                req = client.queue_endpoint_request(
                    endpoint=ep,
                    worker_route="/predict",
                    worker_payload={},
                    stream=True,
                )
                result = await req
                assert result["response"] is mock_stream


# ---------------------------------------------------------------------------
# queue_endpoint_request – resilience edge cases
# ---------------------------------------------------------------------------


class TestQueueEndpointRequestResilience:
    """Cover transport failure, generic exception retry, and cancellation paths
    in queue_endpoint_request that the main tests do not exercise."""

    async def test_session_worker_connection_error_raises(self) -> None:
        """
        Verifies that a ClientConnectorError with an active session raises
        ConnectionError and marks session.open = False.

        This test verifies by:
        1. Creating a Serverless client and Endpoint
        2. Creating a Session bound to that endpoint
        3. Mocking _make_request to raise ClientConnectorError
        4. Asserting ConnectionError is raised and session.open is False

        Assumptions:
        - Session-bound requests cannot re-route to a different worker
        - The session is marked closed on transport failure
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        client._get_session = AsyncMock()
        client.get_ssl_context = AsyncMock(return_value=None)

        session = Session(
            endpoint=ep,
            session_id="sess-1",
            lifetime=60.0,
            expiration="2026-12-31T00:00:00Z",
            url="https://worker1.vast.ai",
            auth_data={"url": "https://worker1.vast.ai", "signature": "abc"},
        )
        assert session.open is True

        with patch(
            "vastai.serverless.client.client._make_request", new_callable=AsyncMock
        ) as mock_req:
            conn_os_error = OSError("connection refused")
            mock_req.side_effect = aiohttp.ClientConnectorError(
                connection_key=MagicMock(),
                os_error=conn_os_error,
            )
            req = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/predict",
                worker_payload={},
                session=session,
            )
            with pytest.raises(ConnectionError, match="Session worker unavailable"):
                await req

        assert session.open is False

    async def test_session_worker_server_disconnected_raises(self) -> None:
        """
        Verifies that ServerDisconnectedError with an active session raises
        ConnectionError.

        This test verifies by:
        1. Mocking _make_request to raise ServerDisconnectedError
        2. Asserting ConnectionError is raised

        Assumptions:
        - ServerDisconnectedError is handled identically to ClientConnectorError
          when a session is present
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        client._get_session = AsyncMock()
        client.get_ssl_context = AsyncMock(return_value=None)

        session = Session(
            endpoint=ep,
            session_id="sess-2",
            lifetime=60.0,
            expiration="2026-12-31T00:00:00Z",
            url="https://worker2.vast.ai",
            auth_data={"url": "https://worker2.vast.ai", "signature": "xyz"},
        )

        with patch(
            "vastai.serverless.client.client._make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.side_effect = aiohttp.ServerDisconnectedError()
            req = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/predict",
                worker_payload={},
                session=session,
            )
            with pytest.raises(ConnectionError, match="Session worker unavailable"):
                await req

        assert session.open is False

    async def test_no_session_connection_error_reroutes(self) -> None:
        """
        Verifies that a ClientConnectorError WITHOUT a session triggers a
        re-route instead of raising.

        This test verifies by:
        1. Mocking _make_request to raise ClientConnectorError once, then succeed
        2. Mocking _route to return READY both times
        3. Asserting the request succeeds and _route was called twice (initial + re-route)

        Assumptions:
        - Without a session, transport errors trigger re-routing to a new worker
        - request_idx resets so a fresh route is obtained
        """
        client = Serverless(api_key="test-key", max_poll_interval=0.001)
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        client._get_session = AsyncMock()
        client.get_ssl_context = AsyncMock(return_value=None)

        with patch.object(ep, "_route", new_callable=AsyncMock) as mock_route:
            mock_route.return_value = MagicMock(
                status="READY",
                request_idx=1,
                get_url=MagicMock(return_value="https://w.vast.ai"),
                body={"url": "https://w.vast.ai"},
            )
            conn_os_error = OSError("connection refused")
            with patch(
                "vastai.serverless.client.client._make_request", new_callable=AsyncMock
            ) as mock_req:
                mock_req.side_effect = [
                    aiohttp.ClientConnectorError(
                        connection_key=MagicMock(),
                        os_error=conn_os_error,
                    ),
                    {
                        "ok": True,
                        "json": {"result": "rerouted"},
                        "status": 200,
                        "text": "",
                    },
                ]
                req = client.queue_endpoint_request(
                    endpoint=ep,
                    worker_route="/predict",
                    worker_payload={},
                )
                result = await req
                assert result["ok"] is True
                assert result["response"]["result"] == "rerouted"
                # _route called twice: initial route + re-route after failure
                assert mock_route.call_count == 2

    async def test_generic_exception_retries(self) -> None:
        """
        Verifies that a non-transport exception (e.g. RuntimeError) in
        _make_request triggers a retry rather than failing immediately.

        This test verifies by:
        1. Mocking _make_request to raise RuntimeError once, then succeed
        2. Asserting the request eventually succeeds
        3. Asserting _make_request was called twice

        Assumptions:
        - The bare `except Exception` clause in queue_endpoint_request sets
          status to "Retrying" and continues the loop
        """
        client = Serverless(api_key="test-key", max_poll_interval=0.001)
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        client._get_session = AsyncMock()
        client.get_ssl_context = AsyncMock(return_value=None)

        with patch.object(ep, "_route", new_callable=AsyncMock) as mock_route:
            mock_route.return_value = MagicMock(
                status="READY",
                request_idx=1,
                get_url=MagicMock(return_value="https://w.vast.ai"),
                body={"url": "https://w.vast.ai"},
            )
            with patch(
                "vastai.serverless.client.client._make_request", new_callable=AsyncMock
            ) as mock_req:
                mock_req.side_effect = [
                    RuntimeError("unexpected worker error"),
                    {
                        "ok": True,
                        "json": {"result": "recovered"},
                        "status": 200,
                        "text": "",
                    },
                ]
                req = client.queue_endpoint_request(
                    endpoint=ep,
                    worker_route="/predict",
                    worker_payload={},
                )
                result = await req
                assert result["ok"] is True
                assert result["response"]["result"] == "recovered"
                assert mock_req.call_count == 2

    async def test_cancelled_error_sets_status(self) -> None:
        """
        Verifies that cancelling the background task sets request status
        to "Cancelled".

        This test verifies by:
        1. Mocking _route to set an asyncio.Event when entered, then block
        2. Waiting on that event so ordering is deterministic (no fixed sleeps)
        3. Cancelling the ServerlessRequest and yielding until status is "Cancelled"

        Assumptions:
        - CancelledError is caught by the outer try/except
        - _propagate_cancel forwards the cancellation to the bg_task
        """
        client = Serverless(api_key="test-key")
        ep = Endpoint(client=client, name="ep", id=1, api_key="k")
        client._get_session = AsyncMock()
        client.get_ssl_context = AsyncMock(return_value=None)

        route_entered = asyncio.Event()

        async def _route_after_signal(**kwargs):
            route_entered.set()
            await asyncio.sleep(999)

        with patch.object(ep, "_route", side_effect=_route_after_signal):
            req = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/predict",
                worker_payload={},
            )
            await asyncio.wait_for(route_entered.wait(), timeout=5.0)
            req.cancel()
            for _ in range(200):
                if req.status == "Cancelled":
                    break
                await asyncio.sleep(0)
            else:
                pytest.fail("request status did not become Cancelled in time")
            assert req.status == "Cancelled"


# ---------------------------------------------------------------------------
# get_ssl_context – hermetic SSL certificate loading
# ---------------------------------------------------------------------------


class TestGetSslContext:
    """Cover the get_ssl_context method that downloads and caches the Vast root cert."""

    async def test_downloads_and_caches_ssl_cert(self) -> None:
        """
        Verifies that get_ssl_context fetches the cert, creates an SSLContext,
        and caches it for subsequent calls.

        This test verifies by:
        1. Mocking the aiohttp.ClientSession used inside get_ssl_context
        2. Providing opaque bytes as the HTTP body (real parsing is mocked via
           ``ssl.create_default_context`` returning a MagicMock)
        3. Calling get_ssl_context twice
        4. Asserting the HTTP fetch only happens once (cached)

        Assumptions:
        - get_ssl_context uses a fresh aiohttp.ClientSession internally
        - Production writes PEM to a temp file and loads it; here ``load_verify_locations``
          is never invoked on a real context because ``create_default_context`` is patched
        """
        import ssl as _ssl

        fake_cert_bytes = b"fake-cert-data"

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=fake_cert_bytes)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_ctx = MagicMock(spec=_ssl.SSLContext)

        client = Serverless(api_key="test-key")
        assert client._ssl_context is None

        with patch(
            "vastai.serverless.client.client.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            with patch(
                "vastai.serverless.client.client.ssl.create_default_context",
                return_value=mock_ctx,
            ):
                ctx1 = await client.get_ssl_context()
                ctx2 = await client.get_ssl_context()

        # Should return the same cached context both times
        assert ctx1 is ctx2
        assert ctx1 is mock_ctx
        # The HTTP fetch should only happen once
        mock_session.get.assert_called_once_with(Serverless.SSL_CERT_URL)
        # The cert should have been loaded
        mock_ctx.load_verify_locations.assert_called_once()

    async def test_ssl_cert_fetch_failure_raises(self) -> None:
        """
        Verifies that a non-200 response from the cert URL raises an Exception.

        This test verifies by:
        1. Mocking the HTTP response with status 500
        2. Asserting Exception is raised with appropriate message

        Assumptions:
        - get_ssl_context raises when cert download fails
        - _ssl_context remains None after failure
        """
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        client = Serverless(api_key="test-key")

        with patch(
            "vastai.serverless.client.client.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            with pytest.raises(Exception, match="Failed to fetch SSL cert: 500"):
                await client.get_ssl_context()

        assert client._ssl_context is None
