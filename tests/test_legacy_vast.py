"""Regression tests for the deprecated standalone ``vast.py`` client."""

import importlib.util
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

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


def _assert_owner_only(path):
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_migrates_legacy_api_key_securely(legacy_vast, tmp_path, monkeypatch):
    legacy_file = tmp_path / ".vast_api_key"
    key_file = tmp_path / "vast_api_key"
    legacy_file.write_bytes(b"legacy-key")
    legacy_file.chmod(0o644)
    monkeypatch.setattr(legacy_vast, "APIKEY_FILE_HOME", str(legacy_file))
    monkeypatch.setattr(legacy_vast, "APIKEY_FILE", str(key_file))

    legacy_vast._migrate_legacy_api_key()

    assert key_file.read_bytes() == b"legacy-key"
    assert not legacy_file.exists()
    _assert_owner_only(key_file)


def test_set_api_key_replaces_file_securely(legacy_vast, tmp_path, monkeypatch):
    key_file = tmp_path / "vast_api_key"
    key_file.write_bytes(b"old-key")
    key_file.chmod(0o644)
    monkeypatch.setattr(legacy_vast, "APIKEY_FILE", str(key_file))
    monkeypatch.setattr(legacy_vast, "APIKEY_FILE_HOME", str(tmp_path / ".vast_api_key"))

    legacy_vast.set__api_key(SimpleNamespace(new_api_key="new-key"))

    assert key_file.read_bytes() == b"new-key"
    _assert_owner_only(key_file)


def test_saves_backup_codes_securely(legacy_vast, tmp_path):
    backup_file = tmp_path / "codes.txt"
    backup_file.write_bytes(b"old-codes")
    backup_file.chmod(0o644)

    assert legacy_vast.save_to_file("new-codes", str(backup_file))

    assert backup_file.read_bytes() == b"new-codes"
    _assert_owner_only(backup_file)


def test_tfa_login_saves_session_key_securely(legacy_vast, tmp_path, monkeypatch):
    session_file = tmp_path / "vast_tfa_key"
    session_file.write_bytes(b"old-session")
    session_file.chmod(0o644)
    monkeypatch.setattr(legacy_vast, "TFAKEY_FILE", str(session_file))
    response = Mock()
    response.json.return_value = {"session_key": "new-session"}
    args = SimpleNamespace(
        api_key="api-key",
        backup_code=None,
        code="123456",
        method_id=None,
        method_type="totp",
        secret=None,
    )

    with (
        patch.object(legacy_vast, "apiurl", return_value="https://example.test/tfa"),
        patch.object(legacy_vast, "apiheaders", return_value={}),
        patch.object(legacy_vast, "http_post", return_value=response),
    ):
        legacy_vast.tfa__login(args)

    assert session_file.read_bytes() == b"new-session"
    _assert_owner_only(session_file)


def test_repairs_existing_credential_permissions(legacy_vast, tmp_path, monkeypatch):
    credential_files = [
        tmp_path / "vast_api_key",
        tmp_path / "vast_tfa_key",
        tmp_path / ".vast_api_key",
    ]
    for credential_file in credential_files:
        credential_file.write_bytes(b"secret")
        credential_file.chmod(0o644)

    monkeypatch.setattr(legacy_vast, "APIKEY_FILE", str(credential_files[0]))
    monkeypatch.setattr(legacy_vast, "TFAKEY_FILE", str(credential_files[1]))
    monkeypatch.setattr(legacy_vast, "APIKEY_FILE_HOME", str(credential_files[2]))

    legacy_vast._secure_existing_credentials()

    for credential_file in credential_files:
        _assert_owner_only(credential_file)
