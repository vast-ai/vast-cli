import asyncio
import collections
import io
import logging
import ssl

import pytest

from vastai.serverless.ui import server as ui
from . import fake_vast


@pytest.fixture
def logs():
    stream = io.StringIO()
    handler = ui.configure_logging(stream)
    yield stream
    logging.getLogger().removeHandler(handler)


@pytest.fixture(autouse=True)
async def fresh_server_state(monkeypatch):
    """The server keeps some state at module level: each test starts with it empty, and its
    background lookups end with it, so one test's leftovers can't fail another."""
    monkeypatch.setattr(ui, "_loads", collections.Counter())
    monkeypatch.setattr(ui, "_watches", collections.Counter())
    ui.KNOWN_WORKERS.clear()
    ui._learned_at.clear()
    yield
    for task in list(ui._background):
        task.cancel()
    await asyncio.gather(*ui._background, return_exceptions=True)


@pytest.fixture(autouse=True)
def offline_ssl(monkeypatch):
    async def default_context():
        return ssl.create_default_context()
    monkeypatch.setattr(ui, "vast_ssl_context", default_context)


@pytest.fixture
async def vast_api(aiohttp_server):
    state = fake_vast.initial_state()
    server = await aiohttp_server(fake_vast.make_app(state))
    server.state = state
    return server


@pytest.fixture
async def client(aiohttp_client, vast_api):
    base = str(vast_api.make_url("")).rstrip("/")
    return await aiohttp_client(ui.make_app(base, autoscaler_url=base))
