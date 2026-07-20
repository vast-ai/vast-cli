"""Integration tests for auth CLI commands with mocked HTTP."""

import argparse
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


class TestSetApiKey:
    def test_writes_byte_exact_no_text_mode_translation(self, tmp_path, monkeypatch):
        # `open(path, "w").write(key)` on Windows turns `\n` -> `\r\n`; the key
        # file must contain exactly the key bytes and nothing else, so trailing
        # whitespace bugs are also caught.
        key_file = tmp_path / "vast_api_key"
        legacy_file = tmp_path / ".vast_api_key"
        monkeypatch.setattr("vastai.cli.util.APIKEY_FILE", str(key_file))
        monkeypatch.setattr("vastai.cli.util.APIKEY_FILE_HOME", str(legacy_file))
        from vastai.cli.commands.auth import set__api_key
        set__api_key(argparse.Namespace(new_api_key="test-key-abc-123"))
        assert key_file.read_bytes() == b"test-key-abc-123"

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

        from vastai.cli.commands.auth import set__api_key
        set__api_key(argparse.Namespace(new_api_key="round-trip-key"))

        from vastai import VastAI
        with patch("vastai.sdk.VastClient") as MockClient:
            VastAI()
            assert MockClient.call_args[0][0] == "round-trip-key"


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
