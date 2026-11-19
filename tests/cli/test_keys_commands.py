"""Integration tests for SSH/API key CLI commands with mocked HTTP."""

import pytest
from requests.exceptions import HTTPError


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
        # Backend returns {"apikeys": [...]} (no underscore), not "api_keys".
        patch_get_client.get.return_value = mock_response(200, {
            "apikeys": [{"id": 1, "name": "test-key"}]
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


class TestCreateApiKey:
    def _perms(self, tmp_path):
        perms = tmp_path / "perms.json"
        perms.write_text('{"api": {"instance_read": {"api.instance": {"constraints": {"id": {"eq": "$instance_id"}}}}}}')
        return str(perms)

    def test_no_lifetime_and_no_params_send_neither_field(self, parse_argv, patch_get_client, mock_response, tmp_path):
        """A server that predates the fields refuses unknown ones, so they are sent only when asked for."""
        patch_get_client.post.return_value = mock_response(200, {"id": 1, "key": "k", "expires_at": None})
        args = parse_argv(["create", "api-key", "--name", "c", "--permission_file", self._perms(tmp_path)])
        args.func(args)
        sent = patch_get_client.post.call_args[1]["json_data"]
        assert "lifetime_sec" not in sent and "key_params" not in sent

    def test_lifetime_is_sent_as_seconds(self, parse_argv, patch_get_client, mock_response, tmp_path):
        patch_get_client.post.return_value = mock_response(200, {"id": 1, "key": "k", "expires_at": 1800003600.0})
        args = parse_argv(["create", "api-key", "--name", "c", "--permission_file", self._perms(tmp_path), "--lifetime_sec", "3600"])
        args.func(args)
        assert patch_get_client.post.call_args[1]["json_data"]["lifetime_sec"] == 3600.0

    def test_key_params_are_sent_as_an_object(self, parse_argv, patch_get_client, mock_response, tmp_path):
        """The flag is JSON text; the API takes an object. Sending the text was refused by the server."""
        patch_get_client.post.return_value = mock_response(200, {"id": 1, "key": "k"})
        args = parse_argv(["create", "api-key", "--name", "c", "--permission_file", self._perms(tmp_path),
                           "--key_params", '{"$instance_id": 1234}'])
        args.func(args)
        assert patch_get_client.post.call_args[1]["json_data"]["key_params"] == {"$instance_id": 1234}

    @pytest.mark.parametrize("bad", ['{"instance_id": 1234}', "1234", "not json"])
    def test_key_params_that_bind_nothing_are_refused_before_any_request(self, parse_argv, patch_get_client, tmp_path, capsys, bad):
        args = parse_argv(["create", "api-key", "--name", "c", "--permission_file", self._perms(tmp_path), "--key_params", bad])
        assert args.func(args) == 1
        patch_get_client.post.assert_not_called()
        assert "key_params" in capsys.readouterr().out

    def test_denied_mint_propagates_server_error(self, parse_argv, patch_get_client, mock_response, tmp_path):
        """A rejected mint must reach the CLI error handler, which prints the server's reason."""
        perms = tmp_path / "perms.json"
        perms.write_text('{"api": {"user_write": {"api.team": {"POST": {}}}}}')
        patch_get_client.post.return_value = mock_response(403, {"error": "delegation_exceeds_issuer", "msg": "no explicit grant"})
        args = parse_argv(["create", "api-key", "--name", "c", "--permission_file", str(perms)])
        with pytest.raises(HTTPError):
            args.func(args)
