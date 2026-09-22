"""Tests for vastai/api/client.py — VastClient URL building, headers, retry logic."""

import json
import pytest
import requests
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from vastai.api.client import VastClient, VastSession, as_curl_command, domain_of
from vastai.utils import VERSION


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

    def test_does_not_append_api_key(self):
        c = VastClient(api_key="mykey123")
        url = c._build_url("/instances")
        assert url == "https://console.vast.ai/api/v0/instances"

    def test_api_key_is_not_added_to_query_args(self):
        c = VastClient(api_key="mykey123")
        query_args = {"owner": "me"}

        url = c._build_url("/instances", query_args=query_args)

        assert url == "https://console.vast.ai/api/v0/instances?owner=me"
        assert query_args == {"owner": "me"}

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

    def test_no_auth_when_no_key(self):
        c = VastClient(api_key=None)
        h = c._build_headers()
        assert "Authorization" not in h

    def test_user_agent_defaults_to_sdk(self):
        c = VastClient(api_key=None)
        h = c._build_headers()
        assert h["User-Agent"] == f"vastai-sdk/{VERSION}"

    def test_user_agent_client_type(self):
        c = VastClient(api_key=None, client_type="cli")
        h = c._build_headers()
        assert h["User-Agent"] == f"vastai-cli/{VERSION}"


class TestHttpMethods:
    """Test that get/post/put/delete call _request with the correct method string."""

    @patch.object(VastClient, "_request")
    @patch.object(VastClient, "_build_headers", return_value={})
    @patch.object(VastClient, "_build_url", return_value="https://example.com/api/v0/test")
    def test_get_calls_request(self, mock_url, mock_headers, mock_req):
        c = VastClient(api_key=None)
        c.get("/test")
        mock_req.assert_called_once_with("GET", "https://example.com/api/v0/test", {}, None, timeout=None)

    @patch.object(VastClient, "_request")
    @patch.object(VastClient, "_build_headers", return_value={})
    @patch.object(VastClient, "_build_url", return_value="https://example.com/api/v0/test")
    def test_post_calls_request(self, mock_url, mock_headers, mock_req):
        c = VastClient(api_key=None)
        c.post("/test", json_data={"a": 1})
        mock_req.assert_called_once_with("POST", "https://example.com/api/v0/test", {}, {"a": 1}, timeout=None)

    @patch.object(VastClient, "_request")
    @patch.object(VastClient, "_build_headers", return_value={})
    @patch.object(VastClient, "_build_url", return_value="https://example.com/api/v0/test")
    def test_put_calls_request(self, mock_url, mock_headers, mock_req):
        c = VastClient(api_key=None)
        c.put("/test", json_data={"b": 2})
        mock_req.assert_called_once_with("PUT", "https://example.com/api/v0/test", {}, {"b": 2}, timeout=None)

    @patch.object(VastClient, "_request")
    @patch.object(VastClient, "_build_headers", return_value={})
    @patch.object(VastClient, "_build_url", return_value="https://example.com/api/v0/test")
    def test_delete_calls_request(self, mock_url, mock_headers, mock_req):
        c = VastClient(api_key=None)
        c.delete("/test")
        mock_req.assert_called_once_with("DELETE", "https://example.com/api/v0/test", {}, {}, timeout=None)

    @patch.object(VastClient, "_request")
    @patch.object(VastClient, "_build_headers", return_value={})
    @patch.object(VastClient, "_build_url", return_value="https://example.com/api/v0/test")
    def test_post_defaults_json_to_empty_dict(self, mock_url, mock_headers, mock_req):
        c = VastClient(api_key=None)
        c.post("/test")
        mock_req.assert_called_once_with("POST", "https://example.com/api/v0/test", {}, {}, timeout=None)


class TestRetryLogic:
    @patch("vastai.api.client.time.sleep")
    @patch("vastai.api.client.VastSession")
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
    @patch("vastai.api.client.VastSession")
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
    @patch("vastai.api.client.VastSession")
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

    @patch("vastai.api.client.time.sleep")
    @patch("vastai.api.client.VastSession")
    def test_retries_on_503(self, mock_session_cls, mock_sleep):
        """503 (transient upstream error) should retry the same way 429 does."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.prepare_request.return_value = MagicMock()

        resp_503 = MagicMock(status_code=503)
        resp_200 = MagicMock(status_code=200)
        mock_session.send.side_effect = [resp_503, resp_200]

        c = VastClient(api_key=None, retry=3)
        result = c._request("GET", "https://example.com", {})

        assert result.status_code == 200
        assert mock_sleep.call_count == 1

    @patch("vastai.api.client.time.sleep")
    @patch("vastai.api.client.VastSession")
    def test_retries_on_502_and_504(self, mock_session_cls, mock_sleep):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.prepare_request.return_value = MagicMock()

        resp_502 = MagicMock(status_code=502)
        resp_504 = MagicMock(status_code=504)
        resp_200 = MagicMock(status_code=200)
        mock_session.send.side_effect = [resp_502, resp_504, resp_200]

        c = VastClient(api_key=None, retry=3)
        result = c._request("GET", "https://example.com", {})

        assert result.status_code == 200
        assert mock_session.send.call_count == 3

    @patch("vastai.api.client.time.sleep")
    @patch("vastai.api.client.VastSession")
    def test_retries_on_connection_error(self, mock_session_cls, mock_sleep):
        """First attempt raises ConnectionError; second succeeds."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.prepare_request.return_value = MagicMock()

        resp_200 = MagicMock(status_code=200)
        mock_session.send.side_effect = [
            requests.exceptions.ConnectionError("connection reset"),
            resp_200,
        ]

        c = VastClient(api_key=None, retry=3)
        result = c._request("GET", "https://example.com", {})

        assert result.status_code == 200
        assert mock_session.send.call_count == 2
        assert mock_sleep.call_count == 1

    @patch("vastai.api.client.time.sleep")
    @patch("vastai.api.client.VastSession")
    def test_timeout_exhausts_retries_raises(self, mock_session_cls, mock_sleep):
        """All attempts raise Timeout; the exception propagates (doesn't hang or return None)."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.prepare_request.return_value = MagicMock()

        mock_session.send.side_effect = requests.exceptions.ReadTimeout("read timed out")

        c = VastClient(api_key=None, retry=3)
        with pytest.raises(requests.exceptions.ReadTimeout):
            c._request("GET", "https://example.com", {})

        assert mock_session.send.call_count == 3

    @patch("vastai.api.client.VastSession")
    def test_non_retryable_exception_propagates_immediately(self, mock_session_cls):
        """InvalidURL etc. must not be retried — retrying them burns time for no reason."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.prepare_request.return_value = MagicMock()
        mock_session.send.side_effect = requests.exceptions.InvalidURL("bad url")

        c = VastClient(api_key=None, retry=3)
        with pytest.raises(requests.exceptions.InvalidURL):
            c._request("GET", "https://example.com", {})

        assert mock_session.send.call_count == 1

    @patch("vastai.api.client.VastSession")
    def test_timeout_is_passed_to_send(self, mock_session_cls):
        """The per-request timeout must actually reach session.send()."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.prepare_request.return_value = MagicMock()
        mock_session.send.return_value = MagicMock(status_code=200)

        c = VastClient(api_key=None, retry=1, timeout=45)
        c._request("GET", "https://example.com", {})

        _, kwargs = mock_session.send.call_args
        assert kwargs.get("timeout") == 45

    @patch("vastai.api.client.VastSession")
    def test_per_call_timeout_overrides_default(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.prepare_request.return_value = MagicMock()
        mock_session.send.return_value = MagicMock(status_code=200)

        c = VastClient(api_key=None, retry=1, timeout=120)
        c._request("GET", "https://example.com", {}, timeout=5)

        _, kwargs = mock_session.send.call_args
        assert kwargs.get("timeout") == 5


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


class TestAuthAcrossRedirects:
    """requests drops Authorization on a host change; our own hosts redirect across one."""

    def test_header_survives_a_redirect_within_our_domain(self):
        session = VastSession("https://candidate.vast.ai")
        prep = SimpleNamespace(
            url="https://candidate-server.vast.ai/api/v0/users/current/",
            headers={"Authorization": "Bearer mykey123"},
        )
        session.rebuild_auth(prep, None)
        assert prep.headers["Authorization"] == "Bearer mykey123"

    def test_header_is_dropped_when_a_redirect_leaves_our_domain(self):
        session = VastSession("https://console.vast.ai")
        prep = SimpleNamespace(
            url="https://elsewhere.example.com/api/v0/users/current/",
            headers={"Authorization": "Bearer mykey123"},
        )
        response = SimpleNamespace(
            request=SimpleNamespace(url="https://console.vast.ai/api/v0/users/current")
        )
        session.rebuild_auth(prep, response)
        assert "Authorization" not in prep.headers

    @pytest.mark.parametrize("a,b,same", [
        ("https://console.vast.ai", "https://console.vast.ai/x", True),
        ("https://candidate.vast.ai", "https://candidate-server.vast.ai/x", True),
        ("https://console.vast.ai", "https://evil.example.com/x", False),
        ("http://localhost:8080", "http://localhost:8080/x", True),
        ("https://console.vast.ai", "not-a-url", False),
    ])
    def test_domain_comparison(self, a, b, same):
        assert (domain_of(a) == domain_of(b)) is same


class TestCurlRendering:
    """--curl must print a command that actually runs."""

    def _prep(self, url, method="GET", json_data=None):
        req = requests.Request(
            method=method, url=url, json=json_data,
            headers={"User-Agent": "vastai-sdk/1.0", "Authorization": "Bearer mykey123"},
        )
        return requests.Session().prepare_request(req)

    def test_keeps_the_authorization_header(self):
        out = as_curl_command(self._prep("https://console.vast.ai/api/v0/instances/"))
        assert "-H 'Authorization: Bearer mykey123'" in out

    def test_drops_the_noise_headers(self):
        out = as_curl_command(self._prep("https://console.vast.ai/api/v0/instances/"))
        assert "User-Agent" not in out
        assert "Accept-Encoding" not in out

    def test_a_body_carrying_request_declares_json(self):
        # without this curl sends form encoding and the API answers 400
        out = as_curl_command(
            self._prep("https://console.vast.ai/api/v0/bundles/", "PUT", {"num_gpus": 1})
        )
        assert "-H 'Content-Type: application/json'" in out

    def test_a_get_declares_no_content_type(self):
        out = as_curl_command(self._prep("https://console.vast.ai/api/v0/instances/"))
        assert "Content-Type" not in out

    def test_a_url_without_query_args_does_not_raise(self):
        out = as_curl_command(self._prep("https://console.vast.ai/api/v0/users/current"))
        assert out.startswith("curl \\\n")
        assert "https://console.vast.ai/api/v0/users/current" in out

    def test_renders_a_body_carrying_request(self):
        out = as_curl_command(
            self._prep("https://console.vast.ai/api/v0/instances/", "PUT", {"label": "x"})
        )
        assert "-X PUT" in out
        assert '"label": "x"' in out
        assert "-H 'Authorization: Bearer mykey123'" in out

    def test_one_flag_per_line(self):
        out = as_curl_command(
            self._prep("https://console.vast.ai/api/v0/instances/", "PUT", {"label": "x"})
        )
        assert all(line.endswith("\\") for line in out.splitlines()[:-1])
