"""Unit tests for Backend session-related HTTP handlers (health, get).

Exercises request validation and session lookup without starting the worker or
binding real ports.
"""
from __future__ import annotations

import json

import pytest

from vastai.serverless.server.lib.backend import Backend


@pytest.mark.asyncio
async def test_session_health_handler_invalid_json_returns_422(
    pyworker_backend: Backend,
    make_backend_http_request,
    web_json_body,
) -> None:
    req = make_backend_http_request(
        json_side_effect=json.JSONDecodeError("msg", "doc", 0),
    )
    resp = await pyworker_backend.session_health_handler(req)
    assert resp.status == 422
    assert "invalid JSON" in web_json_body(resp).get("error", "")


@pytest.mark.asyncio
async def test_session_health_handler_missing_session_id_returns_422(
    pyworker_backend: Backend,
    make_backend_http_request,
    web_json_body,
) -> None:
    req = make_backend_http_request(json_data={})
    resp = await pyworker_backend.session_health_handler(req)
    assert resp.status == 422
    assert "session_id" in web_json_body(resp).get("error", "")


@pytest.mark.asyncio
async def test_session_health_handler_unknown_session_returns_ok_false(
    pyworker_backend: Backend,
    make_backend_http_request,
    web_json_body,
) -> None:
    req = make_backend_http_request(json_data={"session_id": "missing"})
    resp = await pyworker_backend.session_health_handler(req)
    assert resp.status == 200
    assert web_json_body(resp) == {"ok": False}


@pytest.mark.asyncio
async def test_session_health_handler_valid_auth_returns_ok_true(
    pyworker_backend: Backend,
    make_backend_http_request,
    make_pyworker_session,
    web_json_body,
) -> None:
    pyworker_backend.sessions["s1"] = make_pyworker_session(
        session_id="s1",
        lifetime=1.0,
        auth_data={"token": "abc"},
    )
    req = make_backend_http_request(
        json_data={
            "session_id": "s1",
            "session_auth": {"token": "abc"},
        }
    )
    resp = await pyworker_backend.session_health_handler(req)
    assert resp.status == 200
    assert web_json_body(resp) == {"ok": True}


@pytest.mark.asyncio
async def test_session_health_handler_wrong_auth_returns_401(
    pyworker_backend: Backend,
    make_backend_http_request,
    make_pyworker_session,
    web_json_body,
) -> None:
    pyworker_backend.sessions["s1"] = make_pyworker_session(
        session_id="s1",
        lifetime=1.0,
        auth_data={"token": "good"},
    )
    req = make_backend_http_request(
        json_data={
            "session_id": "s1",
            "session_auth": {"token": "bad"},
        }
    )
    resp = await pyworker_backend.session_health_handler(req)
    assert resp.status == 401
    assert "session_auth" in web_json_body(resp).get("error", "")


@pytest.mark.asyncio
async def test_session_get_handler_unknown_session_returns_400(
    pyworker_backend: Backend,
    make_backend_http_request,
) -> None:
    req = make_backend_http_request(
        json_data={"session_id": "nope", "session_auth": {}},
    )
    resp = await pyworker_backend.session_get_handler(req)
    assert resp.status == 400


@pytest.mark.asyncio
async def test_session_get_handler_returns_session_fields_when_valid(
    pyworker_backend: Backend,
    make_backend_http_request,
    make_pyworker_session,
    web_json_body,
) -> None:
    pyworker_backend.sessions["s2"] = make_pyworker_session(
        session_id="s2",
        lifetime=30.0,
        auth_data={"k": "v"},
        expiration=99.0,
        on_close_route="/cb",
        on_close_payload={"x": 1},
    )
    req = make_backend_http_request(
        json_data={
            "session_id": "s2",
            "session_auth": {"k": "v"},
        }
    )
    resp = await pyworker_backend.session_get_handler(req)
    assert resp.status == 200
    data = web_json_body(resp)
    assert data["session_id"] == "s2"
    assert data["auth_data"] == {"k": "v"}
    assert data["lifetime"] == 30.0
    assert data["expiration"] == 99.0
    assert data["on_close_route"] == "/cb"
    assert data["on_close_payload"] == {"x": 1}
