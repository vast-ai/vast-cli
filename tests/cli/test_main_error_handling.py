"""Tests for error handling in vastai/cli/main.py: the 2FA session-expiry
retry logic (CLN-3555) and _emit_error's client/host 401 hint (CLN-3582)."""

import argparse
import io
from contextlib import redirect_stderr
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import HTTPError

from vastai.cli.main import _emit_error, _is_tfa_session_expired, run_command


def _http_error(status_code, msg):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"msg": msg}
    return HTTPError(response=resp)


def _args(*, raw=False, func=None):
    return argparse.Namespace(raw=raw, func=func)


def _host_command_func(command_name):
    """A stand-in for args.func: mysignature is the registered subparser."""
    sp = SimpleNamespace(host_only=True, command_name=command_name)
    func = lambda a: None  # noqa: E731
    func.mysignature = sp
    return func


def _client_command_func(command_name):
    sp = SimpleNamespace(host_only=False, command_name=command_name)
    func = lambda a: None  # noqa: E731
    func.mysignature = sp
    return func


class TestIsTfaSessionExpired:
    def test_401_invalid_user_key_is_expired(self):
        assert _is_tfa_session_expired(401, "Invalid user key") is True

    def test_404_session_expired_message_is_expired(self):
        assert _is_tfa_session_expired(404, "Session expired. Please log in again.") is True

    def test_401_with_other_message_is_not_expired(self):
        assert _is_tfa_session_expired(401, "Please log in or sign up") is False

    def test_404_with_other_message_is_not_expired(self):
        assert _is_tfa_session_expired(404, "Not found") is False

    def test_other_status_codes_are_not_expired(self):
        assert _is_tfa_session_expired(500, "Session expired. Please log in again.") is False


class TestRunCommandSessionExpiredRetry:
    def test_404_session_expired_falls_back_to_api_key_and_retries(self, tmp_path, capsys):
        tfa_file = tmp_path / "vast_tfa_key"
        api_file = tmp_path / "vast_api_key"
        tfa_file.write_text("stale-tfa-key")
        api_file.write_text("normal-api-key")

        func = MagicMock(side_effect=[_http_error(404, "Session expired. Please log in again."), 0])
        args = _args(func=func)

        with patch("vastai.cli.main.TFAKEY_FILE", str(tfa_file)), \
             patch("vastai.cli.main.APIKEY_FILE", str(api_file)):
            with pytest.raises(SystemExit) as exc_info:
                run_command(args)

        assert exc_info.value.code == 0
        assert func.call_count == 2
        assert args.api_key == "normal-api-key"
        assert not tfa_file.exists()

        err = capsys.readouterr().out
        assert "Your 2FA session has expired." in err
        assert "Trying again with your normal API Key" in err
        assert "vastai tfa login" in err

    def test_401_invalid_user_key_falls_back_same_as_404(self, tmp_path):
        tfa_file = tmp_path / "vast_tfa_key"
        api_file = tmp_path / "vast_api_key"
        tfa_file.write_text("stale-tfa-key")
        api_file.write_text("normal-api-key")

        func = MagicMock(side_effect=[_http_error(401, "Invalid user key"), 0])
        args = _args(func=func)

        with patch("vastai.cli.main.TFAKEY_FILE", str(tfa_file)), \
             patch("vastai.cli.main.APIKEY_FILE", str(api_file)):
            with pytest.raises(SystemExit):
                run_command(args)

        assert func.call_count == 2
        assert args.api_key == "normal-api-key"

    def test_no_fallback_api_key_tells_user_to_run_tfa_login(self, tmp_path, capsys):
        tfa_file = tmp_path / "vast_tfa_key"
        api_file = tmp_path / "vast_api_key"  # does not exist
        tfa_file.write_text("stale-tfa-key")

        func = MagicMock(side_effect=[_http_error(404, "Session expired. Please log in again.")])
        args = _args(func=func)

        with patch("vastai.cli.main.TFAKEY_FILE", str(tfa_file)), \
             patch("vastai.cli.main.APIKEY_FILE", str(api_file)):
            run_command(args)  # breaks out of the loop without sys.exit

        assert func.call_count == 1
        assert not tfa_file.exists()

        out = capsys.readouterr().out
        assert "vastai tfa login" in out

    def test_plain_404_without_tfa_key_file_is_not_treated_as_session_expiry(self, tmp_path, capsys):
        tfa_file = tmp_path / "vast_tfa_key"  # does not exist
        api_file = tmp_path / "vast_api_key"

        func = MagicMock(side_effect=[_http_error(404, "Session expired. Please log in again.")])
        args = _args(raw=False, func=func)

        with patch("vastai.cli.main.TFAKEY_FILE", str(tfa_file)), \
             patch("vastai.cli.main.APIKEY_FILE", str(api_file)):
            run_command(args)

        assert func.call_count == 1
        err = capsys.readouterr().err
        assert "Failed with error 404: Session expired. Please log in again." in err


class TestHostCommand401Hint:
    def test_known_command_gets_specific_hint(self):
        args = _args(func=_host_command_func("show machines"))
        buf = io.StringIO()
        with patch("vastai.cli.main.get_role", return_value="client"):
            with redirect_stderr(buf):
                _emit_error(args, 401, "no permission")
        out = buf.getvalue()
        assert "'show machines' is a host-only command" in out
        assert "did you mean 'vastai show instances'?" in out
        assert "set role host" in out

    def test_unknown_command_gets_generic_hint(self):
        args = _args(func=_host_command_func("dump-logs"))
        buf = io.StringIO()
        with patch("vastai.cli.main.get_role", return_value="client"):
            with redirect_stderr(buf):
                _emit_error(args, 401, "no permission")
        out = buf.getvalue()
        assert "'dump-logs' is a host-only command" in out
        assert "vastai --help" in out

    def test_host_role_does_not_get_the_hint(self):
        args = _args(func=_host_command_func("show machines"))
        buf = io.StringIO()
        with patch("vastai.cli.main.get_role", return_value="host"):
            with redirect_stderr(buf):
                _emit_error(args, 401, "no permission")
        assert "host-only command" not in buf.getvalue()

    def test_undetected_role_also_gets_the_hint(self):
        # Client is the default: an unset role is treated the same as
        # 'client', not 'host' — so the hint still fires.
        args = _args(func=_host_command_func("show machines"))
        buf = io.StringIO()
        with patch("vastai.cli.main.get_role", return_value=None):
            with redirect_stderr(buf):
                _emit_error(args, 401, "no permission")
        assert "host-only command" in buf.getvalue()

    def test_non_host_only_command_does_not_get_the_hint(self):
        args = _args(func=_client_command_func("show instances"))
        buf = io.StringIO()
        with patch("vastai.cli.main.get_role", return_value="client"):
            with redirect_stderr(buf):
                _emit_error(args, 401, "no permission")
        assert "host-only command" not in buf.getvalue()

    def test_2fa_message_takes_precedence_over_the_hint(self):
        # Even for a host command in the client role, an explicit 2FA error
        # keeps its own (pre-existing) guidance rather than the new hint.
        args = _args(func=_host_command_func("show machines"))
        buf = io.StringIO()
        with patch("vastai.cli.main.get_role", return_value="client"):
            with redirect_stderr(buf):
                _emit_error(args, 401, "Two Factor Authentication required")
        out = buf.getvalue()
        assert "tfa login" in out
        assert "host-only command" not in out

    def test_raw_mode_skips_the_hint_and_emits_json(self):
        args = _args(raw=True, func=_host_command_func("show machines"))
        buf = io.StringIO()
        with patch("vastai.cli.main.get_role", return_value="client"):
            with redirect_stderr(buf):
                _emit_error(args, 401, "no permission")
        out = buf.getvalue()
        assert "host-only command" not in out
        assert '"error": true' in out

    def test_no_func_on_args_does_not_crash(self):
        # Defensive: args without a func attribute (shouldn't happen in
        # practice, but _emit_error must not blow up on missing state).
        args = argparse.Namespace(raw=False)
        buf = io.StringIO()
        with patch("vastai.cli.main.get_role", return_value="client"):
            with redirect_stderr(buf):
                _emit_error(args, 401, "no permission")
        assert "Failed with error 401" in buf.getvalue()
