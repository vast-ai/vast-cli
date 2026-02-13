"""Unit tests for vastai.serverless.client.client module.

Tests for ServerlessRequest and Serverless class instantiation/configuration.
These tests focus on synchronous initialization code that does NOT require
actual network calls or async execution.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch, PropertyMock
import sys
import time
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vastai.serverless.client.client import Serverless, ServerlessRequest


@pytest.fixture
def event_loop_for_request():
    """Create an event loop for ServerlessRequest tests (Future requires event loop)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    asyncio.set_event_loop(None)


class TestServerlessRequest:
    """Tests for ServerlessRequest class."""

    def test_init_defaults(self, event_loop_for_request):
        """Test ServerlessRequest initializes with expected defaults."""
        before_time = time.time()
        req = ServerlessRequest()
        after_time = time.time()

        assert req.status == "New"
        assert req.start_time is None
        assert req.complete_time is None
        assert req.req_idx == 0
        # create_time should be between before and after test execution
        assert before_time <= req.create_time <= after_time

    def test_init_status_is_new(self, event_loop_for_request):
        """Test that initial status is always 'New'."""
        req = ServerlessRequest()
        assert req.status == "New"

    def test_then_returns_self(self, event_loop_for_request):
        """Test that then() method returns self for chaining."""
        req = ServerlessRequest()
        callback = MagicMock()
        result = req.then(callback)
        assert result is req

    def test_then_callback_called_on_result(self, event_loop_for_request):
        """Test that callback is called when result is set."""
        req = ServerlessRequest()
        callback = MagicMock()
        req.then(callback)

        test_data = {"test": "data", "value": 123}
        req.set_result(test_data)
        # Run pending callbacks
        event_loop_for_request.run_until_complete(asyncio.sleep(0))

        callback.assert_called_once_with(test_data)

    def test_then_callback_not_called_on_exception(self, event_loop_for_request):
        """Test that callback is NOT called when exception is set."""
        req = ServerlessRequest()
        callback = MagicMock()
        req.then(callback)

        # Set exception instead of result
        req.set_exception(ValueError("test error"))
        # Run pending callbacks
        event_loop_for_request.run_until_complete(asyncio.sleep(0))

        # Callback should not be called for exceptions
        callback.assert_not_called()

    def test_multiple_then_callbacks(self, event_loop_for_request):
        """Test that multiple callbacks can be chained."""
        req = ServerlessRequest()
        callback1 = MagicMock()
        callback2 = MagicMock()

        req.then(callback1).then(callback2)

        test_data = {"result": "success"}
        req.set_result(test_data)
        # Run pending callbacks
        event_loop_for_request.run_until_complete(asyncio.sleep(0))

        callback1.assert_called_once_with(test_data)
        callback2.assert_called_once_with(test_data)


class TestServerlessInit:
    """Tests for Serverless class __init__ method."""

    def test_raises_on_none_api_key(self):
        """Test that None api_key raises AttributeError."""
        with pytest.raises(AttributeError, match="API key missing"):
            Serverless(api_key=None)

    def test_raises_on_empty_api_key(self):
        """Test that empty string api_key raises AttributeError."""
        with pytest.raises(AttributeError, match="API key missing"):
            Serverless(api_key="")

    def test_valid_api_key_stored(self):
        """Test that valid api_key is stored correctly."""
        client = Serverless(api_key="test_api_key_123")
        assert client.api_key == "test_api_key_123"

    def test_prod_instance_url(self):
        """Test instance='prod' sets autoscaler_url to production URL."""
        client = Serverless(api_key="test_key", instance="prod")
        assert client.autoscaler_url == "https://run.vast.ai"

    def test_alpha_instance_url(self):
        """Test instance='alpha' sets autoscaler_url to alpha URL."""
        client = Serverless(api_key="test_key", instance="alpha")
        assert client.autoscaler_url == "https://run-alpha.vast.ai"

    def test_local_instance_url(self):
        """Test instance='local' sets autoscaler_url to localhost."""
        client = Serverless(api_key="test_key", instance="local")
        assert client.autoscaler_url == "http://localhost:8080"

    def test_unknown_instance_defaults_to_prod(self):
        """Test that unknown instance value defaults to production URL."""
        client = Serverless(api_key="test_key", instance="unknown_value")
        assert client.autoscaler_url == "https://run.vast.ai"

    def test_connection_limit_stored(self):
        """Test that connection_limit is stored correctly."""
        client = Serverless(api_key="test_key", connection_limit=100)
        assert client.connection_limit == 100

    def test_default_connection_limit(self):
        """Test default connection_limit value."""
        client = Serverless(api_key="test_key")
        assert client.connection_limit == 500

    def test_default_request_timeout_stored_as_float(self):
        """Test that default_request_timeout is stored as float."""
        client = Serverless(api_key="test_key", default_request_timeout=120)
        assert client.default_request_timeout == 120.0
        assert isinstance(client.default_request_timeout, float)

    def test_max_poll_interval_stored_as_float(self):
        """Test that max_poll_interval is stored as float."""
        client = Serverless(api_key="test_key", max_poll_interval=30)
        assert client.max_poll_interval == 30.0
        assert isinstance(client.max_poll_interval, float)

    def test_debug_true_sets_logger_level(self):
        """Test debug=True sets logger to DEBUG level."""
        client = Serverless(api_key="test_key", debug=True)
        assert client.logger.level == logging.DEBUG

    def test_debug_false_uses_null_handler(self):
        """Test debug=False adds NullHandler (no output)."""
        client = Serverless(api_key="test_key", debug=False)
        # Logger should have handlers, and at least one should be NullHandler
        handlers = client.logger.handlers
        assert any(isinstance(h, logging.NullHandler) for h in handlers)

    def test_session_initially_none(self):
        """Test that _session is None after initialization."""
        client = Serverless(api_key="test_key")
        assert client._session is None

    def test_ssl_context_initially_none(self):
        """Test that _ssl_context is None after initialization."""
        client = Serverless(api_key="test_key")
        assert client._ssl_context is None


class TestServerlessIsOpen:
    """Tests for Serverless.is_open() method."""

    def test_returns_false_when_session_is_none(self):
        """Test is_open() returns False when _session is None."""
        client = Serverless(api_key="test_key")
        assert client._session is None
        assert client.is_open() is False

    def test_returns_true_when_session_open(self):
        """Test is_open() returns True when session exists and not closed."""
        client = Serverless(api_key="test_key")

        # Create a mock session that is not closed
        mock_session = MagicMock()
        mock_session.closed = False
        client._session = mock_session

        assert client.is_open() is True

    def test_returns_false_when_session_closed(self):
        """Test is_open() returns False when session is closed."""
        client = Serverless(api_key="test_key")

        # Create a mock session that IS closed
        mock_session = MagicMock()
        mock_session.closed = True
        client._session = mock_session

        assert client.is_open() is False


class TestServerlessGetAvgRequestTime:
    """Tests for Serverless.get_avg_request_time() method."""

    def test_returns_60_hardcoded(self):
        """Test get_avg_request_time() returns 60.0 (hardcoded value)."""
        client = Serverless(api_key="test_key")
        result = client.get_avg_request_time()
        assert result == 60.0
        assert isinstance(result, float)


class TestServerlessConstants:
    """Tests for Serverless class constants."""

    def test_ssl_cert_url(self):
        """Test SSL_CERT_URL constant value."""
        assert Serverless.SSL_CERT_URL == "https://console.vast.ai/static/jvastai_root.cer"

    def test_vast_web_url(self):
        """Test VAST_WEB_URL constant value."""
        assert Serverless.VAST_WEB_URL == "https://console.vast.ai"

    def test_vast_serverless_url(self):
        """Test VAST_SERVERLESS_URL constant value."""
        assert Serverless.VAST_SERVERLESS_URL == "https://run.vast.ai"


class TestServerlessLatencies:
    """Tests for latencies deque initialization."""

    def test_latencies_initialized_empty(self):
        """Test that latencies deque is empty after init."""
        client = Serverless(api_key="test_key")
        assert len(client.latencies) == 0

    def test_latencies_maxlen_is_50(self):
        """Test that latencies deque has maxlen of 50."""
        client = Serverless(api_key="test_key")
        assert client.latencies.maxlen == 50
