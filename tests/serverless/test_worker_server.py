"""Unit tests for the serverless pyworker server Worker class.

Tests Worker initialization (backend and routes), run_async, and run.
All server startup and backend behavior is mocked; no real network or server.
"""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vastai.serverless.server.worker import (
    Worker,
    WorkerConfig,
    HandlerConfig,
    BenchmarkConfig,
    LogActionConfig,
)
from vastai.serverless.server.lib.data_types import LogAction
from vastai.serverless.server.lib import backend as backend_mod
from vastai.serverless.server.lib import server as server_mod


# ---------------------------------------------------------------------------
# Worker initialization and run
# ---------------------------------------------------------------------------


class TestWorker:
    """Verify Worker builds backend/routes and run_async/run call server correctly."""

    def test_worker_init_creates_backend_with_config_values(self, worker_config_with_handler) -> None:
        """
        Verifies that Worker.__init__ creates Backend with url, log file, benchmark handler,
        log_actions, healthcheck_url, and max_sessions from WorkerConfig.

        This test verifies by:
        1. Building a WorkerConfig with handler and benchmark via worker_config_with_handler
        2. Patching backend.Backend to a MagicMock
        3. Instantiating Worker(config)
        4. Asserting Backend was called once with the expected keyword arguments

        Assumptions:
        - worker_config_with_handler yields a config with one handler that has BenchmarkConfig
        - Backend is constructed in Worker.__init__ with these arguments
        """
        config = worker_config_with_handler(
            route="/predict",
            dataset=[{"input": "test"}],
        )
        config.model_log_file = "/tmp/model.log"
        config.model_healthcheck_url = "/health"
        config.max_sessions = 5
        config.log_action_config = LogActionConfig(on_load=["Loaded"])

        with patch.object(backend_mod, "Backend", MagicMock()) as mock_backend_class:
            worker = Worker(config)

        mock_backend_class.assert_called_once()
        call_kw = mock_backend_class.call_args[1]
        assert call_kw["model_server_url"] == "http://localhost:8000"
        assert call_kw["model_log_file"] == "/tmp/model.log"
        assert call_kw["benchmark_handler"] is not None
        assert call_kw["healthcheck_url"] == "/health"
        assert call_kw["max_sessions"] == 5
        assert call_kw["log_actions"] == [(LogAction.ModelLoaded, "Loaded")]

    def test_worker_init_creates_routes_for_each_handler(self, worker_config_with_handler) -> None:
        """
        Verifies that Worker attaches one route per handler via backend.create_handler.

        This test verifies by:
        1. Using config with one handler at /predict
        2. Patching Backend so the instance's create_handler returns a mock
        3. Instantiating Worker and asserting len(worker.routes) == 1

        Assumptions:
        - Each (route_path, handler) gets one web.post(route_path, backend.create_handler(handler))
        """
        config = worker_config_with_handler(route="/predict", dataset=[{"x": 1}])
        with patch.object(backend_mod, "Backend", MagicMock()) as mock_backend_class:
            mock_backend = MagicMock()
            mock_backend_class.return_value = mock_backend
            worker = Worker(config)

        assert len(worker.routes) == 1
        assert worker.backend is mock_backend

    @pytest.mark.asyncio
    async def test_worker_run_async_calls_start_server_async(
        self, worker_config_with_handler
    ) -> None:
        """
        Verifies that Worker.run_async calls server.start_server_async with backend and routes.

        This test verifies by:
        1. Creating Worker with mocked Backend
        2. Patching server.start_server_async with AsyncMock
        3. Calling await worker.run_async(host="0.0.0.0")
        4. Asserting start_server_async was called once with backend, routes, and kwargs

        Assumptions:
        - No real server is started; start_server_async is fully mocked
        """
        config = worker_config_with_handler(route="/", dataset=[{"a": 1}])
        with patch.object(backend_mod, "Backend", MagicMock()):
            worker = Worker(config)
        with patch.object(
            server_mod, "start_server_async", new_callable=AsyncMock
        ) as mock_start:
            await worker.run_async(host="0.0.0.0")

        mock_start.assert_called_once()
        assert mock_start.call_args[0][0] is worker.backend
        assert mock_start.call_args[0][1] is worker.routes
        assert mock_start.call_args[1].get("host") == "0.0.0.0"

    def test_worker_run_calls_start_server(self, worker_config_with_handler) -> None:
        """
        Verifies that Worker.run calls server.start_server with backend and routes.

        This test verifies by:
        1. Creating Worker with mocked Backend
        2. Patching server.start_server (sync) with MagicMock
        3. Calling worker.run()
        4. Asserting start_server was called once with backend and routes

        Assumptions:
        - start_server runs the event loop; we mock it so no server starts
        """
        config = worker_config_with_handler(route="/", dataset=[{"a": 1}])
        with patch.object(backend_mod, "Backend", MagicMock()):
            worker = Worker(config)
        with patch.object(server_mod, "start_server", MagicMock()) as mock_start:
            worker.run()

        mock_start.assert_called_once()
        assert mock_start.call_args[0][0] is worker.backend
        assert mock_start.call_args[0][1] is worker.routes

    def test_worker_init_sets_handler_level_when_root_has_handlers(
        self, worker_config_with_handler
    ) -> None:
        """
        Verifies that Worker.__init__ sets level on existing root logger handlers when present.

        This test verifies by:
        1. Patching logging.getLogger to return a root logger with existing handlers (mocks)
        2. Patching backend.Backend and instantiating Worker
        3. Asserting each existing handler's setLevel was called with logging.DEBUG

        Assumptions:
        - When root_logger.handlers is non-empty, Worker uses the else branch and sets level on each
        """
        config = worker_config_with_handler(route="/", dataset=[{"a": 1}])
        mock_handler = MagicMock()
        mock_root = MagicMock()
        mock_root.handlers = [mock_handler]
        mock_root.setLevel = MagicMock()

        with patch.object(backend_mod, "Backend", MagicMock()):
            with patch("vastai.serverless.server.worker.logging.getLogger", return_value=mock_root):
                Worker(config)

        mock_handler.setLevel.assert_called_once_with(logging.DEBUG)

