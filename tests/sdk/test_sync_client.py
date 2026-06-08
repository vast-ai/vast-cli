"""Tests for vastai.sync.client.SyncClient instance-listing.

Focused on the v0 -> v1 instances-list migration: the SyncClient hand-rolls
its own request (manual ``json.dumps`` into ``requests`` params, no VastClient
auto-encoding), so it needs coverage the shared-client tests don't provide.
"""

import json
from unittest.mock import patch, MagicMock

from vastai.sync.client import SyncClient


def _resp(payload):
    """Mock requests.Response returning ``payload`` from ``.json()``."""
    r = MagicMock()
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    return r


class TestShowInstancesV1:
    def test_hits_v1_endpoint(self):
        client = SyncClient(api_key="test-key")
        with patch("vastai.sync.client.requests.get") as mock_get:
            mock_get.return_value = _resp({"instances": [{"id": 1}]})
            client.show_instances()

        url = mock_get.call_args[0][0]
        assert url.endswith("/api/v1/instances/")
        # No v0 owner-keyed listing — v1 scopes by the authenticated client_id.
        assert mock_get.call_args.kwargs["params"].get("owner") is None

    def test_paginates_until_next_token_exhausted(self):
        client = SyncClient(api_key="test-key")
        pages = [
            _resp({"instances": [{"id": 1}, {"id": 2}], "next_token": "tok"}),
            _resp({"instances": [{"id": 3}], "next_token": None}),
        ]
        with patch("vastai.sync.client.requests.get", side_effect=pages) as mock_get:
            result = client.show_instances()

        assert mock_get.call_count == 2
        assert [inst.id for inst in result] == [1, 2, 3]
        # Second page must carry the token returned by the first.
        assert mock_get.call_args_list[1].kwargs["params"]["after_token"] == "tok"

    def test_nested_params_are_json_encoded(self):
        client = SyncClient(api_key="test-key")
        with patch("vastai.sync.client.requests.get") as mock_get:
            mock_get.return_value = _resp({"instances": []})
            client.show_instances()

        params = mock_get.call_args.kwargs["params"]
        # Dict/list params must be JSON strings — requests cannot serialize the
        # nested structures the v1 backend expects on the query string.
        assert json.loads(params["select_filters"]) == {}
        assert json.loads(params["order_by"]) == [{"col": "id", "dir": "asc"}]

    def test_null_instances_returns_empty(self):
        client = SyncClient(api_key="test-key")
        with patch("vastai.sync.client.requests.get") as mock_get:
            mock_get.return_value = _resp({"instances": None})
            assert client.show_instances() == []
