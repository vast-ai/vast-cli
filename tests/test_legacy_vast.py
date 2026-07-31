"""Regression tests for the deprecated standalone ``vast.py`` client."""

import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest


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
