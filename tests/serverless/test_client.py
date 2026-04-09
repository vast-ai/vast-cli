"""Unit tests for vastai.serverless.client.client (Serverless, ServerlessRequest).

All HTTP and SSL fetch paths are mocked; no real network calls.

Coverage notes (functionality-oriented):
- ``ServerlessRequest.then``: stdout on exception path
- ``__init__``: instance match arms (prod/alpha/local/candidate/default), ``debug`` logging,
  ``VAST_API_KEY`` (subprocess import), connection/tuning kwargs, preconfigured logger
- ``_get_session``: ``TCPConnector(limit=connection_limit)``
- ``get_ssl_context``: non-200 cert response
- Session helpers: ``/session/get`` and ``/session/end`` success and error paths, ``TimeoutError`` passthrough
- ``start_endpoint_session``: validation of queue result shape
- ``queue_endpoint_request``: timeouts, retry branches, session shortcut, transport errors,
  non-OK worker responses, stream mode, task cancellation, ``latencies``, session without URL,
  ``_route`` failure → ``Errored``
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from vastai.serverless.client import client as serverless_client_mod
from vastai.serverless.client.client import Serverless, ServerlessRequest
from vastai.serverless.client.endpoint import Endpoint
from vastai.serverless.client.session import Session

# Repo root (tests/serverless -> parents[2]) for subprocess imports of ``vastai``.
_REPO_ROOT = str(Path(__file__).resolve().parents[2])


# ---------------------------------------------------------------------------
# ServerlessRequest
# ---------------------------------------------------------------------------


class TestServerlessRequest:
    """Verify ServerlessRequest future wrapper and then() chaining."""

    def test_then_invokes_callback_with_result_on_success(self) -> None:
        """
        Verifies that then() registers a done callback that receives the future result.

        This test verifies by:
        1. Creating a ServerlessRequest and chaining then() with a callback that appends results
        2. Resolving the future with a known value
        3. Running the event loop until callbacks run
        4. Asserting the callback received the resolved value

        Assumptions:
        - asyncio event loop processes done callbacks when the future is marked done
        """
        results: list = []

        async def _run() -> None:
            req = ServerlessRequest()
            req.then(lambda r: results.append(r))
            req.set_result("ok")
            await asyncio.sleep(0)

        asyncio.run(_run())
        assert results == ["ok"]

    def test_then_skips_callback_when_future_has_exception(self) -> None:
        """
        Verifies that then()'s callback is not invoked when the future completes with an exception.

        This test verifies by:
        1. Registering then() with a callback that appends to a list
        2. Setting an exception on the future
        3. Yielding to the loop and asserting the callback did not run

        Assumptions:
        - Implementation checks fut.exception() is None before calling the user callback
        """
        results: list = []

        async def _run() -> None:
            req = ServerlessRequest()
            req.then(lambda r: results.append(r))
            req.set_exception(RuntimeError("boom"))
            await asyncio.sleep(0)

        asyncio.run(_run())
        assert results == []

    def test_then_logs_exception_to_stdout_when_future_fails(self, capsys) -> None:
        """then() prints the future's exception before skipping the user callback."""

        async def _run() -> None:
            req = ServerlessRequest()
            req.then(lambda r: None)
            req.set_exception(ValueError("then-exc-marker"))
            await asyncio.sleep(0)

        asyncio.run(_run())
        captured = capsys.readouterr()
        assert "then-exc-marker" in captured.out or "ValueError" in captured.out

    def test_new_request_has_expected_initial_tracking_fields(self) -> None:
        """ServerlessRequest starts in New state with timestamps and index defaults."""

        async def _run() -> None:
            req = ServerlessRequest()
            assert req.status == "New"
            assert req.req_idx == 0
            assert req.start_time is None
            assert req.complete_time is None
            assert isinstance(req.create_time, float)

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Serverless construction and URLs
# ---------------------------------------------------------------------------


class TestServerlessInit:
    """Verify API key validation and instance-based base URLs."""

    def test_raises_attribute_error_when_api_key_is_none(self) -> None:
        """
        Verifies that Serverless raises AttributeError when api_key is None.

        This test verifies by:
        1. Instantiating Serverless(api_key=None) explicitly
        2. Asserting AttributeError with a message about the API key

        Assumptions:
        - Explicit None bypasses environment default for this call
        """
        with pytest.raises(AttributeError, match="API key missing"):
            Serverless(api_key=None)

    def test_raises_attribute_error_when_api_key_is_empty_string(self) -> None:
        """
        Verifies that Serverless raises AttributeError when api_key is the empty string.

        This test verifies by:
        1. Instantiating Serverless(api_key="")
        2. Asserting AttributeError

        Assumptions:
        - Empty string is treated as missing per client implementation
        """
        with pytest.raises(AttributeError, match="API key missing"):
            Serverless(api_key="")

    def test_accepts_explicit_api_key(self) -> None:
        """
        Verifies that Serverless stores a non-empty explicit api_key.

        This test verifies by:
        1. Constructing Serverless(api_key="sk-test")
        2. Asserting client.api_key equals the provided value

        Assumptions:
        - No environment patching required when api_key is passed explicitly
        """
        client = Serverless(api_key="sk-test")
        assert client.api_key == "sk-test"

    def test_instance_prod_sets_console_and_run_urls(self) -> None:
        """
        Verifies that instance='prod' sets autoscaler and web URLs to production hosts.

        This test verifies by:
        1. Creating Serverless with instance='prod'
        2. Asserting autoscaler_url and vast_web_url match expected prod values

        Assumptions:
        - Production URLs are stable contract surface for the SDK
        """
        client = Serverless(api_key="k", instance="prod")
        assert client.autoscaler_url == "https://run.vast.ai"
        assert client.vast_web_url == "https://console.vast.ai"

    def test_instance_alpha_sets_alpha_hosts(self) -> None:
        """
        Verifies that instance='alpha' selects alpha run and web hosts.

        This test verifies by:
        1. Creating Serverless with instance='alpha'
        2. Asserting URLs contain alpha hostnames

        Assumptions:
        - Alpha instance string is supported by match/case in __init__
        """
        client = Serverless(api_key="k", instance="alpha")
        assert client.autoscaler_url == "https://run-alpha.vast.ai"

    def test_instance_local_sets_local_autoscaler(self) -> None:
        """
        Verifies that instance='local' points autoscaler at localhost.

        This test verifies by:
        1. Creating Serverless with instance='local'
        2. Asserting autoscaler_url is http://localhost:8080

        Assumptions:
        - Local dev instance uses fixed port 8080 per implementation
        """
        client = Serverless(api_key="k", instance="local")
        assert client.autoscaler_url == "http://localhost:8080"

    def test_instance_candidate_sets_candidate_hosts(self) -> None:
        """
        Verifies that instance='candidate' selects candidate run and web hosts.

        This test verifies by:
        1. Creating Serverless with instance='candidate'
        2. Asserting autoscaler_url and vast_web_url match candidate endpoints

        Assumptions:
        - Candidate instance string is supported by match/case in __init__
        """
        client = Serverless(api_key="k", instance="candidate")
        assert client.autoscaler_url == "https://run-candidate.vast.ai"

    def test_instance_unknown_string_falls_back_to_default_urls(self) -> None:
        """
        Verifies that an unrecognized instance value uses the default (prod-like) URL pair.

        This test verifies by:
        1. Creating Serverless with a non-matching instance string
        2. Asserting URLs match the default branch (same as prod)

        Assumptions:
        - Default branch is the final case in the instance match
        """
        client = Serverless(api_key="k", instance="unknown-env")
        assert client.autoscaler_url == "https://run.vast.ai"
        assert client.vast_web_url == "https://console.vast.ai"

    def test_debug_true_attaches_stream_handler_and_disables_propagation(self) -> None:
        """
        Verifies that debug=True configures the class logger for debug output.

        This test verifies by:
        1. Constructing Serverless(api_key=..., debug=True)
        2. Asserting debug flag, DEBUG level, and propagate is False (per implementation)

        Assumptions:
        - Debug mode adds a StreamHandler and avoids duplicate root logging

        Logger teardown is handled by the autouse ``_restore_serverless_logger_state``
        fixture in ``tests/conftest.py`` (RAII).
        """
        client = Serverless(api_key="k", debug=True)
        assert client.debug is True
        assert client.logger.level == logging.DEBUG
        assert client.logger.propagate is False
        assert any(
            isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.NullHandler)
            for h in client.logger.handlers
        )

    def test_debug_false_leaves_logger_propagate_true(self) -> None:
        """Non-debug mode keeps propagate True so app logging config applies."""
        client = Serverless(api_key="k", debug=False)
        assert client.debug is False
        assert client.logger.propagate is True

    def test_uses_vast_api_key_from_environment_when_not_passed(self) -> None:
        """Omitting api_key uses VAST_API_KEY (read when ``client`` module is imported).

        The default ``api_key=os.environ.get(...)`` is bound at class definition time in
        CPython, so a fresh interpreter is needed to observe env changes.
        """
        code = (
            "import os, sys\n"
            f"sys.path.insert(0, {_REPO_ROOT!r})\n"
            "os.environ['VAST_API_KEY'] = 'key-from-env-xyz'\n"
            "from vastai.serverless.client.client import Serverless\n"
            "c = Serverless()\n"
            "assert c.api_key == 'key-from-env-xyz', c.api_key\n"
        )
        subprocess.run([sys.executable, "-c", code], check=True)

    def test_constructor_stores_connection_limit_and_timeouts(self) -> None:
        """connection_limit, default_request_timeout, and max_poll_interval are kept on the client."""
        client = Serverless(
            api_key="k",
            connection_limit=321,
            default_request_timeout=999.5,
            max_poll_interval=3.25,
        )
        assert client.connection_limit == 321
        assert client.default_request_timeout == 999.5
        assert client.max_poll_interval == 3.25

    def test_skips_null_handler_when_serverless_logger_already_configured(self) -> None:
        """If the class logger already has handlers, __init__ does not add NullHandler."""
        log = logging.getLogger("Serverless")
        existing = logging.StreamHandler()
        log.addHandler(existing)
        try:
            client = Serverless(api_key="k", debug=False)
            assert existing in client.logger.handlers
            assert not any(
                isinstance(h, logging.NullHandler) for h in client.logger.handlers
            )
        finally:
            log.removeHandler(existing)


# ---------------------------------------------------------------------------
# Session lifecycle helpers
# ---------------------------------------------------------------------------


class TestServerlessSessionOpen:
    """Verify is_open, context manager, and close behavior with mocked aiohttp session."""

    @pytest.mark.asyncio
    async def test_is_open_true_when_session_exists_and_not_closed(
        self, client
    ) -> None:
        """is_open() is True when _session is set and aiohttp session is open."""
        mock_sess = MagicMock()
        mock_sess.closed = False
        client._session = mock_sess
        assert client.is_open() is True

    @pytest.mark.asyncio
    async def test_is_open_false_before_session_created(self, client) -> None:
        """
        Verifies is_open() is False until _get_session has created a session.

        This test verifies by:
        1. Constructing Serverless without opening a session
        2. Calling is_open() and asserting False

        Assumptions:
        - _session starts as None
        """
        assert client.is_open() is False

    @pytest.mark.asyncio
    async def test_context_manager_closes_session(self, client) -> None:
        """
        Verifies __aexit__ closes the aiohttp session opened in __aenter__.

        This test verifies by:
        1. Patching ClientSession and get_ssl_context so _get_session succeeds
        2. Using async with Serverless()
        3. Asserting session.close was awaited after the block

        Assumptions:
        - ClientSession is constructed via vastai.serverless.client.client.aiohttp.ClientSession
        """
        mock_sess = MagicMock()
        mock_sess.closed = False
        mock_sess.close = AsyncMock()

        with (
            patch(
                "vastai.serverless.client.client.aiohttp.ClientSession",
                return_value=mock_sess,
            ),
            patch.object(
                Serverless,
                "get_ssl_context",
                new=AsyncMock(return_value=None),
            ),
        ):
            async with client:
                assert client._session is mock_sess
            mock_sess.close.assert_awaited()

    @pytest.mark.asyncio
    async def test_close_is_idempotent_when_no_session(self, client) -> None:
        """
        Verifies close() does not raise when there is no active session.

        This test verifies by:
        1. Creating Serverless and calling await close() without _get_session

        Assumptions:
        - close() guards on self._session truthiness
        """
        await client.close()

    @pytest.mark.asyncio
    async def test_get_session_recreates_when_previous_session_marked_closed(
        self, client
    ) -> None:
        """
        Verifies _get_session builds a new ClientSession when the existing one is closed.

        This test verifies by:
        1. Patching ClientSession to return distinct mock sessions per construction
        2. Opening a session, marking it closed, calling _get_session again
        3. Asserting a second ClientSession was constructed

        Assumptions:
        - Branch ``self._session is None or self._session.closed`` triggers recreation
        """
        instances: list[MagicMock] = []

        def _new_session(*_a, **_kw) -> MagicMock:
            m = MagicMock()
            m.closed = False
            m.close = AsyncMock()
            instances.append(m)
            return m

        with (
            patch(
                "vastai.serverless.client.client.aiohttp.ClientSession",
                side_effect=_new_session,
            ),
            patch.object(
                Serverless,
                "get_ssl_context",
                new=AsyncMock(return_value=None),
            ),
        ):
            first = await client._get_session()
            first.closed = True
            second = await client._get_session()

        assert len(instances) == 2
        assert second is instances[1]
        assert client._session is second

    @pytest.mark.asyncio
    async def test_close_awaits_session_close_when_session_open(self, client) -> None:
        """
        Verifies close() awaits session.close when the session exists and is open.

        This test verifies by:
        1. Assigning a mock session with closed=False and AsyncMock close()
        2. Awaiting client.close()
        3. Asserting close was awaited on the session

        Assumptions:
        - close() only runs when self._session is truthy and not closed
        """
        mock_sess = MagicMock()
        mock_sess.closed = False
        mock_sess.close = AsyncMock()
        client._session = mock_sess
        await client.close()
        mock_sess.close.assert_awaited()

    @pytest.mark.asyncio
    async def test_get_session_passes_connection_limit_to_tcp_connector(self) -> None:
        """_get_session builds TCPConnector with limit=connection_limit."""
        limits: list[int] = []
        mock_connector = MagicMock()

        def _tcp_side_effect(*_a, **kw) -> MagicMock:
            limits.append(kw["limit"])
            return mock_connector

        mock_sess = MagicMock()
        mock_sess.closed = False
        mock_sess.close = AsyncMock()

        tuned = Serverless(api_key="k", connection_limit=88)
        with (
            patch(
                "vastai.serverless.client.client.aiohttp.TCPConnector",
                side_effect=_tcp_side_effect,
            ),
            patch(
                "vastai.serverless.client.client.aiohttp.ClientSession",
                return_value=mock_sess,
            ),
            patch.object(
                Serverless,
                "get_ssl_context",
                new=AsyncMock(return_value=None),
            ),
        ):
            await tuned._get_session()

        assert limits == [88]

    @pytest.mark.asyncio
    async def test_get_session_returns_same_open_session_without_recreating(
        self, client
    ) -> None:
        """Second _get_session call reuses ClientSession when the first is still open."""
        mock_sess = MagicMock()
        mock_sess.closed = False
        mock_sess.close = AsyncMock()

        with (
            patch(
                "vastai.serverless.client.client.aiohttp.ClientSession",
                return_value=mock_sess,
            ) as client_session_ctor,
            patch.object(
                Serverless,
                "get_ssl_context",
                new=AsyncMock(return_value=None),
            ),
        ):
            first = await client._get_session()
            second = await client._get_session()

        assert first is second is mock_sess
        assert client_session_ctor.call_count == 1

    @pytest.mark.asyncio
    async def test_is_open_false_when_session_marked_closed(self, client) -> None:
        """is_open() is False when _session exists but aiohttp reports closed."""
        mock_sess = MagicMock()
        mock_sess.closed = True
        client._session = mock_sess
        assert client.is_open() is False


# ---------------------------------------------------------------------------
# get_ssl_context
# ---------------------------------------------------------------------------


class TestServerlessGetSslContext:
    """Verify SSL context loading uses mocked cert download and ssl APIs."""

    @pytest.mark.asyncio
    async def test_get_ssl_context_fetches_cert_and_caches_context(
        self, client
    ) -> None:
        """
        Verifies get_ssl_context downloads PEM bytes, loads them, and caches SSLContext.

        This test verifies by:
        1. Patching aiohttp.ClientSession and nested get() response with status 200 and read()
        2. Patching ssl.create_default_context to return a mock context
        3. Calling get_ssl_context twice and asserting create_default_context once
        4. Asserting load_verify_locations was called with a .cer temp path

        Assumptions:
        - Second call returns cached _ssl_context without another HTTP fetch
        """
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read = AsyncMock(
            return_value=b"-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----"
        )

        mock_get_cm = MagicMock()
        mock_get_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_get_cm.__aexit__ = AsyncMock(return_value=None)

        mock_sess_inst = MagicMock()
        mock_sess_inst.get = MagicMock(return_value=mock_get_cm)
        mock_sess_inst.__aenter__ = AsyncMock(return_value=mock_sess_inst)
        mock_sess_inst.__aexit__ = AsyncMock(return_value=None)

        mock_ctx = MagicMock()

        with (
            patch(
                "vastai.serverless.client.client.aiohttp.ClientSession",
                return_value=mock_sess_inst,
            ),
            patch(
                "vastai.serverless.client.client.ssl.create_default_context",
                return_value=mock_ctx,
            ),
            patch("vastai.serverless.client.client.os.unlink") as mock_unlink,
        ):
            ctx1 = await client.get_ssl_context()
            ctx2 = await client.get_ssl_context()

        assert ctx1 is mock_ctx is ctx2
        mock_ctx.load_verify_locations.assert_called_once()
        cafile = mock_ctx.load_verify_locations.call_args.kwargs.get("cafile")
        assert cafile.endswith(".cer")
        # Only one unlink is from our client (the .cer temp). Some Python/ssl builds
        # also unlink other temps during load_verify_locations — do not require exactly
        # one os.unlink call on the mock.
        unlink_targets = [c.args[0] for c in mock_unlink.call_args_list if c.args]
        assert cafile in unlink_targets

    @pytest.mark.asyncio
    async def test_get_ssl_context_raises_when_cert_fetch_status_not_200(
        self, client
    ) -> None:
        """
        Verifies get_ssl_context raises when the certificate HTTP response is not 200.

        This test verifies by:
        1. Mocking the cert GET response with a non-200 status
        2. Awaiting get_ssl_context and asserting an exception mentions the status

        Assumptions:
        - Non-200 responses do not write temp files or cache SSL context
        """
        mock_resp = MagicMock()
        mock_resp.status = 503

        mock_get_cm = MagicMock()
        mock_get_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_get_cm.__aexit__ = AsyncMock(return_value=None)

        mock_sess_inst = MagicMock()
        mock_sess_inst.get = MagicMock(return_value=mock_get_cm)
        mock_sess_inst.__aenter__ = AsyncMock(return_value=mock_sess_inst)
        mock_sess_inst.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "vastai.serverless.client.client.aiohttp.ClientSession",
            return_value=mock_sess_inst,
        ):
            with pytest.raises(Exception, match="Failed to fetch SSL cert: 503"):
                await client.get_ssl_context()


# ---------------------------------------------------------------------------
# get_endpoints / get_endpoint
# ---------------------------------------------------------------------------


class TestServerlessGetEndpoints:
    """Verify endpoint listing and lookup delegate to _make_request with correct args."""

    @pytest.mark.asyncio
    async def test_get_endpoints_parses_results_into_endpoint_objects(
        self, serverless_master_client
    ) -> None:
        """
        Verifies get_endpoints maps API results to Endpoint instances with correct fields.

        This test verifies by:
        1. Patching vastai.serverless.client.client._make_request (AsyncMock) to return ok+json
        2. Awaiting get_endpoints and asserting length, names, ids, api_keys

        Assumptions:
        - _make_request is imported into client module (patch target is client._make_request)
        """
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
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
            endpoints = await serverless_master_client.get_endpoints()

        assert len(endpoints) == 2
        assert endpoints[0].name == "a" and endpoints[0].id == 1
        assert endpoints[0].api_key == "ek1"
        mock_req.assert_awaited()
        call_kw = mock_req.call_args.kwargs
        assert call_kw["url"] == serverless_master_client.vast_web_url
        assert call_kw["route"] == "/api/v0/endptjobs/"
        assert call_kw["api_key"] == "master"
        assert call_kw["params"] == {"client_id": "me"}

    @pytest.mark.asyncio
    async def test_get_endpoints_wraps_make_request_exception(self, client) -> None:
        """
        Verifies get_endpoints raises Exception with context when _make_request fails.

        This test verifies by:
        1. Making _make_request raise ValueError
        2. Awaiting get_endpoints and asserting raised Exception mentions Failed to get endpoints

        Assumptions:
        - Client wraps underlying errors in a single message prefix
        """
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            side_effect=ValueError("network"),
        ):
            with pytest.raises(Exception, match="Failed to get endpoints"):
                await client.get_endpoints()

    @pytest.mark.asyncio
    async def test_get_endpoints_returns_empty_list_when_no_results(
        self, client
    ) -> None:
        """ok=True with empty results yields an empty Endpoint list."""
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            return_value={"ok": True, "json": {"results": []}},
        ):
            endpoints = await client.get_endpoints()
        assert endpoints == []

    @pytest.mark.asyncio
    async def test_get_endpoints_raises_when_http_result_not_ok(self, client) -> None:
        """
        Verifies get_endpoints raises when the request dict has ok=False.

        This test verifies by:
        1. Returning ok=False with status and text from the mock
        2. Asserting Exception mentions HTTP status

        Assumptions:
        - Non-ok results are surfaced without parsing results
        """
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            return_value={"ok": False, "status": 503, "text": "unavailable"},
        ):
            with pytest.raises(Exception, match="HTTP 503"):
                await client.get_endpoints()

    @pytest.mark.asyncio
    async def test_get_endpoint_returns_matching_endpoint_by_name(self, client) -> None:
        """
        Verifies get_endpoint returns the Endpoint whose name matches the argument.

        This test verifies by:
        1. Patching get_endpoints on the instance to return predefined endpoints
        2. Awaiting get_endpoint('two') and asserting the correct object is returned

        Assumptions:
        - Lookup is linear scan over get_endpoints() results
        """
        e1 = Endpoint(client, "one", 1, "k1")
        e2 = Endpoint(client, "two", 2, "k2")
        with patch.object(
            client, "get_endpoints", new_callable=AsyncMock, return_value=[e1, e2]
        ):
            found = await client.get_endpoint("two")
        assert found is e2

    @pytest.mark.asyncio
    async def test_get_endpoint_raises_when_name_not_found(self, client) -> None:
        """
        Verifies get_endpoint raises when no endpoint matches the given name.

        This test verifies by:
        1. Patching get_endpoints to return an empty list
        2. Asserting Exception mentions the endpoint name

        Assumptions:
        - Missing name produces a clear error string
        """
        with patch.object(
            client, "get_endpoints", new_callable=AsyncMock, return_value=[]
        ):
            with pytest.raises(Exception, match="could not be found"):
                await client.get_endpoint("missing")


# ---------------------------------------------------------------------------
# get_endpoint_workers
# ---------------------------------------------------------------------------


class TestServerlessGetEndpointWorkers:
    """Verify worker listing via autoscaler POST and response edge cases."""

    @pytest.mark.asyncio
    async def test_get_endpoint_workers_requires_endpoint_type(
        self, client_with_session
    ) -> None:
        """
        Verifies get_endpoint_workers raises ValueError for non-Endpoint argument.

        This test verifies by:
        1. Passing a MagicMock instead of Endpoint
        2. Asserting ValueError with message about Endpoint

        Assumptions:
        - isinstance(endpoint, Endpoint) guard is enforced
        """
        client = client_with_session
        with pytest.raises(ValueError, match="endpoint must be an Endpoint"):
            await client.get_endpoint_workers(MagicMock())

    @pytest.mark.asyncio
    async def test_get_endpoint_workers_returns_worker_list(
        self, serverless_master_client, make_mock_http_response
    ) -> None:
        """
        Verifies JSON list responses are converted to Worker dataclass instances.

        This test verifies by:
        1. Mocking _session.post async context with status 200 and json list
        2. Awaiting get_endpoint_workers with a real Endpoint
        3. Asserting Worker id and status

        Assumptions:
        - POST URL is autoscaler_url + get_endpoint_workers/
        """
        payload_item = {"id": 7, "status": "READY"}
        mock_resp = make_mock_http_response(
            status=200,
            json_data=[payload_item],
            text="",
        )

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)

        client = serverless_master_client
        client._session = mock_session
        ep = Endpoint(client, "ep", 99, "ek")

        workers = await client.get_endpoint_workers(ep)

        assert len(workers) == 1
        assert workers[0].id == 7
        assert workers[0].status == "READY"
        mock_session.post.assert_called_once()
        url = mock_session.post.call_args[0][0]
        assert url.endswith("/get_endpoint_workers/")
        assert mock_session.post.call_args.kwargs["json"] == {
            "id": 99,
            "api_key": "master",
        }

    @pytest.mark.asyncio
    async def test_get_endpoint_workers_returns_empty_list_on_error_msg(
        self, client_with_session, make_serverless_endpoint, make_mock_http_response
    ) -> None:
        """
        Verifies dict responses containing error_msg yield an empty worker list.

        This test verifies by:
        1. Returning JSON dict with error_msg key from the mock response
        2. Asserting the result is []

        Assumptions:
        - Server may return error_msg when workers are not ready; client soft-fails
        """
        mock_resp = make_mock_http_response(
            status=200,
            json_data={"error_msg": "not ready"},
        )

        client = client_with_session
        client._session.post = MagicMock(return_value=mock_resp)
        ep = make_serverless_endpoint(client, name="ep", endpoint_id=1, api_key="ek")

        workers = await client.get_endpoint_workers(ep)
        assert workers == []

    @pytest.mark.asyncio
    async def test_get_endpoint_workers_raises_on_non_200(
        self, client_with_session, make_serverless_endpoint, make_mock_http_response
    ) -> None:
        """
        Verifies non-200 HTTP status raises RuntimeError with body text.

        This test verifies by:
        1. Setting resp.status to 502 and text() to a message
        2. Asserting RuntimeError mentions HTTP 502

        Assumptions:
        - resp.text is awaited for error diagnostics
        """
        mock_resp = make_mock_http_response(status=502, text="bad gateway")

        client = client_with_session
        client._session.post = MagicMock(return_value=mock_resp)
        ep = make_serverless_endpoint(client, name="ep", endpoint_id=1, api_key="ek")

        with pytest.raises(RuntimeError, match="HTTP 502"):
            await client.get_endpoint_workers(ep)

    @pytest.mark.asyncio
    async def test_get_endpoint_workers_raises_on_unexpected_json_type(
        self, client_with_session, make_serverless_endpoint, make_mock_http_response
    ) -> None:
        """
        Verifies non-list JSON (without error_msg) raises RuntimeError.

        This test verifies by:
        1. Returning JSON string or other non-list type
        2. Asserting RuntimeError mentions Unexpected response type

        Assumptions:
        - Successful worker list must be a JSON array
        """
        mock_resp = make_mock_http_response(status=200, json_data="not-a-list")

        client = client_with_session
        client._session.post = MagicMock(return_value=mock_resp)
        ep = make_serverless_endpoint(client, name="ep", endpoint_id=1, api_key="ek")

        with pytest.raises(RuntimeError, match="Unexpected response type"):
            await client.get_endpoint_workers(ep)

    @pytest.mark.asyncio
    async def test_get_endpoint_workers_raises_on_dict_without_error_msg(
        self, client_with_session, make_serverless_endpoint, make_mock_http_response
    ) -> None:
        """JSON object without error_msg is not a worker list; client raises RuntimeError."""
        mock_resp = make_mock_http_response(status=200, json_data={"status": "ok"})

        client = client_with_session
        client._session.post = MagicMock(return_value=mock_resp)
        ep = make_serverless_endpoint(client, name="ep", endpoint_id=1, api_key="ek")

        with pytest.raises(RuntimeError, match="wanted list"):
            await client.get_endpoint_workers(ep)


# ---------------------------------------------------------------------------
# Session get / end
# ---------------------------------------------------------------------------


class TestServerlessEndpointSessionHttp:
    """Verify get_endpoint_session and end_endpoint_session use _make_request."""

    @pytest.mark.asyncio
    async def test_get_endpoint_session_builds_session_from_json(
        self, client, make_serverless_endpoint
    ) -> None:
        """
        Verifies get_endpoint_session constructs Session from auth_data and metadata.

        This test verifies by:
        1. Mocking _make_request to return ok with json containing auth_data and url
        2. Awaiting get_endpoint_session and asserting Session fields

        Assumptions:
        - session_auth dict includes url key used as request base
        """
        ep = make_serverless_endpoint(client, name="n", endpoint_id=1, api_key="ek")
        session_auth = {"url": "https://worker.example/session"}
        worker_json = {
            "auth_data": {"token": "t", "url": "https://worker.example/w"},
            "lifetime": 60.0,
            "expiration": "later",
        }
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            return_value={"ok": True, "json": worker_json},
        ) as mock_req:
            sess = await client.get_endpoint_session(ep, 42, session_auth, timeout=5.0)

        assert isinstance(sess, Session)
        assert sess.session_id == 42
        assert sess.auth_data == worker_json["auth_data"]
        assert sess.url == "https://worker.example/w"
        mock_req.assert_awaited()
        assert mock_req.call_args.kwargs["url"] == session_auth["url"]
        assert mock_req.call_args.kwargs["route"] == "/session/get"
        assert mock_req.call_args.kwargs["body"]["session_id"] == 42

    @pytest.mark.asyncio
    async def test_get_endpoint_session_raises_without_auth_data(
        self, client, make_serverless_endpoint
    ) -> None:
        """
        Verifies missing auth_data in JSON raises Exception.

        This test verifies by:
        1. Returning ok json without auth_data key
        2. Asserting Exception is raised

        Assumptions:
        - auth_data is required to build Session
        """
        ep = make_serverless_endpoint(client, name="n", endpoint_id=1, api_key="ek")
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            return_value={"ok": True, "json": {"lifetime": 1}},
        ):
            with pytest.raises(Exception, match="Missing auth_data"):
                await client.get_endpoint_session(ep, 1, {"url": "https://x"})

    @pytest.mark.asyncio
    async def test_end_endpoint_session_raises_when_not_ok(
        self, client, make_session_mock
    ) -> None:
        """
        Verifies end_endpoint_session raises when _make_request returns ok=False.

        This test verifies by:
        1. Mocking _make_request with ok False and json error
        2. Passing a minimal Session mock with required attributes
        3. Asserting Exception mentions /session/end

        Assumptions:
        - Session.url and session.auth_data are read for the request body
        """
        mock_session = make_session_mock(
            session_id=9, url="https://worker/u", auth_data={"a": 1}
        )

        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            return_value={"ok": False, "json": {"error": "gone"}},
        ):
            with pytest.raises(Exception, match="/session/end"):
                await client.end_endpoint_session(mock_session)

    @pytest.mark.asyncio
    async def test_get_endpoint_session_raises_when_http_result_not_ok(
        self, client, make_serverless_endpoint
    ) -> None:
        """
        Verifies get_endpoint_session raises when _make_request returns ok=False.

        This test verifies by:
        1. Returning a failed result with json error detail
        2. Asserting the raised Exception mentions /session/get

        Assumptions:
        - Error message prefers json['error'] when present
        """
        ep = make_serverless_endpoint(client, name="n", endpoint_id=1, api_key="ek")
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            return_value={"ok": False, "json": {"error": "nope"}},
        ):
            with pytest.raises(Exception, match="/session/get"):
                await client.get_endpoint_session(ep, 1, {"url": "https://x"})

    @pytest.mark.asyncio
    async def test_get_endpoint_session_propagates_timeout_error(
        self, client, make_serverless_endpoint
    ) -> None:
        """
        Verifies asyncio.TimeoutError from _make_request is not wrapped by the outer handler.

        This test verifies by:
        1. Making _make_request raise asyncio.TimeoutError
        2. Awaiting get_endpoint_session and expecting the same exception type

        Assumptions:
        - TimeoutError is listed before the broad Exception handler in the implementation
        """
        ep = make_serverless_endpoint(client, name="n", endpoint_id=1, api_key="ek")
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            side_effect=asyncio.TimeoutError,
        ):
            with pytest.raises(asyncio.TimeoutError):
                await client.get_endpoint_session(ep, 1, {"url": "https://x"})

    @pytest.mark.asyncio
    async def test_get_endpoint_session_wraps_unexpected_errors(
        self, client, make_serverless_endpoint
    ) -> None:
        """
        Verifies non-timeout errors from _make_request are wrapped with session context.

        This test verifies by:
        1. Making _make_request raise OSError
        2. Asserting raised Exception message includes session id and Failed to get session

        Assumptions:
        - Outer except Exception path logs and re-raises a new Exception
        """
        ep = make_serverless_endpoint(client, name="n", endpoint_id=1, api_key="ek")
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            side_effect=OSError("disk"),
        ):
            with pytest.raises(Exception, match="Failed to get session 5"):
                await client.get_endpoint_session(ep, 5, {"url": "https://x"})

    @pytest.mark.asyncio
    async def test_end_endpoint_session_succeeds_when_ok_true(
        self, client, make_session_mock
    ) -> None:
        """
        Verifies end_endpoint_session returns None when _make_request reports success.

        This test verifies by:
        1. Mocking _make_request to return ok=True
        2. Awaiting end_endpoint_session and asserting no exception

        Assumptions:
        - Successful end is a fire-and-forget style API (implicit None return)
        """
        mock_session = make_session_mock(auth_data={"a": 1})
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            return_value={"ok": True, "json": {}},
        ):
            await client.end_endpoint_session(mock_session)

    @pytest.mark.asyncio
    async def test_end_endpoint_session_wraps_generic_errors(
        self, client, make_session_mock
    ) -> None:
        """Non-timeout failures from _make_request are wrapped with session context."""
        mock_session = make_session_mock(session_id=3, auth_data={})
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            side_effect=OSError("down"),
        ):
            with pytest.raises(Exception, match="Failed to end session 3"):
                await client.end_endpoint_session(mock_session)

    @pytest.mark.asyncio
    async def test_end_endpoint_session_propagates_timeout_error(
        self, client, make_session_mock
    ) -> None:
        """
        Verifies asyncio.TimeoutError from end_endpoint_session is not wrapped.

        This test verifies by:
        1. Making _make_request raise asyncio.TimeoutError
        2. Asserting asyncio.TimeoutError propagates

        Assumptions:
        - Same TimeoutError ordering as get_endpoint_session
        """
        mock_session = make_session_mock(auth_data={})
        with patch(
            "vastai.serverless.client.client._make_request",
            new_callable=AsyncMock,
            side_effect=asyncio.TimeoutError,
        ):
            with pytest.raises(asyncio.TimeoutError):
                await client.end_endpoint_session(mock_session)


# ---------------------------------------------------------------------------
# start_endpoint_session
# ---------------------------------------------------------------------------


class TestServerlessStartEndpointSession:
    """Verify start_endpoint_session awaits queue_endpoint_request result shape."""

    @pytest.mark.asyncio
    async def test_start_endpoint_session_returns_session_on_success(
        self,
        client,
        default_start_endpoint_session_ep,
        make_completed_serverless_request,
    ) -> None:
        """
        Verifies start_endpoint_session returns Session when queue result is well-formed.

        This test verifies by:
        1. Patching queue_endpoint_request to return an already-resolved ServerlessRequest
        2. Awaiting start_endpoint_session and asserting Session session_id and url

        Assumptions:
        - queue_endpoint_request is awaited inside start_endpoint_session
        """
        ep = default_start_endpoint_session_ep
        done = make_completed_serverless_request(
            result={
                "ok": True,
                "response": {"session_id": 100, "expiration": "e"},
                "url": "https://w/u",
                "auth_data": {"x": 1},
            }
        )

        with patch.object(client, "queue_endpoint_request", return_value=done):
            sess = await client.start_endpoint_session(ep, cost=50, lifetime=30.0)

        assert isinstance(sess, Session)
        assert sess.session_id == 100
        assert sess.url == "https://w/u"
        assert sess.lifetime == 30.0

    @pytest.mark.asyncio
    async def test_start_endpoint_session_raises_when_queue_reports_not_ok(
        self,
        client,
        default_start_endpoint_session_ep,
        make_completed_serverless_request,
    ) -> None:
        """
        Verifies start_endpoint_session raises when the queued worker result has ok=False.

        This test verifies by:
        1. Resolving the queue future with ok=False and json error
        2. Asserting Exception mentions /session/create

        Assumptions:
        - queue_endpoint_request result dict uses the same ok/json shape as HTTP helpers
        """
        ep = default_start_endpoint_session_ep
        done = make_completed_serverless_request(
            result={"ok": False, "json": {"error": "busy"}, "text": ""}
        )
        with patch.object(client, "queue_endpoint_request", return_value=done):
            with pytest.raises(Exception, match="/session/create"):
                await client.start_endpoint_session(ep)

    @pytest.mark.asyncio
    async def test_start_endpoint_session_raises_when_session_id_missing(
        self,
        client,
        default_start_endpoint_session_ep,
        make_completed_serverless_request,
    ) -> None:
        """
        Verifies start_endpoint_session raises when response JSON omits session_id.

        This test verifies by:
        1. Returning ok=True with a response dict without session_id
        2. Asserting Exception mentions Missing session id

        Assumptions:
        - session_id is required to construct Session
        """
        ep = default_start_endpoint_session_ep
        done = make_completed_serverless_request(
            result={
                "ok": True,
                "response": {"expiration": "e"},
                "url": "https://w/",
                "auth_data": {"x": 1},
            }
        )
        with patch.object(client, "queue_endpoint_request", return_value=done):
            with pytest.raises(Exception, match="Missing session id"):
                await client.start_endpoint_session(ep)

    @pytest.mark.asyncio
    async def test_start_endpoint_session_raises_when_url_missing(
        self,
        client,
        default_start_endpoint_session_ep,
        make_completed_serverless_request,
    ) -> None:
        """
        Verifies start_endpoint_session raises when the queue result omits url.

        This test verifies by:
        1. Returning ok=True with session_id but url None / missing
        2. Asserting Exception mentions Missing URL

        Assumptions:
        - url is required for subsequent session calls
        """
        ep = default_start_endpoint_session_ep
        done = make_completed_serverless_request(
            result={
                "ok": True,
                "response": {"session_id": 1, "expiration": "e"},
                "url": None,
                "auth_data": {"x": 1},
            }
        )
        with patch.object(client, "queue_endpoint_request", return_value=done):
            with pytest.raises(Exception, match="Missing URL"):
                await client.start_endpoint_session(ep)

    @pytest.mark.asyncio
    async def test_start_endpoint_session_raises_when_auth_data_missing(
        self,
        client,
        default_start_endpoint_session_ep,
        make_completed_serverless_request,
    ) -> None:
        """
        Verifies start_endpoint_session raises when auth_data is absent from the queue result.

        This test verifies by:
        1. Returning ok=True with valid response and url but auth_data None
        2. Asserting Exception mentions Missing auth data

        Assumptions:
        - auth_data is required to build Session
        """
        ep = default_start_endpoint_session_ep
        done = make_completed_serverless_request(
            result={
                "ok": True,
                "response": {"session_id": 1, "expiration": "e"},
                "url": "https://w/",
                "auth_data": None,
            }
        )
        with patch.object(client, "queue_endpoint_request", return_value=done):
            with pytest.raises(Exception, match="Missing auth data"):
                await client.start_endpoint_session(ep)

    @pytest.mark.asyncio
    async def test_start_endpoint_session_raises_when_response_none(
        self,
        client,
        default_start_endpoint_session_ep,
        make_completed_serverless_request,
    ) -> None:
        """
        Verifies ok=True but ``response`` is None raises
        """
        ep = default_start_endpoint_session_ep
        done = make_completed_serverless_request(
            result={
                "ok": True,
                "response": None,
                "url": "https://w/",
                "auth_data": {"x": 1},
            }
        )
        with patch.object(client, "queue_endpoint_request", return_value=done):
            with pytest.raises(Exception, match="No response from /session/create"):
                await client.start_endpoint_session(ep)

    @pytest.mark.asyncio
    async def test_start_endpoint_session_wraps_generic_queue_errors(
        self,
        client,
        default_start_endpoint_session_ep,
        make_completed_serverless_request,
    ) -> None:
        """Errors other than TimeoutError from the queue future are wrapped."""
        ep = default_start_endpoint_session_ep
        done = make_completed_serverless_request(exception=ValueError("queue broke"))
        with patch.object(client, "queue_endpoint_request", return_value=done):
            with pytest.raises(Exception, match="Failed to create session"):
                await client.start_endpoint_session(ep)

    @pytest.mark.asyncio
    async def test_start_endpoint_session_propagates_timeout_error(
        self,
        client,
        default_start_endpoint_session_ep,
        make_completed_serverless_request,
    ) -> None:
        """
        Verifies asyncio.TimeoutError from queue_endpoint_request is re-raised.

        This test verifies by:
        1. Patching queue_endpoint_request to return a future completed with TimeoutError via set_exception

        Assumptions:
        - Awaiting the ServerlessRequest propagates set_exception payloads
        """
        ep = default_start_endpoint_session_ep
        done = make_completed_serverless_request(exception=asyncio.TimeoutError())
        with patch.object(client, "queue_endpoint_request", return_value=done):
            with pytest.raises(asyncio.TimeoutError):
                await client.start_endpoint_session(ep)


# ---------------------------------------------------------------------------
# queue_endpoint_request
# ---------------------------------------------------------------------------


class TestServerlessQueueEndpointRequest:
    """Verify routing poll loop and worker _make_request success path (mocked, no real sleep)."""

    @pytest.mark.asyncio
    async def test_queue_endpoint_request_completes_after_route_ready_and_worker_ok(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies queue_endpoint_request resolves with worker JSON when route then worker succeed.

        This test verifies by:
        1. Patching endpoint._route to return WAITING then READY with url and body
        2. Patching client._make_request to return ok with json
        3. Patching asyncio.sleep and random.uniform to avoid delays
        4. Awaiting the returned ServerlessRequest and asserting response payload and ok

        Assumptions:
        - Endpoint._route is replaced with a fake that simulates WAITING then READY
        - Worker call uses vastai.serverless.client.client._make_request
        """
        ep = make_serverless_endpoint(client_with_session)
        client = client_with_session

        waiting = make_route_response_mock(request_idx=7)
        ready = make_route_response_mock(
            status="READY",
            url="https://worker/",
            request_idx=7,
            body={"token": "t"},
        )

        route_seq = iter([waiting, ready])

        async def fake_route(*_a, **_kw):
            return next(route_seq)

        worker_json = {"result": 42}

        with (
            patch.object(Endpoint, "_route", side_effect=fake_route),
            patch(
                "vastai.serverless.client.client._make_request",
                new_callable=AsyncMock,
                return_value={"ok": True, "json": worker_json},
            ),
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/do",
                worker_payload={"x": 1},
                cost=10,
            )
            result = await fut

        assert result["ok"] is True
        assert result["response"] == worker_json
        assert result["url"] == "https://worker/"


class TestServerlessQueueEndpointRequestBranches:
    """Additional queue_endpoint_request paths (timeouts, retries, session, cancel, stream)."""

    @pytest.mark.asyncio
    async def test_queue_times_out_before_route_when_timeout_zero(
        self, monkeypatch, client_with_session, make_serverless_endpoint
    ) -> None:
        """
        Verifies the outer loop raises TimeoutError when elapsed time exceeds timeout.

        This test verifies by:
        1. Patching client module time.time so the timeout check sees elapsed >= 0 immediately
        2. Using timeout=0 and awaiting the ServerlessRequest
        3. Asserting asyncio.TimeoutError is delivered to the awaiter

        Assumptions:
        - TimeoutError is stored on the future via the task's outer Exception handler

        Note:
        Use pytest ``monkeypatch`` (not ``unittest.mock.patch``) for ``time.time`` so the
        mock is always undone after the test. A stuck ``return_value=100.0`` patch would
        leave ``start_time`` and later ``time()`` identical in the next test's polling
        loop, causing an infinite spin and a hung suite (often seen as Cursor/IDE freeze).
        """
        client = client_with_session
        ep = make_serverless_endpoint(client, name="ep", endpoint_id=1, api_key="ek")

        # Patch the same ``time`` module object ``client.py`` imports (not a string path:
        # ``pytest`` may resolve ``...client.time`` incorrectly).
        monkeypatch.setattr(serverless_client_mod.time, "time", lambda: 100.0)
        fut = client.queue_endpoint_request(
            endpoint=ep,
            worker_route="/r",
            worker_payload={},
            timeout=0.0,
        )
        with pytest.raises(asyncio.TimeoutError):
            await fut

    @pytest.mark.asyncio
    async def test_queue_times_out_while_polling_route_status(
        self,
        monkeypatch,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
    ) -> None:
        """
        Verifies TimeoutError when the route stays non-READY until the deadline.

        This test verifies by:
        1. Returning a perpetual WAITING route from _route
        2. Patching time.time so the first *inner* poll iteration sees elapsed time past timeout
           (accounting for create_time + start_time + outer deadline calls)
        3. Asserting asyncio.TimeoutError with the poll-loop message

        Assumptions:
        - Polling loop checks the same elapsed timeout as the top of the outer loop
        - time.time() may be invoked more than once per iteration; the fake must stay stable

        ``logging`` calls ``time.time()`` for every ``LogRecord``. If any handler is left on
        the ``Serverless`` logger (e.g. from a prior test), extra calls desynchronize this
        fake and the client spins in the poll loop forever (100% CPU — feels like a freeze).
        """
        client = client_with_session
        monkeypatch.setattr(client.logger, "disabled", True)
        ep = make_serverless_endpoint(client)

        waiting = make_route_response_mock()

        calls = {"n": 0}

        def _fake_time() -> float:
            calls["n"] += 1
            # ServerlessRequest.__init__ calls time.time() for create_time before the task body.
            # Then: start_time, outer deadline (line ~357), then inner poll deadline (~381).
            if calls["n"] <= 3:
                return 0.0
            return 100.0

        async def always_waiting(*_a, **_kw):
            return waiting

        monkeypatch.setattr(serverless_client_mod.time, "time", _fake_time)

        with (
            patch.object(Endpoint, "_route", side_effect=always_waiting),
            patch(
                "vastai.serverless.client.client.asyncio.sleep", new_callable=AsyncMock
            ),
            patch("vastai.serverless.client.client.random.uniform", return_value=0.1),
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/do",
                worker_payload={},
                timeout=10.0,
            )
            with pytest.raises(
                asyncio.TimeoutError, match="waiting for worker to become ready"
            ):
                await fut

    @pytest.mark.asyncio
    async def test_queue_logs_retry_route_after_connector_error_continues_loop(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies ClientConnectorError without a session sets Retrying and re-enters routing.

        This test verifies by:
        1. First worker _make_request raises ClientConnectorError
        2. Second iteration uses a new route READY and second worker call succeeds
        3. Asserting final ok and that two _route calls occurred (retry path)

        Assumptions:
        - request_idx stays non-zero on retry so the 'retry route call' log branch can run
        """
        ep = make_serverless_endpoint(client_with_session)
        client = client_with_session

        ready = make_route_response_mock(
            status="READY",
            url="https://worker/",
            request_idx=3,
            body={"token": "t"},
        )

        route_calls = 0

        async def route_then_route(*_a, **_kw):
            nonlocal route_calls
            route_calls += 1
            return ready

        make_req = AsyncMock(
            side_effect=[
                aiohttp.ClientConnectorError(MagicMock(), OSError("gone")),
                {"ok": True, "json": {"done": True}},
            ]
        )

        with (
            patch.object(Endpoint, "_route", side_effect=route_then_route),
            patch("vastai.serverless.client.client._make_request", make_req),
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/do",
                worker_payload={},
                cost=10,
            )
            result = await fut

        assert result["ok"] is True
        assert route_calls == 2

    @pytest.mark.asyncio
    async def test_queue_connector_error_with_session_raises_connection_error(
        self,
        client_with_session,
        make_serverless_endpoint,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies ClientConnectorError with an active session raises ConnectionError.

        This test verifies by:
        1. Passing a Session with url set and open=True
        2. Making _make_request raise ClientConnectorError
        3. Asserting ConnectionError and session.open is False

        Assumptions:
        - Session-bound workers cannot re-route; client marks session closed
        """
        ep = make_serverless_endpoint(client_with_session)
        client = client_with_session
        sess = Session(ep, 1, 60.0, "e", "https://sess/", {"a": 1})

        with (
            patch(
                "vastai.serverless.client.client._make_request",
                new_callable=AsyncMock,
                side_effect=aiohttp.ClientConnectorError(MagicMock(), OSError("gone")),
            ),
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/do",
                worker_payload={},
                session=sess,
            )
            with pytest.raises(ConnectionError, match="Session worker unavailable"):
                await fut

        assert sess.open is False

    @pytest.mark.asyncio
    async def test_queue_server_disconnected_with_session_raises_connection_error(
        self,
        client_with_session,
        make_serverless_endpoint,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies ServerDisconnectedError with session is treated like a dead worker.

        This test verifies by:
        1. Raising aiohttp.ServerDisconnectedError from _make_request
        2. Asserting ConnectionError

        Assumptions:
        - Same handling as ClientConnectorError for session-bound calls
        """
        ep = make_serverless_endpoint(client_with_session)
        client = client_with_session
        sess = Session(ep, 1, 60.0, "e", "https://sess/", {"a": 1})

        with (
            patch(
                "vastai.serverless.client.client._make_request",
                new_callable=AsyncMock,
                side_effect=aiohttp.ServerDisconnectedError(),
            ),
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/do",
                worker_payload={},
                session=sess,
            )
            with pytest.raises(ConnectionError):
                await fut

    @pytest.mark.asyncio
    async def test_queue_generic_exception_on_worker_retries_then_succeeds(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies non-aiohttp exceptions from _make_request trigger Retrying and continue.

        This test verifies by:
        1. First _make_request raises ValueError
        2. Second returns ok True
        3. Asserting successful result

        Assumptions:
        - Generic Exception path does not re-raise immediately; loop continues
        """
        ep = make_serverless_endpoint(client_with_session)
        client = client_with_session

        ready = make_route_response_mock(status="READY", request_idx=2, body={"t": 1})

        make_req = AsyncMock(
            side_effect=[
                ValueError("transient"),
                {"ok": True, "json": {"v": 1}},
            ]
        )

        with (
            patch.object(Endpoint, "_route", AsyncMock(return_value=ready)),
            patch("vastai.serverless.client.client._make_request", make_req),
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/do",
                worker_payload={},
            )
            result = await fut

        assert result["ok"] is True
        assert make_req.await_count == 2

    @pytest.mark.asyncio
    async def test_queue_uses_session_url_without_routing(
        self,
        client_with_session,
        make_serverless_endpoint,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies queue_endpoint_request skips routing when session is provided with a URL.

        This test verifies by:
        1. Passing Session with url and auth_data
        2. Asserting Endpoint._route is never called and worker URL matches session.url

        Assumptions:
        - session branch sets worker_url and auth_data from the session
        """
        ep = make_serverless_endpoint(client_with_session)
        client = client_with_session
        sess = Session(ep, 9, 60.0, "e", "https://sess-worker/", {"tok": 1})

        route_mock = AsyncMock()
        with (
            patch.object(Endpoint, "_route", route_mock),
            patch(
                "vastai.serverless.client.client._make_request",
                new_callable=AsyncMock,
                return_value={"ok": True, "json": {"x": 1}},
            ) as make_req,
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/in",
                worker_payload={"p": 1},
                session=sess,
            )
            result = await fut

        route_mock.assert_not_called()
        assert result["url"] == "https://sess-worker/"
        called_url = make_req.call_args.kwargs["url"]
        assert called_url == "https://sess-worker/"

    @pytest.mark.asyncio
    async def test_queue_non_ok_retryable_retries_until_success(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies retryable ok=False responses sleep and retry when retry=True.

        This test verifies by:
        1. Returning ok=False with retryable=True then ok=True
        2. Patching sleep and random
        3. Asserting final success and multiple _make_request calls

        Assumptions:
        - max_retries None allows retries while retryable remains true
        """
        ep = make_serverless_endpoint(client_with_session)
        client = client_with_session

        ready = make_route_response_mock(status="READY")

        make_req = AsyncMock(
            side_effect=[
                {"ok": False, "retryable": True, "status": 503},
                {"ok": True, "json": {"ok": True}},
            ]
        )

        with (
            patch.object(Endpoint, "_route", AsyncMock(return_value=ready)),
            patch("vastai.serverless.client.client._make_request", make_req),
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/do",
                worker_payload={},
                retry=True,
            )
            result = await fut

        assert result["ok"] is True
        assert make_req.await_count == 2

    @pytest.mark.asyncio
    async def test_queue_retry_false_finishes_on_retryable_without_retry(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """When retry=False, a retryable worker error completes immediately (no loop)."""
        ep = make_serverless_endpoint(client_with_session)
        client = client_with_session

        ready = make_route_response_mock(status="READY")

        with (
            patch.object(Endpoint, "_route", AsyncMock(return_value=ready)),
            patch(
                "vastai.serverless.client.client._make_request",
                new_callable=AsyncMock,
                return_value={
                    "ok": False,
                    "retryable": True,
                    "status": 503,
                    "text": "busy",
                },
            ) as make_req,
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/do",
                worker_payload={},
                retry=False,
            )
            result = await fut

        assert result["ok"] is False
        assert make_req.await_count == 1

    @pytest.mark.asyncio
    async def test_queue_max_retries_stops_retryable_loop(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """When max_retries is set and exhausted, return the last non-ok result."""
        ep = make_serverless_endpoint(client_with_session)
        client = client_with_session

        ready = make_route_response_mock(status="READY")

        fail = {"ok": False, "retryable": True, "status": 503, "json": {"detail": "x"}}

        with (
            patch.object(Endpoint, "_route", AsyncMock(return_value=ready)),
            patch(
                "vastai.serverless.client.client._make_request",
                new_callable=AsyncMock,
                return_value=fail,
            ) as make_req,
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/do",
                worker_payload={},
                max_retries=1,
            )
            result = await fut

        assert result["ok"] is False
        assert result["response"] == {"detail": "x"}
        assert make_req.await_count == 1

    @pytest.mark.asyncio
    async def test_queue_non_ok_retryable_times_out_before_backoff_sleep(
        self,
        monkeypatch,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies TimeoutError when retry is needed but global timeout is already exceeded.

        This test verifies by:
        1. Returning ok=False retryable with timeout set
        2. Patching time.time so elapsed time exceeds timeout before sleep
        3. Asserting asyncio.TimeoutError

        Assumptions:
        - Lines that guard retry with remaining timeout are exercised

        Disables the client logger so ``LogRecord`` timestamps do not consume ``time.time()``
        calls from the side_effect iterator (same freeze risk as the polling-timeout test).
        """
        client = client_with_session
        monkeypatch.setattr(client.logger, "disabled", True)
        ep = make_serverless_endpoint(client)

        ready = make_route_response_mock(status="READY")

        # time.time() order: create_time (ServerlessRequest.__init__), start_time, first
        # outer-loop deadline (~357), then retry guard (~447), then f-string in TimeoutError.
        _clock = iter([0.0, 0.0, 0.0, 100.0, 100.0])

        def _t() -> float:
            return next(_clock, 1e9)

        with (
            patch.object(Endpoint, "_route", AsyncMock(return_value=ready)),
            patch(
                "vastai.serverless.client.client._make_request",
                new_callable=AsyncMock,
                return_value={"ok": False, "retryable": True, "status": 503},
            ),
            patch("vastai.serverless.client.client.time.time", side_effect=_t),
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/do",
                worker_payload={},
                timeout=50.0,
            )
            # LogRecord timestamps may call time.time() while the patch is active, so the
            # exact call sequence to reach the retry-path guard (line ~447) can shift.
            with pytest.raises(asyncio.TimeoutError, match="(?i)timed out after"):
                await fut

    @pytest.mark.asyncio
    async def test_queue_non_ok_not_retryable_returns_error_dict_without_json(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies completed future carries text fallback when HTTP json is missing.

        This test verifies by:
        1. Returning ok=False without retryable and without json but with text
        2. Asserting response['response'] embeds error text

        Assumptions:
        - Non-retryable failures finalize the ServerlessRequest with ok False
        """
        ep = make_serverless_endpoint(client_with_session)
        client = client_with_session

        ready = make_route_response_mock(status="READY")

        with (
            patch.object(Endpoint, "_route", AsyncMock(return_value=ready)),
            patch(
                "vastai.serverless.client.client._make_request",
                new_callable=AsyncMock,
                return_value={
                    "ok": False,
                    "retryable": False,
                    "status": 400,
                    "json": None,
                    "text": "bad request body",
                },
            ),
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/do",
                worker_payload={},
                retry=True,
            )
            result = await fut

        assert result["ok"] is False
        assert result["response"] == {"error": "bad request body"}

    @pytest.mark.asyncio
    async def test_queue_stream_true_uses_stream_field_in_success_result(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies stream=True maps worker_response from result['stream'].

        This test verifies by:
        1. Returning ok=True with stream=iterable-like sentinel (mock)
        2. Asserting response['response'] is that stream object

        Assumptions:
        - Streaming mode does not read json for the worker payload slot
        """
        ep = make_serverless_endpoint(client_with_session)
        client = client_with_session

        ready = make_route_response_mock(status="READY")
        stream_obj = object()

        with (
            patch.object(Endpoint, "_route", AsyncMock(return_value=ready)),
            patch(
                "vastai.serverless.client.client._make_request",
                new_callable=AsyncMock,
                return_value={"ok": True, "stream": stream_obj},
            ),
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/do",
                worker_payload={},
                stream=True,
            )
            result = await fut

        assert result["response"] is stream_obj

    @pytest.mark.asyncio
    async def test_queue_cancel_marks_background_task_cancelled(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
    ) -> None:
        """
        Verifies cancelling the ServerlessRequest cancels the background task and ends clean.

        This test verifies by:
        1. Patching sleep to block until cancelled (CancelledError)
        2. Cancelling the future from the test task
        3. Asserting the future is cancelled or completes without result

        Assumptions:
        - add_done_callback propagates cancellation to the asyncio.Task running task()
        """
        ep = make_serverless_endpoint(client_with_session)
        client = client_with_session

        waiting = make_route_response_mock()

        cancel_event = asyncio.Event()
        # Patching client.asyncio.sleep replaces the real asyncio.sleep globally; keep a
        # reference so the side_effect can await the true sleep and avoid recursion.
        real_sleep = asyncio.sleep

        async def slow_sleep(_delay: float) -> None:
            cancel_event.set()
            await real_sleep(0.01)

        async def wait_route(*_a, **_kw):
            return waiting

        with (
            patch.object(Endpoint, "_route", side_effect=wait_route),
            patch(
                "vastai.serverless.client.client.asyncio.sleep", side_effect=slow_sleep
            ),
            patch("vastai.serverless.client.client.random.uniform", return_value=0.1),
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/do",
                worker_payload={},
            )
            await asyncio.wait_for(cancel_event.wait(), timeout=2.0)
            fut.cancel()
            with pytest.raises(asyncio.CancelledError):
                await fut
            # Let the background task process cancellation and run the in-task
            # ``except asyncio.CancelledError`` handler (coverage + deterministic teardown).
            await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_queue_reuses_provided_serverless_request_instance(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies queue_endpoint_request returns the same ServerlessRequest when passed in.

        This test verifies by:
        1. Passing serverless_request=existing future
        2. Asserting identity is preserved (branch that skips default construction)

        Assumptions:
        - Callers can correlate logs/status on a pre-created request object
        """
        client = client_with_session
        ep = make_serverless_endpoint(client)

        ready = make_route_response_mock(status="READY")
        existing = ServerlessRequest()

        with (
            patch.object(Endpoint, "_route", AsyncMock(return_value=ready)),
            patch(
                "vastai.serverless.client.client._make_request",
                new_callable=AsyncMock,
                return_value={"ok": True, "json": {}},
            ),
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/do",
                worker_payload={},
                serverless_request=existing,
            )
            assert fut is existing
            await fut

    @pytest.mark.asyncio
    async def test_queue_route_ready_with_zero_request_idx_still_completes(
        self,
        client_with_session,
        make_serverless_endpoint,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """
        Verifies routing with falsy request_idx still reaches worker _make_request.

        This test verifies by:
        1. Using RouteResponse-like body without request_idx so internal idx is 0
        2. Asserting worker call succeeds (covers 'no request_idx' log branch)

        Assumptions:
        - request_idx 0 is falsy and triggers the error log but processing continues
        """
        ep = make_serverless_endpoint(client_with_session)
        client = client_with_session

        from vastai.serverless.client.endpoint import RouteResponse

        route = RouteResponse({"url": "https://w/", "token": "t"})

        with (
            patch.object(Endpoint, "_route", AsyncMock(return_value=route)),
            patch(
                "vastai.serverless.client.client._make_request",
                new_callable=AsyncMock,
                return_value={"ok": True, "json": {"z": 2}},
            ),
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/do",
                worker_payload={},
            )
            result = await fut

        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_queue_success_records_latency_in_client_deque(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_route_response_mock,
        patch_serverless_queue_async_stubs,
    ) -> None:
        """Completed worker requests append one sample to ``Serverless.latencies``."""
        client = client_with_session
        client.latencies.clear()
        ep = make_serverless_endpoint(client)
        ready = make_route_response_mock(status="READY")

        with (
            patch.object(Endpoint, "_route", AsyncMock(return_value=ready)),
            patch(
                "vastai.serverless.client.client._make_request",
                new_callable=AsyncMock,
                return_value={"ok": True, "json": {"x": 1}},
            ),
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/do",
                worker_payload={},
            )
            await fut

        assert len(client.latencies) == 1
        assert isinstance(client.latencies[0], float)
        assert client.latencies[0] >= 0.0

    @pytest.mark.asyncio
    async def test_queue_session_with_url_none_calls_worker_with_empty_url(
        self,
        client_with_session,
        make_serverless_endpoint,
        make_session_mock,
    ) -> None:
        """If ``session.url`` is falsy, routing body is skipped and worker URL stays empty."""
        client = client_with_session
        ep = make_serverless_endpoint(client)

        mock_session = make_session_mock(
            session_id=7,
            url=None,
            auth_data={"tok": 1},
        )

        route_mock = AsyncMock()
        make_req = AsyncMock(return_value={"ok": True, "json": {"done": True}})

        with (
            patch.object(Endpoint, "_route", route_mock),
            patch("vastai.serverless.client.client._make_request", make_req),
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/in",
                worker_payload={"p": 1},
                session=mock_session,
            )
            await fut

        route_mock.assert_not_called()
        assert make_req.call_args.kwargs["url"] == ""

    @pytest.mark.asyncio
    async def test_queue_route_raises_sets_errored_exception_on_future(
        self,
        client_with_session,
        make_serverless_endpoint,
    ) -> None:
        """Failures from ``endpoint._route`` outside the worker try block surface on the future."""
        client = client_with_session
        ep = make_serverless_endpoint(client)

        with patch.object(
            Endpoint,
            "_route",
            AsyncMock(side_effect=RuntimeError("scheduler unavailable")),
        ):
            fut = client.queue_endpoint_request(
                endpoint=ep,
                worker_route="/do",
                worker_payload={},
            )
            with pytest.raises(RuntimeError, match="scheduler unavailable"):
                await fut

        assert fut.status == "Errored"
