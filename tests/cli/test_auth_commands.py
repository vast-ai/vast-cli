"""Integration tests for auth CLI commands with mocked HTTP."""

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
