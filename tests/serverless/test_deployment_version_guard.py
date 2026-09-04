"""Tests for deployment version pinning across a rolling update.

``ensure_ready()`` returns as soon as the tarball is uploaded and the rolling
update is triggered — it does not wait for workers to converge. A call issued
immediately afterwards could be answered by a worker still running the previous
code, which surfaces as a confusing type error in the caller rather than as a
deployment problem.

The worker now rejects a request that names a different version with 409, and the
client treats 409 as retryable so it re-routes to an updated worker.
"""

import pytest

from vastai.serverless.client.connection import _retryable


class TestRetryableStatuses:
    def test_409_is_retryable_so_the_client_reroutes(self) -> None:
        assert _retryable(409) is True

    def test_previously_retryable_statuses_are_unchanged(self) -> None:
        for status in (408, 429, 500, 502, 503, 599):
            assert _retryable(status) is True

    def test_other_client_errors_remain_terminal(self) -> None:
        for status in (400, 401, 403, 404, 410, 422):
            assert _retryable(status) is False


async def _noop_remote(*, args: list = [], kwargs: dict = {}):
    """Stand-in with the same signature the real wrapper has.

    Keyword-only ``args``/``kwargs`` and nothing else, so a version hint that
    leaked into the user payload would raise TypeError here instead of silently
    working.
    """
    return {"ok": None}


class TestWorkerVersionGuard:
    """The worker-side half: refuse work meant for a different version."""

    async def _post(self, testkit, body_extra: dict, worker_version):
        """Drive one request through the handler and return the response.

        Requests that pass the version guard go on to contact the (absent) model
        server and come back 500; the assertions below only care that they were
        *not* short-circuited with 409.
        """
        backend, handler = testkit.make_backend(allow_parallel=True)
        backend.metrics.deployment_version_id = worker_version
        backend.unsecured = True  # skip signature checks for this unit test
        # The guard only applies to deployment (remote-dispatch) handlers.
        handler.remote_function = _noop_remote

        body = testkit.auth_payload()
        # The client nests this inside "payload", next to its kwargs -- not at
        # the top level of the envelope.
        body["payload"].update(body_extra)
        request = testkit.json_request(body)
        try:
            return await backend.create_handler(handler)(request)
        finally:
            session = backend.__dict__.get("session")
            if session is not None and not session.closed:
                await session.close()

    async def test_rejects_a_call_for_a_newer_version(
        self, serverless_backend_testkit
    ) -> None:
        response = await self._post(
            serverless_backend_testkit,
            {"expect_version_id": 3216},
            worker_version=3215,
        )
        assert response.status == 409

    async def test_serves_a_call_for_its_own_version(
        self, serverless_backend_testkit
    ) -> None:
        response = await self._post(
            serverless_backend_testkit,
            {"expect_version_id": 3215},
            worker_version=3215,
        )
        assert response.status != 409

    async def test_serves_when_the_client_does_not_pin_a_version(
        self, serverless_backend_testkit
    ) -> None:
        """Backwards compatibility: older clients send no expectation."""
        response = await self._post(
            serverless_backend_testkit, {}, worker_version=3215
        )
        assert response.status != 409

    async def test_serves_when_the_worker_does_not_know_its_version(
        self, serverless_backend_testkit
    ) -> None:
        """A non-deployment endpoint has no version; do not start 409-ing."""
        response = await self._post(
            serverless_backend_testkit,
            {"expect_version_id": 3216},
            worker_version=None,
        )
        assert response.status != 409

    async def test_version_hint_is_not_passed_to_the_remote_function(
        self, serverless_backend_testkit
    ) -> None:
        """The hint is transport metadata and must be stripped from the payload.

        It travels nested beside the user's kwargs, so failing to remove it
        splats an unexpected keyword argument into the wrapped function.
        """
        seen = {}

        async def capture(*, args: list = [], kwargs: dict = {}):
            seen["args"] = args
            seen["kwargs"] = kwargs
            return {"ok": None}

        testkit = serverless_backend_testkit
        backend, handler = testkit.make_backend(allow_parallel=True)
        backend.metrics.deployment_version_id = 3215
        backend.unsecured = True
        handler.remote_function = capture

        body = testkit.auth_payload()
        body["payload"] = {"kwargs": {"x": 1}, "expect_version_id": 3215}
        response = await backend.create_handler(handler)(testkit.json_request(body))

        assert response.status == 200
        assert seen["kwargs"] == {"x": 1}
        assert "expect_version_id" not in seen["kwargs"]
