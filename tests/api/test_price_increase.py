"""Tests for vastai/api/price_increase.py.

Backend contract (source of truth: ``vast/web/views/instance.py:257-312``,
``vast/web/views/pydantic/models/instance.py``):

    PUT /instances/accept-price-increase/   body {"pending_price_increase_id": int}
    PUT /instances/reject-price-increase/   body {"pending_price_increase_id": int}

Both bodies are enforced by ``_Base.Config.extra='forbid'`` — any extra key
returns HTTP 422, so we assert *exact* body equality.
"""

import pytest
from requests.exceptions import HTTPError

from vastai.api import price_increase


SAMPLE_ROW = {
    "pending_price_increase_id": 999,
    "contract_id": 123,
    "host_id": 7,
    "new_gpu_costpersec": 0.0002,
    "old_gpu_costpersec": 0.0001,
    "new_disk_ram_costpersec": None,
    "old_disk_ram_costpersec": None,
    "new_bwu_cost": 0.02,
    "old_bwu_cost": 0.01,
    "new_bwd_cost": 0.02,
    "old_bwd_cost": 0.01,
    "new_platform_fee": 0.15,
    "old_platform_fee": 0.10,
    "contract_end_date": 1_700_000_000.0,
    "ask_end_date": 1_700_500_000.0,
    "created_at": 1_699_990_000.0,
}


class TestListPending:
    def test_list_pending_returns_envelope(self, mock_client, mock_response):
        envelope = {
            "success": True,
            "count": 1,
            "truncated": False,
            "pending_price_increases": [SAMPLE_ROW],
        }
        mock_client.get.return_value = mock_response(200, envelope)
        result = price_increase.list_pending(mock_client)
        assert result == envelope
        mock_client.get.assert_called_once_with("/instances/pending-price-increases/")

    def test_list_pending_raises_on_http_error(self, mock_client, mock_response):
        mock_client.get.return_value = mock_response(500, {"msg": "boom"})
        with pytest.raises(HTTPError):
            price_increase.list_pending(mock_client)


class TestAccept:
    def test_accept_sends_only_pending_id(self, mock_client, mock_response):
        mock_client.put.return_value = mock_response(
            200, {"success": True, "pending_price_increase_id": 999, "contract_id": 123},
        )
        result = price_increase.accept(mock_client, 999)
        mock_client.put.assert_called_once()
        url = mock_client.put.call_args[0][0]
        body = mock_client.put.call_args[1]["json_data"]
        assert url == "/instances/accept-price-increase/"
        # Exact equality matters: extra='forbid' on the backend returns 422
        # for any additional key.
        assert body == {"pending_price_increase_id": 999}
        assert result["contract_id"] == 123

    def test_accept_propagates_404_no_pending(self, mock_client, mock_response):
        mock_client.put.return_value = mock_response(
            404, {"success": False, "error": price_increase.NO_PENDING_PRICE_INCREASE},
        )
        with pytest.raises(HTTPError) as excinfo:
            price_increase.accept(mock_client, 999)
        assert excinfo.value.response.status_code == 404
        assert excinfo.value.response.json()["error"] == "no_pending_price_increase"

    def test_accept_propagates_legacy_409(self, mock_client, mock_response):
        mock_client.put.return_value = mock_response(409, {"msg": "conflict"})
        with pytest.raises(HTTPError) as excinfo:
            price_increase.accept(mock_client, 999)
        assert excinfo.value.response.status_code == 409

    def test_accept_coerces_pending_id_to_int(self, mock_client, mock_response):
        mock_client.put.return_value = mock_response(
            200, {"success": True, "pending_price_increase_id": 5, "contract_id": 1},
        )
        price_increase.accept(mock_client, "5")
        body = mock_client.put.call_args[1]["json_data"]
        assert body == {"pending_price_increase_id": 5}
        assert isinstance(body["pending_price_increase_id"], int)


class TestReject:
    def test_reject_sends_only_pending_id(self, mock_client, mock_response):
        mock_client.put.return_value = mock_response(
            200, {"success": True, "pending_price_increase_id": 999, "contract_id": 123},
        )
        result = price_increase.reject(mock_client, 999)
        mock_client.put.assert_called_once()
        url = mock_client.put.call_args[0][0]
        body = mock_client.put.call_args[1]["json_data"]
        assert url == "/instances/reject-price-increase/"
        assert body == {"pending_price_increase_id": 999}
        assert result["contract_id"] == 123

    def test_reject_propagates_404_no_pending(self, mock_client, mock_response):
        mock_client.put.return_value = mock_response(
            404, {"success": False, "error": price_increase.NO_PENDING_PRICE_INCREASE},
        )
        with pytest.raises(HTTPError):
            price_increase.reject(mock_client, 999)
