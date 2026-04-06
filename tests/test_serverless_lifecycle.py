"""Integration tests for serverless endpoint lifecycle.

Creates real resources (endpoints, workergroups) — incurs costs.
Uses the session-scoped managed_endpoint fixture for request tests,
and creates/tears down ephemeral endpoints for lifecycle tests.

These tests use the session-scoped serverless_client and _serverless_loop
fixtures rather than pytest.mark.asyncio, since the client is session-scoped
and must use a consistent event loop.
"""

import pytest

from vastai.data.endpoint import EndpointConfig
from vastai.data.workergroup import WorkergroupConfig
from vastai.serverless.client.managed import ManagedEndpoint


pytestmark = [pytest.mark.integration, pytest.mark.serverless]


class TestEndpointLifecycle:
    """Tests for creating and deleting endpoints (no workergroups)."""

    def test_create_and_delete_endpoint(self, serverless_client, _serverless_loop):
        async def _test():
            ep = await serverless_client.create_endpoint(
                EndpointConfig(endpoint_name="sdk-test-lifecycle")
            )
            assert ep.id > 0
            assert isinstance(ep, ManagedEndpoint)
            await ep.delete()

        _serverless_loop.run_until_complete(_test())

    def test_create_endpoint_with_config(self, serverless_client, _serverless_loop):
        async def _test():
            ep = await serverless_client.create_endpoint(
                EndpointConfig(
                    endpoint_name="sdk-test-configured",
                    cold_workers=2,
                    max_workers=5,
                )
            )
            try:
                assert ep.id > 0
            finally:
                await ep.delete()

        _serverless_loop.run_until_complete(_test())


class TestWorkerGroupLifecycle:
    """Tests for creating and deleting workergroups on an endpoint."""

    def test_add_and_delete_workergroup(self, serverless_client, template_hash, _serverless_loop):
        async def _test():
            ep = await serverless_client.create_endpoint(
                EndpointConfig(endpoint_name="sdk-test-wg")
            )
            try:
                wg_id = await ep.add_workergroup(template_hash)
                assert isinstance(wg_id, int)
                assert wg_id > 0
                await serverless_client.delete_workergroup(wg_id)
            finally:
                await ep.delete()

        _serverless_loop.run_until_complete(_test())

    def test_add_workergroup_with_config(self, serverless_client, template_hash, _serverless_loop):
        async def _test():
            ep = await serverless_client.create_endpoint(
                EndpointConfig(endpoint_name="sdk-test-wg-cfg")
            )
            try:
                wg_id = await ep.add_workergroup(
                    WorkergroupConfig(
                        template_hash=template_hash,
                        search_params="gpu_ram>=8",
                        gpu_ram=8.0,
                    )
                )
                assert wg_id > 0
                await serverless_client.delete_workergroup(wg_id)
            finally:
                await ep.delete()

        _serverless_loop.run_until_complete(_test())


class TestEndpointRequest:
    """Tests for sending requests to a live serverless endpoint.

    Uses the session-scoped managed_endpoint fixture which has a workergroup
    already attached. The first request may take a while as the autoscaler
    provisions a worker.
    """

    def test_request_returns_response(self, managed_endpoint, _serverless_loop):
        async def _test():
            result = await managed_endpoint.request(
                "/v1/chat/completions",
                {
                    "model": "meta-llama/Llama-3.1-8B-Instruct",
                    "messages": [{"role": "user", "content": "Say hello in exactly one word."}],
                    "max_tokens": 16,
                },
                timeout=300,
            )
            assert result["ok"] is True
            assert result["status"] == 200
            assert "response" in result

        _serverless_loop.run_until_complete(_test())

    def test_request_has_latency(self, managed_endpoint, _serverless_loop):
        async def _test():
            result = await managed_endpoint.request(
                "/v1/chat/completions",
                {
                    "model": "meta-llama/Llama-3.1-8B-Instruct",
                    "messages": [{"role": "user", "content": "Reply with just the word 'ok'."}],
                    "max_tokens": 8,
                },
                timeout=300,
            )
            assert result["latency"] is not None
            assert result["latency"] > 0

        _serverless_loop.run_until_complete(_test())
