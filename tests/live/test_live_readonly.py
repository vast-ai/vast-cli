"""Live read-only API tests — requires VAST_API_KEY environment variable.

These tests call the real Vast.ai API but only perform read operations.
They verify that the API functions return data in the expected shape.
"""

import pytest

pytestmark = pytest.mark.live


class TestBillingReadonly:
    def test_show_user(self, live_client):
        from vastai.api.billing import show_user
        result = show_user(live_client)
        assert isinstance(result, dict)
        assert "email" in result
        assert "id" in result
        assert "api_key" not in result

    def test_show_invoices(self, live_client):
        from vastai.api.billing import show_invoices
        result = show_invoices(live_client)
        assert isinstance(result, dict)
        assert "invoices" in result
        assert "current" in result

    def test_show_subaccounts(self, live_client):
        from vastai.api.billing import show_subaccounts
        from requests.exceptions import HTTPError
        try:
            result = show_subaccounts(live_client)
            assert isinstance(result, list)
        except HTTPError as e:
            if e.response.status_code == 400:
                pytest.skip("Account not approved for subaccount APIs")
            raise

    def test_show_ipaddrs(self, live_client):
        from vastai.api.billing import show_ipaddrs
        result = show_ipaddrs(live_client)
        assert isinstance(result, list)


class TestAuthReadonly:
    def test_show_audit_logs(self, live_client):
        from vastai.api.auth import show_audit_logs
        result = show_audit_logs(live_client)
        assert isinstance(result, list)

    def test_show_env_vars(self, live_client):
        from vastai.api.auth import show_env_vars
        result = show_env_vars(live_client)
        assert isinstance(result, dict)

    def test_show_scheduled_jobs(self, live_client):
        from vastai.api.auth import show_scheduled_jobs
        result = show_scheduled_jobs(live_client)
        assert isinstance(result, list)

    def test_tfa_status(self, live_client):
        from vastai.api.auth import tfa_status
        result = tfa_status(live_client)
        assert isinstance(result, dict)
        assert "tfa_enabled" in result


class TestOffersReadonly:
    def test_search_offers(self, live_client):
        from vastai.api.offers import search_offers
        result = search_offers(live_client, limit=3)
        assert isinstance(result, list)
        if result:
            assert "gpu_name" in result[0]

    def test_search_templates(self, live_client):
        from vastai.api.offers import search_templates
        result = search_templates(live_client)
        assert isinstance(result, list)


class TestInstancesReadonly:
    def test_show_instances(self, live_client):
        from vastai.api.instances import show_instances
        result = show_instances(live_client)
        assert isinstance(result, list)


class TestKeysReadonly:
    def test_show_ssh_keys(self, live_client):
        from vastai.api.keys import show_ssh_keys
        result = show_ssh_keys(live_client)
        assert result is not None

    def test_show_api_keys(self, live_client):
        from vastai.api.keys import show_api_keys
        result = show_api_keys(live_client)
        assert result is not None


class TestMachinesReadonly:
    def test_show_machines(self, live_client):
        from vastai.api.machines import show_machines
        result = show_machines(live_client)
        assert isinstance(result, list)


class TestEndpointsReadonly:
    def test_show_endpoints(self, live_client):
        from vastai.api.endpoints import show_endpoints
        result = show_endpoints(live_client)
        assert result is not None


class TestStorageReadonly:
    def test_show_volumes(self, live_client):
        from vastai.api.storage import show_volumes
        result = show_volumes(live_client)
        assert isinstance(result, list)

    def test_show_connections(self, live_client):
        from vastai.api.storage import show_connections
        result = show_connections(live_client)
        assert result is not None
