"""Unit tests for vastai.serverless.client.endpoint module.

Tests for Endpoint and RouteResponse classes.
These tests focus on synchronous initialization and validation code.
"""

import pytest
from unittest.mock import MagicMock
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vastai.serverless.client.endpoint import Endpoint, RouteResponse


class TestEndpointInit:
    """Tests for Endpoint class __init__ method."""

    def test_raises_on_none_client(self):
        """Test that None client raises ValueError."""
        with pytest.raises(ValueError, match="cannot be created without client"):
            Endpoint(client=None, name="test", id=1, api_key="key")

    def test_raises_on_empty_name(self):
        """Test that empty string name raises ValueError."""
        mock_client = MagicMock()
        with pytest.raises(ValueError, match="name cannot be empty"):
            Endpoint(client=mock_client, name="", id=1, api_key="key")

    def test_raises_on_falsy_name(self):
        """Test that falsy name (None) raises ValueError."""
        mock_client = MagicMock()
        with pytest.raises(ValueError, match="name cannot be empty"):
            Endpoint(client=mock_client, name=None, id=1, api_key="key")

    def test_raises_on_none_id(self):
        """Test that None id raises ValueError."""
        mock_client = MagicMock()
        with pytest.raises(ValueError, match="id cannot be empty"):
            Endpoint(client=mock_client, name="test", id=None, api_key="key")

    def test_valid_instantiation_stores_attributes(self):
        """Test that valid instantiation stores all attributes correctly."""
        mock_client = MagicMock()
        endpoint = Endpoint(
            client=mock_client,
            name="my-endpoint",
            id=123,
            api_key="secret_api_key"
        )
        assert endpoint.client is mock_client
        assert endpoint.name == "my-endpoint"
        assert endpoint.id == 123
        assert endpoint.api_key == "secret_api_key"

    def test_zero_id_is_valid(self):
        """Test that id=0 is valid (not None)."""
        mock_client = MagicMock()
        endpoint = Endpoint(client=mock_client, name="test", id=0, api_key="key")
        assert endpoint.id == 0

    def test_negative_id_is_valid(self):
        """Test that negative id is stored (no validation against negative)."""
        mock_client = MagicMock()
        endpoint = Endpoint(client=mock_client, name="test", id=-5, api_key="key")
        assert endpoint.id == -5


class TestEndpointRepr:
    """Tests for Endpoint __repr__ method."""

    def test_repr_format(self):
        """Test __repr__ returns expected string format."""
        mock_client = MagicMock()
        endpoint = Endpoint(client=mock_client, name="test-ep", id=42, api_key="key")
        assert repr(endpoint) == "<Endpoint test-ep (id=42)>"

    def test_repr_with_long_name(self):
        """Test __repr__ handles long endpoint names."""
        mock_client = MagicMock()
        endpoint = Endpoint(
            client=mock_client,
            name="very-long-endpoint-name-for-testing",
            id=999,
            api_key="key"
        )
        assert repr(endpoint) == "<Endpoint very-long-endpoint-name-for-testing (id=999)>"

    def test_repr_with_special_chars_in_name(self):
        """Test __repr__ handles special characters in name."""
        mock_client = MagicMock()
        endpoint = Endpoint(client=mock_client, name="my_test.endpoint", id=1, api_key="key")
        assert repr(endpoint) == "<Endpoint my_test.endpoint (id=1)>"


class TestRouteResponseStatusReady:
    """Tests for RouteResponse when URL is present (READY status)."""

    def test_status_ready_when_url_present(self):
        """Test that presence of 'url' in body sets status to READY."""
        body = {"url": "https://worker.example.com", "request_idx": 5}
        response = RouteResponse(body)
        assert response.status == "READY"

    def test_request_idx_extracted_when_present(self):
        """Test request_idx is extracted from body when present."""
        body = {"url": "https://worker.example.com", "request_idx": 42}
        response = RouteResponse(body)
        assert response.request_idx == 42

    def test_body_stored_when_ready(self):
        """Test that body dict is stored."""
        body = {"url": "https://worker.example.com", "extra": "data"}
        response = RouteResponse(body)
        assert response.body == body


class TestRouteResponseStatusWaiting:
    """Tests for RouteResponse when URL is NOT present (WAITING status)."""

    def test_status_waiting_when_no_url(self):
        """Test that absence of 'url' in body sets status to WAITING."""
        body = {"request_idx": 3}
        response = RouteResponse(body)
        assert response.status == "WAITING"

    def test_request_idx_extracted_when_waiting(self):
        """Test request_idx is extracted from body when in waiting status."""
        body = {"request_idx": 7}
        response = RouteResponse(body)
        assert response.request_idx == 7

    def test_body_stored_when_waiting(self):
        """Test that body dict is stored when waiting."""
        body = {"request_idx": 3, "other": "info"}
        response = RouteResponse(body)
        assert response.body == body


class TestRouteResponseRequestIdx:
    """Tests for RouteResponse request_idx handling."""

    def test_request_idx_defaults_to_zero(self):
        """Test request_idx defaults to 0 when not in body."""
        body = {}
        response = RouteResponse(body)
        assert response.request_idx == 0

    def test_request_idx_zero_when_explicit(self):
        """Test request_idx=0 when explicitly set."""
        body = {"request_idx": 0}
        response = RouteResponse(body)
        assert response.request_idx == 0

    def test_request_idx_large_value(self):
        """Test request_idx with large value."""
        body = {"request_idx": 999999}
        response = RouteResponse(body)
        assert response.request_idx == 999999


class TestRouteResponseRepr:
    """Tests for RouteResponse __repr__ method."""

    def test_repr_format_ready(self):
        """Test __repr__ returns expected format for READY status."""
        body = {"url": "https://test.com"}
        response = RouteResponse(body)
        assert repr(response) == "<RouteResponse status=READY>"

    def test_repr_format_waiting(self):
        """Test __repr__ returns expected format for WAITING status."""
        body = {}
        response = RouteResponse(body)
        assert repr(response) == "<RouteResponse status=WAITING>"


class TestRouteResponseGetUrl:
    """Tests for RouteResponse.get_url() method."""

    def test_get_url_returns_url_from_body(self):
        """Test get_url() returns url from body when present."""
        body = {"url": "https://example.com/worker"}
        response = RouteResponse(body)
        assert response.get_url() == "https://example.com/worker"

    def test_get_url_none_when_missing(self):
        """Test get_url() returns None when url not in body."""
        body = {}
        response = RouteResponse(body)
        assert response.get_url() is None

    def test_get_url_with_complex_url(self):
        """Test get_url() with complex URL including path and query."""
        body = {"url": "https://worker-123.vast.ai:8080/inference?model=gpt"}
        response = RouteResponse(body)
        assert response.get_url() == "https://worker-123.vast.ai:8080/inference?model=gpt"

    def test_get_url_empty_string(self):
        """Test get_url() when url is empty string."""
        body = {"url": ""}
        response = RouteResponse(body)
        assert response.get_url() == ""


class TestEndpointRequest:
    """Tests for Endpoint.request() method delegation."""

    def test_request_delegates_to_client(self):
        """Test that request() delegates to client.queue_endpoint_request()."""
        mock_client = MagicMock()
        endpoint = Endpoint(client=mock_client, name="test", id=1, api_key="key")

        endpoint.request("/route", {"data": "value"})

        mock_client.queue_endpoint_request.assert_called_once()
        call_kwargs = mock_client.queue_endpoint_request.call_args[1]
        assert call_kwargs["endpoint"] is endpoint
        assert call_kwargs["worker_route"] == "/route"
        assert call_kwargs["worker_payload"] == {"data": "value"}

    def test_request_passes_optional_params(self):
        """Test that request() passes optional parameters."""
        mock_client = MagicMock()
        endpoint = Endpoint(client=mock_client, name="test", id=1, api_key="key")

        endpoint.request("/route", {"data": "value"}, cost=200, retry=False, stream=True)

        call_kwargs = mock_client.queue_endpoint_request.call_args[1]
        assert call_kwargs["cost"] == 200
        assert call_kwargs["retry"] is False
        assert call_kwargs["stream"] is True


class TestEndpointGetWorkers:
    """Tests for Endpoint.get_workers() method delegation."""

    def test_get_workers_delegates_to_client(self):
        """Test that get_workers() delegates to client.get_endpoint_workers()."""
        mock_client = MagicMock()
        endpoint = Endpoint(client=mock_client, name="test", id=1, api_key="key")

        endpoint.get_workers()

        mock_client.get_endpoint_workers.assert_called_once_with(endpoint)
