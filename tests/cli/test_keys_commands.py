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


PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyMaterial user@host"

PRIVATE_KEY = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
-----END OPENSSH PRIVATE KEY-----
"""


class TestCreateSshKey:
    def test_create_ssh_key(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.post.return_value = mock_response(200, {"id": 1, "success": True})
        args = parse_argv(["create", "ssh-key", PUBLIC_KEY])
        args.func(args)
        patch_get_client.post.assert_called_once()
        call_args = patch_get_client.post.call_args
        assert "/ssh/" in call_args[0][0]
        # The key *material* must reach the API, not just the parameter name.
        assert call_args[1]["json_data"]["ssh_key"] == PUBLIC_KEY

    def test_create_ssh_key_reads_public_key_file(
        self, parse_argv, patch_get_client, mock_response, tmp_path
    ):
        """A path to a .pub file is read; the path string itself is never sent.

        `vastai create ssh-key ~/.ssh/id_ed25519.pub` is the form the docs and
        this command's own help text tell users to run.
        """
        key_file = tmp_path / "id_ed25519.pub"
        key_file.write_text(PUBLIC_KEY + "\n")
        patch_get_client.post.return_value = mock_response(200, {"id": 1, "success": True})

        args = parse_argv(["create", "ssh-key", str(key_file)])
        args.func(args)

        sent = patch_get_client.post.call_args[1]["json_data"]["ssh_key"]
        assert sent.strip() == PUBLIC_KEY
        assert str(key_file) not in sent

    def test_create_ssh_key_rejects_private_key(
        self, parse_argv, patch_get_client, tmp_path
    ):
        key_file = tmp_path / "id_ed25519"
        key_file.write_text(PRIVATE_KEY)

        args = parse_argv(["create", "ssh-key", str(key_file)])
        with pytest.raises(ValueError, match="private"):
            args.func(args)
        patch_get_client.post.assert_not_called()

    def test_create_ssh_key_rejects_non_key_string(self, parse_argv, patch_get_client):
        args = parse_argv(["create", "ssh-key", "/does/not/exist/id_ed25519.pub"])
        with pytest.raises(ValueError, match="SSH public key"):
            args.func(args)
        patch_get_client.post.assert_not_called()


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
