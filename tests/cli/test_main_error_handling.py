"""Tests for the 2FA session-expiry retry logic in vastai/cli/main.py (CLN-3555)."""

import argparse
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import HTTPError

from vastai.cli.main import _is_tfa_session_expired, run_command


def _http_error(status_code, msg):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"msg": msg}
    return HTTPError(response=resp)


def _args(*, raw=False, func):
    return argparse.Namespace(raw=raw, func=func)


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
