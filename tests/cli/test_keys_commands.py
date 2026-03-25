"""Integration tests for SSH/API key CLI commands with mocked HTTP."""

import pytest


class TestShowSshKeys:
    def test_show_ssh_keys_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "ssh_keys": [{"id": 1, "ssh_key": "ssh-rsa AAAA..."}]
        })
        args = parse_argv(["show", "ssh-keys", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/ssh/" in call_args[0][0]


class TestShowApiKeys:
    def test_show_api_keys_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "api_keys": [{"id": 1, "name": "test-key"}]
        })
        args = parse_argv(["show", "api-keys", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/auth/apikeys/" in call_args[0][0]


class TestShowApiKey:
    def test_show_api_key(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {"id": 1, "name": "my-key"})
        args = parse_argv(["show", "api-key", "1"])
        args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/auth/apikeys/1/" in call_args[0][0]


class TestCreateSshKey:
    def test_create_ssh_key(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.post.return_value = mock_response(200, {"id": 1, "success": True})
        args = parse_argv(["create", "ssh-key", "ssh-rsa AAAA... user@host"])
        args.func(args)
        patch_get_client.post.assert_called_once()
        call_args = patch_get_client.post.call_args
        assert "/ssh/" in call_args[0][0]
        assert "ssh_key" in call_args[1]["json_data"]


class TestDeleteSshKey:
    def test_delete_ssh_key(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.delete.return_value = mock_response(200, {"success": True})
        args = parse_argv(["delete", "ssh-key", "1"])
        args.func(args)
        patch_get_client.delete.assert_called_once()
        call_args = patch_get_client.delete.call_args
        assert "/ssh/1/" in call_args[0][0]


class TestDeleteApiKey:
    def test_delete_api_key(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.delete.return_value = mock_response(200, {"success": True})
        args = parse_argv(["delete", "api-key", "1"])
        args.func(args)
        patch_get_client.delete.assert_called_once()
        call_args = patch_get_client.delete.call_args
        assert "/auth/apikeys/1/" in call_args[0][0]
