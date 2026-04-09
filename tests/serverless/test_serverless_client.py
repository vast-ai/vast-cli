"""Unit tests for vastai.serverless.client.client (Serverless, ServerlessRequest).

HTTP and routing are mocked via _make_request, queue_endpoint_request, or aiohttp session mocks.

This module is the primary home for queue/session API coverage added for serverless client work.
Broader tests (SSL, subprocess env, ``get_ssl_context``, extra debug branches) live in
``test_client.py``; add new narrow queue/session behavior here first to avoid drift.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from vastai.serverless.client.client import Serverless, ServerlessRequest
from vastai.serverless.client.endpoint import Endpoint


class TestServerlessRequest:
    """ServerlessRequest future wrapper behavior."""

    @pytest.mark.asyncio
    async def test_then_invokes_callback_on_success(self) -> None:
        """
        Verifies ServerlessRequest.then registers a done callback that receives the result.

        This test verifies by:
        1. Creating a ServerlessRequest and chaining .then with a MagicMock callback
        2. Calling set_result with a payload
        3. Yielding to the loop so the callback runs, then asserting call args

        Assumptions:
        - asyncio schedules done callbacks on the next loop iteration
        """
        cb = MagicMock()
        req = ServerlessRequest()
        req.then(cb)
        req.set_result({"ok": True})
        await asyncio.sleep(0)
        cb.assert_called_once_with({"ok": True})


class TestServerlessInitAndConfig:
    """Constructor, API key, and instance URL selection."""

    def test_init_raises_when_api_key_missing(self) -> None:
        """
        Verifies Serverless rejects a missing or empty api_key.

        This test verifies by:
        1. Instantiating Serverless(api_key=None) and Serverless(api_key="")
        2. Asserting AttributeError mentioning API key each time

        Assumptions:
        - __init__ treats None and empty string as missing
        """
        with pytest.raises(AttributeError, match="API key missing"):
            Serverless(api_key=None)
        with pytest.raises(AttributeError, match="API key missing"):
            Serverless(api_key="")

    def test_init_accepts_explicit_api_key(self, client) -> None:
        """
        Verifies explicit api_key is stored on the client.

        This test verifies by:
        1. Constructing Serverless(api_key=...) via client fixture
        2. Asserting client.api_key matches

        Assumptions:
        - No environment key is required when api_key is passed
        """
        assert client.api_key == "k"

    @pytest.mark.parametrize(
        ("instance", "autoscaler_substr"),
        [
            ("prod", "run.vast.ai"),
            ("alpha", "run-alpha.vast.ai"),
            ("candidate", "run-candidate.vast.ai"),
            ("local", "localhost:8080"),
        ],
    )
    def test_instance_selects_autoscaler_url(
        self, instance: str, autoscaler_substr: str
    ) -> None:
        """
        Verifies instance keyword maps to expected autoscaler base URL.

        This test verifies by:
        1. Creating Serverless with instance=...
        2. Asserting autoscaler_url contains the expected host fragment

        Assumptions:
        - Mapping matches current client.py match/case branches
        """
        sl = Serverless(api_key="k", instance=instance)
        assert autoscaler_substr in sl.autoscaler_url


@pytest.mark.asyncio
class TestServerlessEndpoints:
    """get_endpoints and get_endpoint."""

    async def test_get_endpoints_parses_results_into_endpoints(self, client) -> None:
        """
        Verifies get_endpoints builds Endpoint objects from JSON results.

        This test verifies by:
        1. Patching _make_request to return ok JSON with one result row
        2. Calling await client.get_endpoints()
        3. Asserting one Endpoint with matching name, id, api_key

        Assumptions:
        - _make_request is patched at the module where client.py uses it
        """
        fake = {
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
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            return_value=fake,
        ):
            endpoints = await client.get_endpoints()
        assert len(endpoints) == 2
        assert endpoints[0].name == "a"
        assert endpoints[0].id == 1
        assert endpoints[0].api_key == "ek1"
        assert endpoints[0].client is client

    async def test_get_endpoints_raises_when_http_not_ok(self, client) -> None:
        """
        Verifies get_endpoints wraps failed HTTP into Exception.

        This test verifies by:
        1. Returning ok=False from _make_request
        2. Asserting Exception is raised with status context

        Assumptions:
        - Client surfaces HTTP failures as generic Exception
        """
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            return_value={"ok": False, "status": 500, "text": "err"},
        ):
            with pytest.raises(Exception, match="Failed to get endpoints"):
                await client.get_endpoints()

    async def test_get_endpoint_returns_matching_endpoint(self, client) -> None:
        """
        Verifies get_endpoint selects by name from get_endpoints.

        This test verifies by:
        1. Patching get_endpoints to return two Endpoint mocks
        2. Calling get_endpoint('two')
        3. Asserting the correct endpoint is returned

        Assumptions:
        - get_endpoint only compares e.name
        """
        e1 = Endpoint(client, "one", 1, "k")
        e2 = Endpoint(client, "two", 2, "k")
        with patch.object(
            client, "get_endpoints", new_callable=AsyncMock, return_value=[e1, e2]
        ):
            got = await client.get_endpoint("two")
        assert got is e2

    async def test_get_endpoint_raises_when_name_not_found(self, client) -> None:
        """
        Verifies get_endpoint raises when no endpoint matches the name.

        This test verifies by:
        1. Patching get_endpoints to return an empty list
        2. Asserting Exception mentioning the endpoint name

        Assumptions:
        - Empty list yields no match
        """
        with patch.object(
            client, "get_endpoints", new_callable=AsyncMock, return_value=[]
        ):
            with pytest.raises(Exception, match="could not be found"):
                await client.get_endpoint("nope")


@pytest.mark.asyncio
class TestServerlessWorkersAndSessions:
    """get_endpoint_workers, get_endpoint_session, end_endpoint_session, start_endpoint_session."""

    async def test_get_endpoint_workers_requires_endpoint_type(self, client) -> None:
        """
        Verifies get_endpoint_workers rejects non-Endpoint values.

        This test verifies by:
        1. Passing a MagicMock instead of Endpoint
        2. Asserting ValueError

        Assumptions:
        - isinstance check runs before HTTP
        """
        with pytest.raises(ValueError, match="endpoint must be an Endpoint"):
            await client.get_endpoint_workers(MagicMock())

    async def test_get_endpoint_workers_returns_worker_list(
        self, client, make_mock_http_response, make_serverless_endpoint
    ) -> None:
        """
        Verifies get_endpoint_workers parses JSON list into Worker models.

        This test verifies by:
        1. Attaching a mock aiohttp session with post returning worker dicts
        2. Calling await client.get_endpoint_workers(endpoint)
        3. Asserting Worker.id and count

        Assumptions:
        - _session.post is used with JSON body containing endpoint id and api_key
        """
        mock_sess = MagicMock()
        mock_sess.post = MagicMock(
            return_value=make_mock_http_response(
                status=200,
                json_data=[{"id": 99, "status": "RUNNING"}],
            )
        )
        client._session = mock_sess
        ep = make_serverless_endpoint(client, endpoint_id=3)
        workers = await client.get_endpoint_workers(ep)
        assert len(workers) == 1
        assert workers[0].id == 99

    async def test_get_endpoint_workers_error_msg_returns_empty_list(
        self, client, make_mock_http_response, make_serverless_endpoint
    ) -> None:
        """
        Verifies get_endpoint_workers returns [] when API returns error_msg dict.

        This test verifies by:
        1. Returning JSON dict with error_msg key from post()
        2. Asserting empty list result

        Assumptions:
        - Client treats error_msg as soft failure for not-ready endpoints
        """
        mock_sess = MagicMock()
        mock_sess.post = MagicMock(
            return_value=make_mock_http_response(
                status=200, json_data={"error_msg": "not ready"}
            )
        )
        client._session = mock_sess
        ep = make_serverless_endpoint(client, endpoint_id=3)
        workers = await client.get_endpoint_workers(ep)
        assert workers == []

    async def test_get_endpoint_session_builds_session(
        self, client, make_serverless_endpoint
    ) -> None:
        """
        Verifies get_endpoint_session calls _make_request and constructs Session.

        This test verifies by:
        1. Patching _make_request with ok JSON containing auth_data with url
        2. Awaiting get_endpoint_session
        3. Asserting Session fields

        Assumptions:
        - session_auth dict includes url used for worker request and Session.url
        """
        ep = make_serverless_endpoint(client)
        auth = {"url": "https://worker/s", "token": "t"}
        fake = {
            "ok": True,
            "json": {
                "auth_data": auth,
                "lifetime": 120.0,
                "expiration": "2099-01-01",
            },
        }
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            return_value=fake,
        ):
            sess = await client.get_endpoint_session(ep, 42, auth, timeout=5.0)
        assert sess.endpoint is ep
        assert sess.session_id == 42
        assert sess.auth_data == auth
        assert sess.url == "https://worker/s"

    async def test_end_endpoint_session_calls_make_request(
        self, client, make_serverless_endpoint, make_serverless_bound_session
    ) -> None:
        """
        Verifies end_endpoint_session POSTs to session.url via _make_request.

        This test verifies by:
        1. Patching _make_request to return ok
        2. Building a minimal Session with url and auth_data
        3. Awaiting end_endpoint_session and asserting _make_request kwargs

        Assumptions:
        - Route is /session/end and body includes session_id and session_auth
        """
        ep = make_serverless_endpoint(client)
        sess = make_serverless_bound_session(
            client,
            endpoint=ep,
            url="https://worker/end",
            auth_data={"a": 1},
        )
        with patch(
            "vastai.serverless.client.client._make_request", new_callable=AsyncMock
        ) as mock_mr:
            mock_mr.return_value = {"ok": True, "json": {}}
            await client.end_endpoint_session(sess, timeout=8.0)
        mock_mr.assert_awaited_once()
        call_kw = mock_mr.await_args.kwargs
        assert call_kw["url"] == "https://worker/end"
        assert call_kw["route"] == "/session/end"
        assert call_kw["body"]["session_id"] == "sid"

    async def test_start_endpoint_session_uses_queue_result(
        self, client, make_serverless_endpoint
    ) -> None:
        """
        Verifies start_endpoint_session awaits queue_endpoint_request and returns Session.

        This test verifies by:
        1. Patching queue_endpoint_request to return a pre-resolved ServerlessRequest
        2. Awaiting start_endpoint_session
        3. Asserting Session session_id, url, and auth_data

        Assumptions:
        - queue_endpoint_request result dict matches successful worker create shape
        """
        ep = make_serverless_endpoint(client)
        fut = ServerlessRequest()
        fut.set_result(
            {
                "ok": True,
                "response": {"session_id": "new-sid", "expiration": "ex"},
                "url": "https://w/u",
                "auth_data": {"k": "v"},
            }
        )
        with patch.object(client, "queue_endpoint_request", return_value=fut):
            sess = await client.start_endpoint_session(ep, cost=50, lifetime=30.0)
        assert sess.session_id == "new-sid"
        assert sess.expiration == "ex"
        assert sess.url == "https://w/u"
        assert sess.auth_data == {"k": "v"}
        assert sess.lifetime == 30.0


@pytest.mark.asyncio
class TestQueueEndpointRequest:
    """Background task for worker requests (session-bound path)."""

    async def test_queue_endpoint_request_with_session_sets_result_on_success(
        self, client, make_serverless_endpoint, make_serverless_bound_session
    ) -> None:
        """
        Verifies queue_endpoint_request completes when session is set and worker returns ok JSON.

        This test verifies by:
        1. Patching _make_request to return ok with JSON body
        2. Awaiting the returned ServerlessRequest future
        3. Asserting response payload, url, and auth_data echo session fields

        Assumptions:
        - Session-bound path skips _route polling and posts directly to session.url
        """
        ep = make_serverless_endpoint(client)
        sess = make_serverless_bound_session(
            client,
            endpoint=ep,
            session_id="sid-99",
            expiration="2099-01-01",
            url="https://worker/direct",
        )
        with patch(
            "vastai.serverless.client.client._make_request", new_callable=AsyncMock
        ) as mock_mr:
            mock_mr.return_value = {"ok": True, "json": {"answer": 42}}
            fut = client.queue_endpoint_request(
                ep, "/do", {"p": 1}, session=sess, worker_timeout=30.0
            )
            result = await fut
        assert result["ok"] is True
        assert result["response"] == {"answer": 42}
        assert result["url"] == "https://worker/direct"
        assert result["auth_data"] == {"token": "t"}
        mock_mr.assert_awaited()
        call_kw = mock_mr.await_args.kwargs
        assert call_kw["url"] == "https://worker/direct"
        assert call_kw["route"] == "/do"


@pytest.mark.asyncio
class TestServerlessContextAndSessionState:
    """Async context manager, is_open, close."""

    async def test_is_open_false_without_session(self, client) -> None:
        """
        Verifies is_open is False before _get_session creates a session.

        This test verifies by:
        1. Constructing Serverless
        2. Calling is_open() synchronously

        Assumptions:
        - _session starts as None
        """
        assert client.is_open() is False

    async def test_close_noop_when_no_session(self, client) -> None:
        """
        Verifies close does not fail when no session exists.

        This test verifies by:
        1. Calling await close() on a new client
        2. Completing without error

        Assumptions:
        - close checks _session truthiness and closed flag
        """
        await client.close()

    async def test_aenter_calls_get_session(self, client) -> None:
        """
        Verifies __aenter__ awaits _get_session and returns self.

        This test verifies by:
        1. Patching _get_session with AsyncMock
        2. Using async with Serverless(...)
        3. Asserting _get_session awaited and entered object is the client

        Assumptions:
        - __aenter__ only opens session, does not require real aiohttp
        """
        with patch.object(client, "_get_session", new_callable=AsyncMock) as mock_gs:
            async with client as entered:
                assert entered is client
            mock_gs.assert_awaited()


@pytest.mark.asyncio
class TestServerlessSessionApiErrors:
    """Failure paths for get / end / start endpoint session (wrapped exceptions)."""

    async def test_get_endpoint_session_raises_when_worker_http_not_ok(
        self, client, make_serverless_endpoint
    ) -> None:
        ep = make_serverless_endpoint(client)
        auth = {"url": "https://worker/s"}
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            return_value={"ok": False, "status": 503, "text": "unavailable"},
        ):
            with pytest.raises(Exception, match="Error on /session/get"):
                await client.get_endpoint_session(ep, 1, auth)

    async def test_get_endpoint_session_raises_when_auth_data_missing(
        self, client, make_serverless_endpoint
    ) -> None:
        ep = make_serverless_endpoint(client)
        auth = {"url": "https://worker/s"}
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            return_value={"ok": True, "json": {"lifetime": 1.0}},
        ):
            with pytest.raises(Exception, match="Missing auth_data"):
                await client.get_endpoint_session(ep, 1, auth)

    async def test_end_endpoint_session_raises_when_worker_http_not_ok(
        self, client, make_serverless_endpoint, make_serverless_bound_session
    ) -> None:
        ep = make_serverless_endpoint(client)
        sess = make_serverless_bound_session(
            client,
            endpoint=ep,
            session_id="s",
            lifetime=1.0,
            url="https://worker/x",
            auth_data={},
        )
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            return_value={"ok": False, "json": {"error": "gone"}},
        ):
            with pytest.raises(Exception, match="Error on /session/end"):
                await client.end_endpoint_session(sess)

    async def test_start_endpoint_session_raises_when_queue_returns_not_ok(
        self, client, make_serverless_endpoint
    ) -> None:
        ep = make_serverless_endpoint(client)
        fut = ServerlessRequest()
        fut.set_result({"ok": False, "text": "nope"})
        with patch.object(client, "queue_endpoint_request", return_value=fut):
            with pytest.raises(Exception, match="Error on /session/create"):
                await client.start_endpoint_session(ep)

    async def test_start_endpoint_session_raises_when_url_missing(
        self, client, make_serverless_endpoint
    ) -> None:
        ep = make_serverless_endpoint(client)
        fut = ServerlessRequest()
        fut.set_result(
            {
                "ok": True,
                "response": {"session_id": "id", "expiration": "e"},
                "auth_data": {"k": "v"},
            }
        )
        with patch.object(client, "queue_endpoint_request", return_value=fut):
            with pytest.raises(Exception, match="Missing URL"):
                await client.start_endpoint_session(ep)

    async def test_start_endpoint_session_raises_when_auth_data_missing(
        self, client, make_serverless_endpoint
    ) -> None:
        ep = make_serverless_endpoint(client)
        fut = ServerlessRequest()
        fut.set_result(
            {
                "ok": True,
                "response": {"session_id": "id", "expiration": "e"},
                "url": "https://w",
            }
        )
        with patch.object(client, "queue_endpoint_request", return_value=fut):
            with pytest.raises(Exception, match="Missing auth data"):
                await client.start_endpoint_session(ep)

    async def test_start_endpoint_session_raises_when_session_id_missing(
        self, client, make_serverless_endpoint
    ) -> None:
        ep = make_serverless_endpoint(client)
        fut = ServerlessRequest()
        fut.set_result(
            {
                "ok": True,
                "response": {"expiration": "e"},
                "url": "https://w",
                "auth_data": {"k": "v"},
            }
        )
        with patch.object(client, "queue_endpoint_request", return_value=fut):
            with pytest.raises(Exception, match="Missing session id"):
                await client.start_endpoint_session(ep)

    @pytest.mark.parametrize(
        "queue_payload",
        [
            {"ok": True, "url": "https://w", "auth_data": {"k": "v"}},
            {
                "ok": True,
                "response": None,
                "url": "https://w",
                "auth_data": {"k": "v"},
            },
        ],
    )
    async def test_start_endpoint_session_raises_when_response_body_missing(
        self, client, make_serverless_endpoint, queue_payload: dict
    ) -> None:
        """
        Missing or null ``response`` raises
        """
        ep = make_serverless_endpoint(client)
        fut = ServerlessRequest()
        fut.set_result(queue_payload)
        with patch.object(client, "queue_endpoint_request", return_value=fut):
            with pytest.raises(Exception, match="No response from /session/create"):
                await client.start_endpoint_session(ep)

    async def test_start_endpoint_session_wraps_when_response_not_mapping(
        self, client, make_serverless_endpoint
    ) -> None:
        """Non-dict ``response`` is rejected and wrapped as ``Failed to create session``."""
        ep = make_serverless_endpoint(client)
        fut = ServerlessRequest()
        fut.set_result(
            {
                "ok": True,
                "response": [],
                "url": "https://w",
                "auth_data": {"k": "v"},
            }
        )
        with patch.object(client, "queue_endpoint_request", return_value=fut):
            with pytest.raises(Exception, match="Failed to create session"):
                await client.start_endpoint_session(ep)


@pytest.mark.asyncio
class TestStartEndpointSessionQueueContract:
    """Ensure session creation request matches the worker API contract."""

    async def test_start_endpoint_session_forwards_on_close_and_cost_to_queue(
        self, client, make_serverless_endpoint
    ) -> None:
        ep = make_serverless_endpoint(client)
        captured: dict = {}

        def _capture_queue(**kwargs):
            captured.update(kwargs)
            fut = ServerlessRequest()
            fut.set_result(
                {
                    "ok": True,
                    "response": {"session_id": "new", "expiration": "ex"},
                    "url": "https://w",
                    "auth_data": {"t": 1},
                }
            )
            return fut

        with patch.object(client, "queue_endpoint_request", side_effect=_capture_queue):
            await client.start_endpoint_session(
                ep,
                cost=77,
                lifetime=88.0,
                on_close_route="/bye",
                on_close_payload={"reason": "idle"},
                timeout=12.0,
            )

        assert captured["endpoint"] is ep
        assert captured["worker_route"] == "/session/create"
        assert captured["cost"] == 77
        assert captured["timeout"] == 12.0
        wp = captured["worker_payload"]
        assert wp["lifetime"] == 88.0
        assert wp["on_close_route"] == "/bye"
        assert wp["on_close_payload"] == {"reason": "idle"}


# ===========================================================================
# Gap-closing tests – functionality not covered by the tests above
# ===========================================================================


class TestServerlessRequestExceptionPath:
    """ServerlessRequest.then silences exceptions instead of forwarding them."""

    @pytest.mark.asyncio
    async def test_then_does_not_invoke_callback_when_future_has_exception(
        self,
    ) -> None:
        """
        Verifies that .then callback is NOT called when the future resolves with an exception.

        This test verifies by:
        1. Attaching a MagicMock callback via .then
        2. Setting an exception on the future
        3. Yielding to the event loop and asserting the callback was not called

        Assumptions:
        - The _done wrapper prints the exception and returns early without calling callback
        """
        cb = MagicMock()
        req = ServerlessRequest()
        req.then(cb)
        req.set_exception(RuntimeError("oops"))
        await asyncio.sleep(0)
        cb.assert_not_called()


class TestServerlessInitEdgeCases:
    """Serverless.__init__ branches not covered by the parametrised instance tests."""

    def test_unknown_instance_falls_back_to_prod_urls(self) -> None:
        """
        Verifies that an unrecognised instance name falls through to the prod URLs.

        This test verifies by:
        1. Constructing Serverless with instance='staging' (not a known value)
        2. Asserting autoscaler_url and vast_web_url match prod defaults

        Assumptions:
        - match/case _: branch uses run.vast.ai / console.vast.ai
        """
        sl = Serverless(api_key="k", instance="staging")
        assert "run.vast.ai" in sl.autoscaler_url
        assert "console.vast.ai" in sl.vast_web_url

    def test_debug_mode_adds_stream_handler_and_disables_propagation(self) -> None:
        """
        Verifies debug=True attaches a StreamHandler, sets DEBUG level, and stops propagation.

        This test verifies by:
        1. Constructing Serverless(debug=True)
        2. Checking logger.propagate is False and a StreamHandler is present

        Assumptions:
        - Non-debug path sets propagate=True; debug path sets it False
        """
        sl = Serverless(api_key="k", debug=True)
        try:
            assert sl.logger.propagate is False
            assert sl.logger.level == logging.DEBUG
            assert any(isinstance(h, logging.StreamHandler) for h in sl.logger.handlers)
        finally:
            while sl.logger.handlers:
                sl.logger.removeHandler(sl.logger.handlers[0])


class TestServerlessSessionLifecycle:
    """close() and is_open() with a real (mocked) aiohttp session."""

    @pytest.mark.asyncio
    async def test_close_awaits_aiohttp_session_close_when_open(self, client) -> None:
        """
        Verifies close() awaits session.close() when the internal session is open.

        This test verifies by:
        1. Attaching a mock session with closed=False
        2. Awaiting client.close()
        3. Asserting session.close was awaited once

        Assumptions:
        - close() checks _session and not _session.closed before closing
        """
        mock_sess = MagicMock()
        mock_sess.closed = False
        mock_sess.close = AsyncMock()
        client._session = mock_sess
        await client.close()
        mock_sess.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_skips_when_session_already_closed(self, client) -> None:
        """
        Verifies close() is a no-op when the internal session is already closed.

        This test verifies by:
        1. Attaching a mock session with closed=True
        2. Awaiting client.close()
        3. Asserting session.close was NOT called

        Assumptions:
        - Guard: `if self._session and not self._session.closed`
        """
        mock_sess = MagicMock()
        mock_sess.closed = True
        mock_sess.close = AsyncMock()
        client._session = mock_sess
        await client.close()
        mock_sess.close.assert_not_awaited()

    def test_is_open_true_when_session_exists_and_not_closed(self, client) -> None:
        """
        Verifies is_open() returns True when _session exists and is not closed.

        This test verifies by:
        1. Attaching a mock session with closed=False
        2. Calling is_open() synchronously
        3. Asserting True

        Assumptions:
        - is_open checks _session is not None and not closed
        """
        mock_sess = MagicMock()
        mock_sess.closed = False
        client._session = mock_sess
        assert client.is_open() is True


@pytest.mark.asyncio
class TestServerlessGetSession:
    """_get_session creates, reuses, and recreates the aiohttp ClientSession."""

    async def test_get_session_creates_when_none(self, client) -> None:
        """
        Verifies _get_session builds a new ClientSession when _session is None.

        This test verifies by:
        1. Patching get_ssl_context, aiohttp.TCPConnector, aiohttp.ClientSession
        2. Calling _get_session()
        3. Asserting the mock session is stored and returned

        Assumptions:
        - TCPConnector is created with ssl=None (mocked context)
        - ClientSession is called with connector=
        """
        mock_connector = MagicMock()
        mock_aio_session = MagicMock()
        mock_aio_session.closed = False
        with (
            patch.object(
                client, "get_ssl_context", new_callable=AsyncMock, return_value=None
            ),
            patch(
                "vastai.serverless.client.client.aiohttp.TCPConnector",
                return_value=mock_connector,
            ),
            patch(
                "vastai.serverless.client.client.aiohttp.ClientSession",
                return_value=mock_aio_session,
            ) as mock_cs,
        ):
            result = await client._get_session()
        assert result is mock_aio_session
        assert client._session is mock_aio_session
        mock_cs.assert_called_once_with(connector=mock_connector)

    async def test_get_session_reuses_existing_open_session(self, client) -> None:
        """
        Verifies _get_session returns the existing session when it is open.

        This test verifies by:
        1. Assigning a mock open session to client._session
        2. Calling _get_session()
        3. Asserting the same object is returned without creating a new one

        Assumptions:
        - The if-branch is skipped when session exists and is not closed
        """
        existing = MagicMock()
        existing.closed = False
        client._session = existing
        result = await client._get_session()
        assert result is existing

    async def test_get_session_recreates_when_closed(self, client) -> None:
        """
        Verifies _get_session creates a fresh session when the old one is closed.

        This test verifies by:
        1. Assigning a closed mock session
        2. Calling _get_session()
        3. Asserting a new session is created and stored

        Assumptions:
        - `self._session.closed == True` triggers session recreation
        """
        old = MagicMock()
        old.closed = True
        client._session = old
        new_sess = MagicMock()
        new_sess.closed = False
        with (
            patch.object(
                client, "get_ssl_context", new_callable=AsyncMock, return_value=None
            ),
            patch(
                "vastai.serverless.client.client.aiohttp.TCPConnector",
                return_value=MagicMock(),
            ),
            patch(
                "vastai.serverless.client.client.aiohttp.ClientSession",
                return_value=new_sess,
            ),
        ):
            result = await client._get_session()
        assert result is new_sess


@pytest.mark.asyncio
class TestServerlessGetEndpointsExceptionWrapping:
    """get_endpoints wraps _make_request exceptions."""

    async def test_get_endpoints_wraps_make_request_exception(self, client) -> None:
        """
        Verifies get_endpoints wraps a _make_request transport failure in Exception.

        This test verifies by:
        1. Making _make_request raise RuntimeError
        2. Asserting Exception with 'Failed to get endpoints' message

        Assumptions:
        - except clause at lines 166-167 converts any error to a clear message
        """
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            side_effect=RuntimeError("network down"),
        ):
            with pytest.raises(Exception, match="Failed to get endpoints"):
                await client.get_endpoints()


@pytest.mark.asyncio
class TestGetEndpointWorkersErrors:
    """get_endpoint_workers HTTP failure and unexpected-type paths."""

    async def test_raises_on_non_200_http_status(
        self, client, make_mock_http_response, make_serverless_endpoint
    ) -> None:
        """
        Verifies get_endpoint_workers raises RuntimeError on non-200 HTTP.

        This test verifies by:
        1. Returning status=503 from _session.post
        2. Asserting RuntimeError mentioning 'get_endpoint_workers failed'

        Assumptions:
        - post() is used as async-context-manager; make_mock_http_response provides that
        """
        mock_sess = MagicMock()
        mock_sess.post = MagicMock(
            return_value=make_mock_http_response(status=503, text="service unavailable")
        )
        client._session = mock_sess
        ep = make_serverless_endpoint(client)
        with pytest.raises(RuntimeError, match="get_endpoint_workers failed"):
            await client.get_endpoint_workers(ep)

    async def test_raises_on_unexpected_response_type(
        self, client, make_mock_http_response, make_serverless_endpoint
    ) -> None:
        """
        Verifies get_endpoint_workers raises RuntimeError when response is not list or dict.

        This test verifies by:
        1. Returning json_data='unexpected-string' from the mock response
        2. Asserting RuntimeError mentioning 'Unexpected response type'

        Assumptions:
        - isinstance(data, dict) is False; isinstance(data, list) is False for a str
        """
        mock_sess = MagicMock()
        mock_sess.post = MagicMock(
            return_value=make_mock_http_response(
                status=200, json_data="unexpected-string"
            )
        )
        client._session = mock_sess
        ep = make_serverless_endpoint(client)
        with pytest.raises(RuntimeError, match="Unexpected response type"):
            await client.get_endpoint_workers(ep)


@pytest.mark.asyncio
class TestTimeoutErrorPropagation:
    """asyncio.TimeoutError must propagate through all three session API methods."""

    async def test_get_endpoint_session_propagates_timeout(
        self, client, make_serverless_endpoint
    ) -> None:
        """
        Verifies get_endpoint_session re-raises asyncio.TimeoutError.

        This test verifies by:
        1. Making _make_request raise asyncio.TimeoutError
        2. Asserting the same exception type escapes get_endpoint_session

        Assumptions:
        - `except asyncio.TimeoutError: raise` at line 249 is the re-raise path
        """
        ep = make_serverless_endpoint(client)
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            side_effect=asyncio.TimeoutError(),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await client.get_endpoint_session(ep, 1, {"url": "https://w"})

    async def test_end_endpoint_session_propagates_timeout(
        self, client, make_serverless_endpoint, make_serverless_bound_session
    ) -> None:
        """
        Verifies end_endpoint_session re-raises asyncio.TimeoutError.

        This test verifies by:
        1. Making _make_request raise asyncio.TimeoutError
        2. Asserting it escapes end_endpoint_session

        Assumptions:
        - `except asyncio.TimeoutError: raise` at line 282 is the re-raise path
        """
        ep = make_serverless_endpoint(client)
        sess = make_serverless_bound_session(
            client,
            endpoint=ep,
            session_id="s",
            lifetime=1.0,
            url="https://worker/x",
            auth_data={},
        )
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            side_effect=asyncio.TimeoutError(),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await client.end_endpoint_session(sess)

    async def test_start_endpoint_session_propagates_timeout(
        self, client, make_serverless_endpoint
    ) -> None:
        """
        Verifies start_endpoint_session re-raises asyncio.TimeoutError from queue result.

        This test verifies by:
        1. Resolving the ServerlessRequest with an asyncio.TimeoutError exception
        2. Asserting it escapes start_endpoint_session

        Assumptions:
        - `except asyncio.TimeoutError: raise` at line 324 handles this
        """
        ep = make_serverless_endpoint(client)
        fut = ServerlessRequest()
        fut.set_exception(asyncio.TimeoutError("timed out"))
        with patch.object(client, "queue_endpoint_request", return_value=fut):
            with pytest.raises(asyncio.TimeoutError):
                await client.start_endpoint_session(ep)


@pytest.mark.asyncio
class TestQueueEndpointRequestRoutingPath:
    """queue_endpoint_request without a session: _route polling, error recovery, retries."""

    async def test_no_session_immediate_ready_returns_success(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies the no-session path completes when _route is immediately READY.

        This test verifies by:
        1. Making _route return a READY RouteResponse
        2. Making _make_request return ok JSON
        3. Asserting the future resolves with the expected response and url

        Assumptions:
        - Session-less path calls endpoint._route to get worker_url and auth_data
        """
        ep = make_serverless_endpoint(client_with_session)
        ready = make_route_response_mock(
            status="READY", url="https://w/", request_idx=5
        )
        with (
            patch.object(ep, "_route", new_callable=AsyncMock, return_value=ready),
            patch(
                "vastai.serverless.client.client._make_request",
                new_callable=AsyncMock,
                return_value={"ok": True, "json": {"result": "done"}},
            ),
        ):
            result = await client_with_session.queue_endpoint_request(
                ep, "/predict", {"x": 1}
            )
        assert result["ok"] is True
        assert result["response"] == {"result": "done"}
        assert result["url"] == "https://w/"

    async def test_no_session_polls_waiting_then_ready(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies the no-session polling loop transitions from WAITING to READY.

        This test verifies by:
        1. First _route call returns WAITING; second returns READY
        2. Asserting the future eventually resolves ok

        Assumptions:
        - while route.status != 'READY' loop re-calls _route and sleeps (sleep is mocked)
        """
        ep = make_serverless_endpoint(client_with_session)
        waiting = make_route_response_mock(status="WAITING", request_idx=1)
        ready = make_route_response_mock(
            status="READY", url="https://w/", request_idx=1
        )
        with (
            patch.object(
                ep, "_route", new_callable=AsyncMock, side_effect=[waiting, ready]
            ),
            patch(
                "vastai.serverless.client.client._make_request",
                new_callable=AsyncMock,
                return_value={"ok": True, "json": {"result": "ok"}},
            ),
        ):
            result = await client_with_session.queue_endpoint_request(
                ep, "/predict", {"x": 1}
            )
        assert result["ok"] is True

    async def test_no_session_times_out_before_route(
        self,
        client_with_session,
        make_serverless_endpoint,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies queue_endpoint_request raises TimeoutError when elapsed >= timeout before _route.

        This test verifies by:
        1. Patching time.time: first 2 calls return 0.0 (ServerlessRequest init + start_time);
           all subsequent calls return 999.0 (timeout condition + error-message formatting + any extras)
        2. Asserting asyncio.TimeoutError propagates from the future

        Assumptions:
        - Timeout check runs at top of while loop before calling _route
        - ``queue_endpoint_request`` logs ``Queued endpoint request`` synchronously; a LogRecord
          calls ``time.time()`` unless ``info`` is stubbed, which would otherwise desynchronize
          the clock mock (CI often enables logging where local runs skip ``info``).
        """
        ep = make_serverless_endpoint(client_with_session)
        time_seq = itertools.chain((0.0,), itertools.repeat(999.0))
        with (
            patch.object(client_with_session.logger, "info"),
            patch.object(client_with_session.logger, "disabled", True),
            patch(
                "vastai.serverless.client.client.time.time",
                side_effect=lambda: next(time_seq),
            ),
        ):
            fut = client_with_session.queue_endpoint_request(
                ep, "/predict", {"x": 1}, timeout=1.0
            )
            with pytest.raises(asyncio.TimeoutError):
                await fut

    async def test_session_connector_error_marks_session_closed_and_raises(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_serverless_bound_session,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies ConnectorError on a session-bound request marks session.open=False and raises.

        This test verifies by:
        1. Patching _make_request to raise ClientConnectorError
        2. Asserting ConnectionError escapes the future
        3. Asserting session.open is False

        Assumptions:
        - Session-bound path cannot re-route; exception is fatal for the session
        """
        ep = make_serverless_endpoint(client_with_session)
        sess = make_serverless_bound_session(
            client_with_session, endpoint=ep, session_id="s"
        )
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            side_effect=aiohttp.ClientConnectorError(MagicMock(), OSError("gone")),
        ):
            with pytest.raises(ConnectionError, match="Session worker unavailable"):
                await client_with_session.queue_endpoint_request(
                    ep, "/predict", {"x": 1}, session=sess
                )
        assert sess.open is False

    async def test_no_session_connector_error_retries_on_new_route(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies ConnectorError without a session triggers a retry via a new route.

        This test verifies by:
        1. First _make_request call raises ClientConnectorError
        2. Second _make_request call returns success
        3. Asserting the future resolves ok

        Assumptions:
        - No-session path resets request_idx and re-calls _route on ConnectorError
        """
        ep = make_serverless_endpoint(client_with_session)
        ready = make_route_response_mock(
            status="READY", url="https://w/", request_idx=1
        )
        with (
            patch.object(ep, "_route", new_callable=AsyncMock, return_value=ready),
            patch(
                "vastai.serverless.client.client._make_request",
                new_callable=AsyncMock,
                side_effect=[
                    aiohttp.ClientConnectorError(MagicMock(), OSError("gone")),
                    {"ok": True, "json": {"result": "retried"}},
                ],
            ),
        ):
            result = await client_with_session.queue_endpoint_request(
                ep, "/predict", {"x": 1}
            )
        assert result["ok"] is True
        assert result["response"] == {"result": "retried"}

    async def test_non_ok_non_retryable_returns_raw_http_result(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_serverless_bound_session,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies a non-ok, non-retryable response is returned as a raw result dict.

        This test verifies by:
        1. Making _make_request return ok=False, retryable=False
        2. Asserting the future resolves with ok=False and the correct status

        Assumptions:
        - When retry=False or retryable=False, the raw HTTP result is set on the future
        """
        ep = make_serverless_endpoint(client_with_session)
        sess = make_serverless_bound_session(client_with_session, endpoint=ep)
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            return_value={
                "ok": False,
                "status": 422,
                "text": "invalid input",
                "json": {"error": "bad"},
                "retryable": False,
            },
        ):
            result = await client_with_session.queue_endpoint_request(
                ep, "/predict", {"x": 1}, session=sess, retry=False
            )
        assert result["ok"] is False
        assert result["status"] == 422
        assert result["response"] == {"error": "bad"}

    async def test_retryable_result_retries_then_succeeds(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_serverless_bound_session,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies a retryable non-ok response causes a retry and eventually succeeds.

        This test verifies by:
        1. First _make_request returns ok=False, retryable=True
        2. Second _make_request returns ok=True
        3. Asserting the future resolves ok

        Assumptions:
        - retry=True and retryable=True triggers sleep + continue; sleep is mocked instant
        """
        ep = make_serverless_endpoint(client_with_session)
        sess = make_serverless_bound_session(client_with_session, endpoint=ep)
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            side_effect=[
                {
                    "ok": False,
                    "status": 503,
                    "text": "overloaded",
                    "json": None,
                    "retryable": True,
                },
                {"ok": True, "json": {"done": True}, "status": 200, "text": ""},
            ],
        ):
            result = await client_with_session.queue_endpoint_request(
                ep, "/predict", {"x": 1}, session=sess, retry=True
            )
        assert result["ok"] is True
        assert result["response"] == {"done": True}

    async def test_exception_from_route_sets_future_exception(
        self,
        client_with_session,
        make_serverless_endpoint,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies an exception escaping _route is captured as the future's exception.

        This test verifies by:
        1. Making endpoint._route raise RuntimeError
        2. Asserting the awaited future raises the same RuntimeError

        Assumptions:
        - Outer except Exception in task() calls request.set_exception(ex)
        """
        ep = make_serverless_endpoint(client_with_session)
        with patch.object(
            ep,
            "_route",
            new_callable=AsyncMock,
            side_effect=RuntimeError("routing failed"),
        ):
            with pytest.raises(RuntimeError, match="routing failed"):
                await client_with_session.queue_endpoint_request(ep, "/predict", {})

    async def test_cancel_propagates_to_background_task(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_serverless_bound_session,
    ) -> None:
        """
        Verifies cancelling the returned future also cancels the background asyncio task.

        This test verifies by:
        1. Stalling _make_request on an asyncio.Future (never resolves until cancelled)
        2. Cancelling the ServerlessRequest future after the bg task has started
        3. Asserting the future ends in cancelled state

        Assumptions:
        - _propagate_cancel done-callback calls bg_task.cancel() (line 512)
        """
        ep = make_serverless_endpoint(client_with_session)
        sess = make_serverless_bound_session(client_with_session, endpoint=ep)
        reached = asyncio.Event()

        async def _stall(*args, **kwargs):
            reached.set()
            await asyncio.Future()  # blocks until the task is cancelled

        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            side_effect=_stall,
        ):
            fut = client_with_session.queue_endpoint_request(
                ep, "/predict", {}, session=sess
            )
            await reached.wait()
            fut.cancel()

            async def _until_cancelled() -> None:
                while not fut.cancelled():
                    await asyncio.sleep(0)

            await asyncio.wait_for(_until_cancelled(), timeout=2.0)
        assert fut.cancelled()

    async def test_no_session_ready_with_zero_request_idx_still_completes(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies routing succeeds when autoscaler returns READY but request_idx is 0.

        The client logs a missing-index warning for falsy request_idx; work still proceeds.
        """
        ep = make_serverless_endpoint(client_with_session)
        ready = make_route_response_mock(
            status="READY", url="https://w/", request_idx=0
        )
        with (
            patch.object(ep, "_route", new_callable=AsyncMock, return_value=ready),
            patch(
                "vastai.serverless.client.client._make_request",
                new_callable=AsyncMock,
                return_value={"ok": True, "json": {"v": 0}, "status": 200, "text": ""},
            ),
        ):
            result = await client_with_session.queue_endpoint_request(
                ep, "/predict", {"x": 1}
            )
        assert result["ok"] is True
        assert result["response"] == {"v": 0}
        assert result["request_idx"] == 0

    async def test_no_session_times_out_while_polling_for_ready(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """Timeout inside the WAITING→READY poll loop surfaces as asyncio.TimeoutError."""
        ep = make_serverless_endpoint(client_with_session)
        waiting = make_route_response_mock(status="WAITING", request_idx=1)

        def fake_time():
            fake_time.n += 1
            # First four reads stay at t=0; thereafter pretend we are past the deadline.
            return 0.0 if fake_time.n <= 4 else 100.0

        fake_time.n = 0

        with (
            patch.object(client_with_session.logger, "info"),
            patch.object(client_with_session.logger, "debug"),
            patch.object(client_with_session.logger, "disabled", True),
            patch.object(ep, "_route", new_callable=AsyncMock, return_value=waiting),
            patch("vastai.serverless.client.client.time.time", side_effect=fake_time),
        ):
            fut = client_with_session.queue_endpoint_request(
                ep, "/predict", {"x": 1}, timeout=5.0
            )
            with pytest.raises(asyncio.TimeoutError, match="become ready"):
                await fut

    async def test_no_session_worker_generic_exception_retries_then_succeeds(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Non-transport exceptions from _make_request trigger a retry (outer loop), not failure.
        """
        ep = make_serverless_endpoint(client_with_session)
        ready = make_route_response_mock(
            status="READY", url="https://w/", request_idx=2
        )
        with (
            patch.object(ep, "_route", new_callable=AsyncMock, return_value=ready),
            patch(
                "vastai.serverless.client.client._make_request",
                new_callable=AsyncMock,
                side_effect=[
                    ValueError("worker glitch"),
                    {
                        "ok": True,
                        "json": {"recovered": True},
                        "status": 200,
                        "text": "",
                    },
                ],
            ),
        ):
            result = await client_with_session.queue_endpoint_request(
                ep, "/predict", {"x": 1}
            )
        assert result["ok"] is True
        assert result["response"] == {"recovered": True}

    async def test_retryable_worker_response_times_out_before_retry(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_serverless_bound_session,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """If overall timeout is exhausted before a retryable sleep, raise TimeoutError."""
        ep = make_serverless_endpoint(client_with_session)
        sess = make_serverless_bound_session(client_with_session, endpoint=ep)

        def fake_time():
            fake_time.n += 1
            return 0.0 if fake_time.n <= 3 else 2.0

        fake_time.n = 0

        with (
            patch.object(client_with_session.logger, "info"),
            patch.object(client_with_session.logger, "debug"),
            patch.object(client_with_session.logger, "disabled", True),
            patch("vastai.serverless.client.client.time.time", side_effect=fake_time),
            patch(
                "vastai.serverless.client.client._make_request",
                new_callable=AsyncMock,
                return_value={
                    "ok": False,
                    "retryable": True,
                    "status": 503,
                    "text": "busy",
                    "json": None,
                },
            ),
        ):
            fut = client_with_session.queue_endpoint_request(
                ep, "/p", {}, session=sess, retry=True, timeout=1.0
            )
            with pytest.raises(asyncio.TimeoutError, match="Request timed out"):
                await fut

    async def test_session_stream_true_places_stream_body_in_response(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_serverless_bound_session,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """When stream=True, the future result uses result['stream'] as the response payload."""
        ep = make_serverless_endpoint(client_with_session)
        sess = make_serverless_bound_session(client_with_session, endpoint=ep)
        stream_body = object()
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            return_value={"ok": True, "stream": stream_body, "status": 200, "text": ""},
        ):
            result = await client_with_session.queue_endpoint_request(
                ep, "/predict", {}, session=sess, stream=True
            )
        assert result["ok"] is True
        assert result["response"] is stream_body
