"""Tests for vastai/api/client.py — VastClient URL building, headers, retry logic."""

import json
import pytest
from unittest.mock import patch, MagicMock
from vastai.api.client import VastClient


class TestBuildUrl:
    def test_adds_api_v0_prefix(self):
        c = VastClient(api_key=None)
        url = c._build_url("/instances")
        assert "/api/v0/instances" in url

    def test_preserves_api_v1_prefix(self):
        c = VastClient(api_key=None)
        url = c._build_url("/api/v1/invoices/")
        assert "/api/v1/invoices/" in url
        assert "/api/v0" not in url

    def test_appends_api_key(self):
        c = VastClient(api_key="mykey123")
        url = c._build_url("/instances")
        assert "api_key=mykey123" in url

    def test_no_query_when_no_args_and_no_key(self):
        c = VastClient(api_key=None)
        url = c._build_url("/instances")
        assert "?" not in url

    def test_url_encodes_query_args(self):
        c = VastClient(api_key=None)
        url = c._build_url("/test", query_args={"q": "hello world"})
        assert "q=hello+world" in url

    def test_json_encodes_dict_args(self):
        c = VastClient(api_key=None)
        url = c._build_url("/test", query_args={"data": {"key": "val"}})
        # json.dumps({"key": "val"}) URL-encoded
        assert "data=" in url

    def test_server_url_default(self):
        c = VastClient(api_key=None)
        url = c._build_url("/test")
        assert url.startswith("https://console.vast.ai")

    def test_custom_server_url(self):
        c = VastClient(api_key=None, server_url="https://custom.api.com")
        url = c._build_url("/test")
        assert url.startswith("https://custom.api.com")


class TestBuildHeaders:
    def test_includes_bearer_auth(self):
        c = VastClient(api_key="mykey")
        h = c._build_headers()
        assert h["Authorization"] == "Bearer mykey"

    def test_empty_when_no_key(self):
        c = VastClient(api_key=None)
        h = c._build_headers()
        assert h == {}


class TestHttpMethods:
    """Test that get/post/put/delete call _request with the correct method string."""

    @patch.object(VastClient, "_request")
    @patch.object(VastClient, "_build_headers", return_value={})
    @patch.object(VastClient, "_build_url", return_value="https://example.com/api/v0/test")
    def test_get_calls_request(self, mock_url, mock_headers, mock_req):
        c = VastClient(api_key=None)
        c.get("/test")
        mock_req.assert_called_once_with("GET", "https://example.com/api/v0/test", {}, None)

    @patch.object(VastClient, "_request")
    @patch.object(VastClient, "_build_headers", return_value={})
    @patch.object(VastClient, "_build_url", return_value="https://example.com/api/v0/test")
    def test_post_calls_request(self, mock_url, mock_headers, mock_req):
        c = VastClient(api_key=None)
        c.post("/test", json_data={"a": 1})
        mock_req.assert_called_once_with("POST", "https://example.com/api/v0/test", {}, {"a": 1})

    @patch.object(VastClient, "_request")
    @patch.object(VastClient, "_build_headers", return_value={})
    @patch.object(VastClient, "_build_url", return_value="https://example.com/api/v0/test")
    def test_put_calls_request(self, mock_url, mock_headers, mock_req):
        c = VastClient(api_key=None)
        c.put("/test", json_data={"b": 2})
        mock_req.assert_called_once_with("PUT", "https://example.com/api/v0/test", {}, {"b": 2})

    @patch.object(VastClient, "_request")
    @patch.object(VastClient, "_build_headers", return_value={})
    @patch.object(VastClient, "_build_url", return_value="https://example.com/api/v0/test")
    def test_delete_calls_request(self, mock_url, mock_headers, mock_req):
        c = VastClient(api_key=None)
        c.delete("/test")
        mock_req.assert_called_once_with("DELETE", "https://example.com/api/v0/test", {}, {})

    @patch.object(VastClient, "_request")
    @patch.object(VastClient, "_build_headers", return_value={})
    @patch.object(VastClient, "_build_url", return_value="https://example.com/api/v0/test")
    def test_post_defaults_json_to_empty_dict(self, mock_url, mock_headers, mock_req):
        c = VastClient(api_key=None)
        c.post("/test")
        mock_req.assert_called_once_with("POST", "https://example.com/api/v0/test", {}, {})


class TestRetryLogic:
    @patch("vastai.api.client.time.sleep")
    @patch("vastai.api.client.requests.Session")
    def test_retries_on_429(self, mock_session_cls, mock_sleep):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_prep = MagicMock()
        mock_session.prepare_request.return_value = mock_prep

        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_200 = MagicMock()
        resp_200.status_code = 200

        mock_session.send.side_effect = [resp_429, resp_200]

        c = VastClient(api_key=None, retry=3)
        result = c._request("GET", "https://example.com", {})

        assert result.status_code == 200
        assert mock_sleep.call_count == 1

    @patch("vastai.api.client.time.sleep")
    @patch("vastai.api.client.requests.Session")
    def test_stops_on_non_429(self, mock_session_cls, mock_sleep):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_prep = MagicMock()
        mock_session.prepare_request.return_value = mock_prep

        resp_500 = MagicMock()
        resp_500.status_code = 500

        mock_session.send.return_value = resp_500

        c = VastClient(api_key=None, retry=3)
        result = c._request("GET", "https://example.com", {})

        assert result.status_code == 500
        mock_sleep.assert_not_called()

    @patch("vastai.api.client.time.sleep")
    @patch("vastai.api.client.requests.Session")
    def test_exhausts_retry_count(self, mock_session_cls, mock_sleep):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_prep = MagicMock()
        mock_session.prepare_request.return_value = mock_prep

        resp_429 = MagicMock()
        resp_429.status_code = 429
        mock_session.send.return_value = resp_429

        c = VastClient(api_key=None, retry=2)
        result = c._request("GET", "https://example.com", {})

        assert result.status_code == 429
        assert mock_session.send.call_count == 2


class TestClientInit:
    def test_default_values(self):
        c = VastClient()
        assert c.api_key is None
        assert c.retry == 3
        assert c.explain is False
        assert c.curl is False

    def test_custom_values(self):
        c = VastClient(api_key="k", server_url="http://x", retry=5, explain=True, curl=True)
        assert c.api_key == "k"
        assert c.server_url == "http://x"
        assert c.retry == 5
        assert c.explain is True
        assert c.curl is True
