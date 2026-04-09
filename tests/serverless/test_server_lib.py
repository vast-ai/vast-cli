"""Tests for vastai.serverless.server.lib.server entrypoints."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from vastai.serverless.server.lib import server as server_lib


def test_start_server_invokes_asyncio_run_with_start_server_async() -> None:
    """start_server should delegate to asyncio.run(start_server_async(...))."""
    backend = MagicMock()
    routes = []

    with patch.object(server_lib, "run") as mock_run:
        server_lib.start_server(backend, routes, host="127.0.0.1", port=8080)

    mock_run.assert_called_once()
    (coro,) = mock_run.call_args[0]
    assert asyncio.iscoroutine(coro)
    coro.close()
