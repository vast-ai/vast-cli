"""The 401 hint must name the key that was actually sent, not the one on disk."""
from types import SimpleNamespace

import pytest

from vastai.cli.main import _emit_error


@pytest.fixture
def no_ambient_key(monkeypatch, tmp_path):
    monkeypatch.delenv("VAST_API_KEY", raising=False)
    monkeypatch.setattr("vastai.cli.main.APIKEY_FILE", str(tmp_path / "absent"))
    return tmp_path


def args(api_key=None, url=None):
    return SimpleNamespace(raw=False, api_key=api_key, url=url)


def test_names_the_command_line_key(no_ambient_key, capsys):
    _emit_error(args("cli-key-abcd", "https://candidate.vast.ai"), 401, "Invalid user key")
    err = capsys.readouterr().err
    assert "Sent key from --api-key (ends in ...abcd)" in err
    assert "https://candidate.vast.ai" in err


def test_command_line_key_outranks_the_env_var(no_ambient_key, monkeypatch, capsys):
    monkeypatch.setenv("VAST_API_KEY", "env-key-wxyz")
    _emit_error(args("cli-key-abcd"), 401, "Invalid user key")
    err = capsys.readouterr().err
    assert "--api-key (ends in ...abcd)" in err
    assert "wxyz" not in err


def test_env_var_is_still_named_when_it_is_the_source(no_ambient_key, monkeypatch, capsys):
    monkeypatch.setenv("VAST_API_KEY", "env-key-wxyz")
    _emit_error(args("env-key-wxyz"), 401, "Invalid user key")
    err = capsys.readouterr().err
    assert "$VAST_API_KEY (ends in ...wxyz)" in err


def test_file_is_still_named_when_it_is_the_source(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("VAST_API_KEY", raising=False)
    key_file = tmp_path / "vast_api_key"
    key_file.write_text("file-key-mnop")
    monkeypatch.setattr("vastai.cli.main.APIKEY_FILE", str(key_file))
    _emit_error(args("file-key-mnop"), 401, "Invalid user key")
    err = capsys.readouterr().err
    assert "Sent key from" in err and "...mnop" in err


def test_no_key_at_all_still_says_so(no_ambient_key, capsys):
    _emit_error(args(None), 401, "Invalid user key")
    assert "No API key is configured." in capsys.readouterr().err
