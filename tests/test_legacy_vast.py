"""Regression tests for the deprecated standalone ``vast.py`` client."""

import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from requests.exceptions import HTTPError


@pytest.fixture(scope="module")
def legacy_vast(tmp_path_factory):
    """Load vast.py without touching the user's real configuration paths."""
    temp_home = tmp_path_factory.mktemp("legacy-vast-home")
    module_path = Path(__file__).parents[1] / "vast.py"
    original_expanduser = os.path.expanduser
    cache_dir = temp_home / ".cache" / "vastai"
    cache_dir.mkdir(parents=True)
    (cache_dir / "gpu_names_cache.json").write_text(
        json.dumps({"gpu_names": ["Test GPU"]})
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(temp_home / ".config"))
        monkeypatch.setenv("XDG_CACHE_HOME", str(temp_home / ".cache"))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: temp_home))
        monkeypatch.setattr(
            os.path,
            "expanduser",
            lambda path: str(temp_home / path[2:])
            if path.startswith("~/")
            else original_expanduser(path),
        )
        spec = importlib.util.spec_from_file_location("legacy_vast", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

    return module


def test_http_request_adds_bearer_header_when_headers_are_omitted(legacy_vast):
    args = SimpleNamespace(api_key="secret", retry=1, explain=False, curl=False)
    legacy_vast.ARGS = args
    response = SimpleNamespace(status_code=200)

    with patch.object(legacy_vast.requests.Session, "send", return_value=response) as send:
        result = legacy_vast.http_get(args, "https://example.test/api/v0/instances")

    prepared_request = send.call_args.args[0]
    assert result is response
    assert prepared_request.headers["Authorization"] == "Bearer secret"
    assert "api_key" not in prepared_request.url


def test_http_request_adds_bearer_header_when_headers_are_empty(legacy_vast):
    # library-style callers pass the module-level `headers` global, which is
    # empty when main() never ran; they used to rely on the api_key query param
    args = SimpleNamespace(api_key="secret", retry=1, explain=False, curl=False)
    legacy_vast.ARGS = args
    response = SimpleNamespace(status_code=200)

    with patch.object(legacy_vast.requests.Session, "send", return_value=response) as send:
        legacy_vast.http_get(
            args,
            "https://example.test/api/v0/instances",
            headers={},
        )

    prepared_request = send.call_args.args[0]
    assert prepared_request.headers["Authorization"] == "Bearer secret"
    assert "api_key" not in prepared_request.url


def test_http_request_preserves_explicit_headers(legacy_vast):
    args = SimpleNamespace(api_key="secret", retry=1, explain=False, curl=False)
    legacy_vast.ARGS = args
    response = SimpleNamespace(status_code=200)
    explicit_headers = {"Authorization": "Bearer override"}

    with patch.object(legacy_vast.requests.Session, "send", return_value=response) as send:
        legacy_vast.http_get(
            args,
            "https://example.test/api/v0/instances",
            headers=explicit_headers,
        )

    prepared_request = send.call_args.args[0]
    assert prepared_request.headers["Authorization"] == "Bearer override"


def test_http_request_does_not_retry_search_quota_429(legacy_vast):
    args = SimpleNamespace(api_key="secret", retry=3, explain=False, curl=False)
    legacy_vast.ARGS = args
    response = SimpleNamespace(status_code=429, json=lambda: {"error": "search_quota_exceeded"})

    with patch.object(legacy_vast.requests.Session, "send", return_value=response) as send:
        result = legacy_vast.http_post(args, "https://example.test/api/v0/bundles/")

    assert result is response
    assert send.call_count == 1


def test_http_request_waits_retry_after_on_429(legacy_vast):
    args = SimpleNamespace(api_key="secret", retry=3, explain=False, curl=False)
    legacy_vast.ARGS = args
    limited = SimpleNamespace(status_code=429, headers={"Retry-After": "2"}, json=lambda: {})
    ok = SimpleNamespace(status_code=200)

    with patch.object(legacy_vast.requests.Session, "send", side_effect=[limited, ok]), \
         patch.object(legacy_vast.time, "sleep") as sleep:
        result = legacy_vast.http_get(args, "https://example.test/api/v0/instances")

    assert result is ok
    sleep.assert_called_once_with(2.0)


@pytest.mark.parametrize("status,state", [(202, "cancelling"), (200, "cancelling"),
                                        (200, "cancelled"), (200, "done"), (200, "failed")])
def test_cancel_copy_id(legacy_vast, mock_response, capsys, status, state):
    cp_id = "cp_0123456789abcdef"
    args = SimpleNamespace(dst=cp_id, api_key=None, url="https://example.test", explain=False)
    response = mock_response(status, {"success": True, "cp_id": cp_id, "state": state})
    with patch.object(legacy_vast, "http_del", return_value=response) as delete:
        legacy_vast.cancel__copy(args)
    assert delete.call_args.args[1] == f"https://example.test/api/v0/copies/{cp_id}/"
    assert "json" not in delete.call_args.kwargs
    assert f"Copy {cp_id}: {state}" in capsys.readouterr().out


@pytest.mark.parametrize("extra", [{}, {"cp_id": "cp_0123456789abcdef", "state": "cancelling"}])
@pytest.mark.parametrize("dst_id", [12371, "12371"])
def test_cancel_copy_legacy_instance_id(legacy_vast, mock_response, capsys, extra, dst_id):
    args = SimpleNamespace(dst=dst_id, api_key=None, url="https://example.test", explain=False)
    with patch.object(legacy_vast, "http_del", return_value=mock_response(200, {"success": True, **extra})) as delete:
        legacy_vast.cancel__copy(args)
    assert delete.call_args.args[1] == "https://example.test/api/v0/commands/copy_direct/"
    assert delete.call_args.kwargs["json"] == {"client_id": "me", "dst_id": dst_id}
    out = capsys.readouterr().out
    assert "Remote copy canceled" not in out
    if extra:
        assert "Copy cp_0123456789abcdef: cancelling" in out


def test_copy_prints_id(legacy_vast, mock_response, capsys):
    args = SimpleNamespace(src="123:/data", dst="456:/data", api_key=None,
                           url="https://example.test", explain=False)
    with patch.object(legacy_vast, "http_put", return_value=mock_response(200, {
        "success": True, "cp_id": "cp_0123456789abcdef",
    })):
        legacy_vast.copy(args)
    assert "cp_0123456789abcdef" in capsys.readouterr().out


@pytest.mark.parametrize("command", ["copy", "clone__volume"])
def test_copy_conflict_prints_holder(legacy_vast, mock_response, capsys, command):
    cp_id = "cp_0123456789abcdef"
    args = SimpleNamespace(src="V.123:/data", dst="C.456:/data", api_key=None,
                           source=123, dest=456, size=None, disable_compression=False,
                           url="https://example.test", explain=False, raw=False)
    args.func = getattr(legacy_vast, command)
    response = mock_response(409, {
        "error": "copy_in_progress", "cp_id": cp_id, "holder": {"cp_id": cp_id, "state": "running"},
    })
    with patch.object(legacy_vast, "http_put", return_value=response), \
         patch.object(legacy_vast, "http_post", return_value=response), \
         patch.object(legacy_vast, "TABCOMPLETE", False), \
         patch.object(legacy_vast, "parser") as parser:
        parser.parse_args.return_value = args
        legacy_vast.main()
    out = capsys.readouterr().out
    assert f"Copy {cp_id} (running)" in out
    assert f"vastai cancel copy {cp_id}" in out


def test_cancel_copy_not_found(legacy_vast, mock_response):
    args = SimpleNamespace(dst="cp_0123456789abcdef", api_key=None,
                           url="https://example.test", explain=False)
    with patch.object(legacy_vast, "http_del", return_value=mock_response(404, {"error": "not_found"})):
        with pytest.raises(HTTPError):
            legacy_vast.cancel__copy(args)
