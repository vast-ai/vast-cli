"""Integration tests for auth CLI commands with mocked HTTP."""

import argparse
import io
import stat
import sys
from unittest.mock import patch

import pytest
from requests.exceptions import HTTPError


class TestShowAuditLogs:
    def test_show_audit_logs_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, [
            {"ip_address": "1.2.3.4", "api_key_id": 1, "created_at": "2024-01-01", "api_route": "/test", "args": "{}"}
        ])
        args = parse_argv(["show", "audit-logs", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/audit_logs/" in call_args[0][0]

    def test_show_audit_logs_display(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, [
            {"ip_address": "1.2.3.4", "api_key_id": 1, "created_at": "2024-01-01", "api_route": "/test", "args": "{}"}
        ])
        args = parse_argv(["show", "audit-logs"])
        args.func(args)
        captured = capsys.readouterr()
        assert "ip_address" in captured.out or "1.2.3.4" in captured.out


class TestShowEnvVars:
    def test_show_env_vars_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "secrets": {"MY_VAR": "my_value", "OTHER": "secret"}
        })
        args = parse_argv(["show", "env-vars", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/secrets/" in call_args[0][0]
        # Values should be masked when not using --show-values
        assert result["MY_VAR"] == "*****"

    def test_show_env_vars_with_values(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "secrets": {"MY_VAR": "my_value"}
        })
        args = parse_argv(["show", "env-vars", "--raw", "--show-values"])
        result = args.func(args)
        assert result["MY_VAR"] == "my_value"


class TestCreateEnvVar:
    def test_create_env_var(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.post.return_value = mock_response(200, {"success": True, "msg": "Created"})
        args = parse_argv(["create", "env-var", "MY_NAME", "MY_VALUE"])
        args.func(args)
        patch_get_client.post.assert_called_once()
        call_args = patch_get_client.post.call_args
        assert "/secrets/" in call_args[0][0]
        assert call_args[1]["json_data"]["key"] == "MY_NAME"
        assert call_args[1]["json_data"]["value"] == "MY_VALUE"


class TestUpdateEnvVar:
    def test_update_env_var(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.put.return_value = mock_response(200, {"success": True, "msg": "Updated"})
        args = parse_argv(["update", "env-var", "MY_NAME", "NEW_VALUE"])
        args.func(args)
        patch_get_client.put.assert_called_once()
        call_args = patch_get_client.put.call_args
        assert "/secrets/" in call_args[0][0]
        assert call_args[1]["json_data"]["key"] == "MY_NAME"
        assert call_args[1]["json_data"]["value"] == "NEW_VALUE"


class TestDeleteEnvVar:
    def test_delete_env_var(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.delete.return_value = mock_response(200, {"success": True, "msg": "Deleted"})
        args = parse_argv(["delete", "env-var", "MY_NAME"])
        args.func(args)
        patch_get_client.delete.assert_called_once()
        call_args = patch_get_client.delete.call_args
        assert "/secrets/" in call_args[0][0]
        assert call_args[1]["json_data"]["key"] == "MY_NAME"


API_KEY = "0123456789abcdef" * 4
OTHER_API_KEY = "fedcba9876543210" * 4


class TerminalStdin(io.StringIO):
    def isatty(self):
        return True


class TestSetApiKey:
    @pytest.fixture
    def key_file(self, tmp_path, monkeypatch):
        key_file = tmp_path / "vast_api_key"
        monkeypatch.setattr("vastai.cli.util.APIKEY_FILE", str(key_file))
        monkeypatch.setattr("vastai.cli.util.APIKEY_FILE_HOME", str(tmp_path / ".vast_api_key"))
        monkeypatch.delenv("VAST_API_KEY", raising=False)
        return key_file

    def test_writes_byte_exact_no_text_mode_translation(self, key_file, monkeypatch):
        # `open(path, "w").write(key)` on Windows turns `\n` -> `\r\n`; the key
        # file must contain exactly the key bytes and nothing else, so trailing
        # whitespace bugs are also caught.
        monkeypatch.setattr("vastai.api.machines.show_machines", lambda client: [])
        from vastai.cli.commands.auth import set__api_key
        set__api_key(argparse.Namespace(new_api_key=API_KEY))
        assert key_file.read_bytes() == API_KEY.encode()

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
    def test_key_file_is_owner_only_when_replacing_an_existing_one(self, key_file):
        key_file.write_text(OTHER_API_KEY)
        key_file.chmod(0o644)
        from vastai.cli.commands.auth import set__api_key
        set__api_key(argparse.Namespace(new_api_key=API_KEY))
        assert key_file.read_text() == API_KEY
        assert stat.S_IMODE(key_file.stat().st_mode) == 0o600

    @pytest.mark.parametrize("bad", ["YOUR_API_KEY", API_KEY + "0", "g" * 64])
    def test_rejects_what_is_not_an_api_key(self, key_file, capsys, bad):
        key_file.write_text(OTHER_API_KEY)
        from vastai.cli.commands.auth import set__api_key
        with pytest.raises(SystemExit) as exit_info:
            set__api_key(argparse.Namespace(new_api_key=bad))
        assert exit_info.value.code == 1
        assert key_file.read_text() == OTHER_API_KEY
        out = capsys.readouterr().out
        assert "64 hex characters" in out
        assert bad not in out

    def test_rejection_fails_the_command_under_raw(self, key_file, parse_argv):
        # --raw prints a command's return value as JSON and exits 0, so a rejection
        # signalled by returning would look like success to a script.
        from vastai.cli.main import run_command
        with pytest.raises(SystemExit) as exit_info:
            run_command(parse_argv(["set", "api-key", "YOUR_API_KEY", "--raw"]))
        assert exit_info.value.code == 1
        assert not key_file.exists()

    def test_key_is_optional_on_the_command_line(self, parse_argv):
        assert parse_argv(["set", "api-key"]).new_api_key is None

    def test_left_out_key_is_asked_for_at_a_hidden_prompt(self, key_file, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", TerminalStdin())
        monkeypatch.setattr("getpass.getpass", lambda prompt: f"  {API_KEY}\n")
        from vastai.cli.commands.auth import set__api_key
        set__api_key(argparse.Namespace(new_api_key=None))
        assert key_file.read_text() == API_KEY
        assert API_KEY not in capsys.readouterr().out

    def test_cancelled_prompt_saves_nothing(self, key_file, monkeypatch):
        def cancel(prompt):
            raise KeyboardInterrupt
        monkeypatch.setattr("sys.stdin", TerminalStdin())
        monkeypatch.setattr("getpass.getpass", cancel)
        from vastai.cli.commands.auth import set__api_key
        with pytest.raises(SystemExit) as exit_info:
            set__api_key(argparse.Namespace(new_api_key=None))
        assert exit_info.value.code == 1
        assert not key_file.exists()

    def test_left_out_key_without_a_terminal_fails_without_reading_stdin(self, key_file, monkeypatch, capsys):
        # An agent or CI job holding an open pipe on stdin must fail at once, not wait on it.
        piped = io.StringIO(API_KEY + "\n")
        monkeypatch.setattr("sys.stdin", piped)
        from vastai.cli.commands.auth import set__api_key
        with pytest.raises(SystemExit) as exit_info:
            set__api_key(argparse.Namespace(new_api_key=None))
        assert exit_info.value.code == 1
        assert piped.tell() == 0
        assert not key_file.exists()
        assert "No API key given" in capsys.readouterr().out

    def test_sdk_reads_back_key_written_by_cli(self, tmp_path, monkeypatch):
        # End-to-end: `set api-key` writes the file; VastAI() picks it up.
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Path.home() on Windows
        monkeypatch.delenv("VAST_API_KEY", raising=False)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        xdg_dir = tmp_path / ".config" / "vastai"
        xdg_dir.mkdir(parents=True)
        key_file = xdg_dir / "vast_api_key"
        monkeypatch.setattr("vastai.cli.util.APIKEY_FILE", str(key_file))
        monkeypatch.setattr("vastai.cli.util.APIKEY_FILE_HOME", str(tmp_path / ".vast_api_key"))
        monkeypatch.setattr("vastai.api.machines.show_machines", lambda client: [])

        from vastai.cli.commands.auth import set__api_key
        set__api_key(argparse.Namespace(new_api_key=API_KEY))

        from vastai import VastAI
        with patch("vastai.sdk.VastClient") as MockClient:
            VastAI()
            assert MockClient.call_args[0][0] == API_KEY


class TestSetRole:
    def test_set_role_host(self, tmp_path, monkeypatch, capsys):
        role_file = tmp_path / "vast_role"
        monkeypatch.setattr("vastai.cli.util.ROLE_FILE", str(role_file))
        from vastai.cli.commands.auth import set__role
        set__role(argparse.Namespace(role="host"))
        assert role_file.read_text() == "host"
        assert "host" in capsys.readouterr().out.lower()

    def test_set_role_client(self, tmp_path, monkeypatch, capsys):
        role_file = tmp_path / "vast_role"
        monkeypatch.setattr("vastai.cli.util.ROLE_FILE", str(role_file))
        from vastai.cli.commands.auth import set__role
        set__role(argparse.Namespace(role="client"))
        assert role_file.read_text() == "client"
        assert "hidden" in capsys.readouterr().out.lower()

    def test_only_host_and_client_are_valid_choices(self, cli_parser):
        with pytest.raises(SystemExit):
            cli_parser.parse_args(["set", "role", "admin"])


class TestTfaStatus:
    def test_tfa_status_raw(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {
            "tfa_enabled": True, "methods": [], "backup_codes_remaining": 5
        })
        args = parse_argv(["tfa", "status", "--raw"])
        args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/tfa/status/" in call_args[0][0]


class TestTfaMethodFieldsFormatUtc:
    def test_created_at_formats_in_utc(self, monkeypatch):
        import time as _time
        if not hasattr(_time, "tzset"):
            pytest.skip("tzset unavailable on this platform")
        monkeypatch.setenv("TZ", "America/Los_Angeles")
        _time.tzset()
        try:
            from vastai.cli.commands.auth import TFA_METHOD_FIELDS
            created_formatter = dict((f[0], f[3]) for f in TFA_METHOD_FIELDS)["created_at"]
            # 1705276800 = 2024-01-15 00:00:00 UTC; in LA would be 2024-01-14 16:00
            assert created_formatter(1705276800) == "2024-01-15 00:00:00"
        finally:
            _time.tzset()

    def test_falsy_value_renders_na(self):
        from vastai.cli.commands.auth import TFA_METHOD_FIELDS
        created_formatter = dict((f[0], f[3]) for f in TFA_METHOD_FIELDS)["created_at"]
        assert created_formatter(None) == "N/A"
        assert created_formatter(0) == "N/A"
