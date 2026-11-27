"""Integration tests for storage/volume CLI commands with mocked HTTP."""

import pytest
from requests.exceptions import HTTPError


CP_ID = "cp_0123456789abcdef"


class TestShowVolumes:
    def test_show_volumes_raw(self, parse_argv, patch_get_client, mock_response):
        import time
        patch_get_client.get.return_value = mock_response(200, {
            "volumes": [
                {"id": 1, "label": "my-vol", "disk_space": 100, "status": "active",
                 "start_date": time.time() - 3600}
            ]
        })
        args = parse_argv(["show", "volumes", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/volumes" in call_args[0][0]


class TestShowConnections:
    def test_show_connections_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, [
            {"id": 1, "name": "my-s3", "cloud_type": "s3"}
        ])
        args = parse_argv(["show", "connections", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/users/cloud_integrations/" in call_args[0][0]

    def test_show_connections_hf_raw(self, parse_argv, patch_get_client, mock_response):
        connections = [
            {"id": 5, "name": "HF_1", "cloud_type": "hf"}
        ]
        patch_get_client.get.return_value = mock_response(200, connections)
        args = parse_argv(["show", "connections", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/users/cloud_integrations/" in call_args[0][0]
        assert result == connections


class TestCloudCopy:
    def test_cloud_copy_hf(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.post.return_value = mock_response(200, {"success": True})
        args = parse_argv([
            "cloud", "copy",
            "--src", "my-bucket/data",
            "--dst", "/workspace",
            "--instance", "6003036",
            "--connection", "1234",
            "--transfer", "Cloud To Instance",
            "--raw",
        ])
        args.func(args)
        patch_get_client.post.assert_called_once()
        call_args = patch_get_client.post.call_args
        assert "/commands/rclone/" in call_args[0][0]
        assert call_args[1]["json_data"] == {
            "src": "my-bucket/data",
            "dst": "/workspace",
            "instance_id": "6003036",
            "selected": "1234",
            "transfer": "Cloud To Instance",
            "flags": [],
        }


class TestCopy:
    @pytest.mark.parametrize("src,dst", [("123:/data", "456:/data"), ("V.123:/data", "C.456:/data")])
    def test_prints_copy_id(self, parse_argv, patch_get_client, mock_response, capsys, src, dst):
        patch_get_client.put.return_value = mock_response(200, {"success": True, "cp_id": CP_ID})
        args = parse_argv(["copy", src, dst])
        args.func(args)
        assert CP_ID in capsys.readouterr().out

    def test_conflict_prints_holder_and_cancel_command(self, parse_argv, patch_get_client, mock_response, capsys):
        from vastai.cli.main import run_command
        patch_get_client.put.return_value = mock_response(409, {
            "success": False, "error": "copy_in_progress", "cp_id": CP_ID,
            "holder": {"cp_id": CP_ID, "state": "running",
                       "src": {"kind": "volume", "id": 123}, "dst": {"kind": "instance", "id": 456}},
        })
        args = parse_argv(["copy", "V.123:/data", "C.456:/data"])
        run_command(args)
        out = capsys.readouterr().err
        assert f"Copy {CP_ID} (running)" in out
        assert f"vastai cancel copy {CP_ID}" in out

    @pytest.mark.parametrize("status,error", [(409, "other_conflict"), (403, "forbidden")])
    def test_other_errors_propagate(self, parse_argv, patch_get_client, mock_response, status, error):
        patch_get_client.put.return_value = mock_response(status, {"error": error})
        args = parse_argv(["copy", "123:/data", "456:/data"])
        with pytest.raises(HTTPError):
            args.func(args)

    def test_copy_hf_prefix_passthrough(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.put.return_value = mock_response(200, {"success": True})
        args = parse_argv([
            "copy",
            "hf.101:/my-bucket/data",
            "C.123:/workspace/",
        ])
        args.func(args)
        patch_get_client.put.assert_called_once()
        call_args = patch_get_client.put.call_args
        assert "/commands/copy_direct/" in call_args[0][0]
        assert call_args[1]["json_data"]["src_id"] == "hf.101"


class TestCancelCopy:
    @pytest.mark.parametrize("status,state", [(202, "cancelling"), (200, "cancelling"),
                                            (200, "cancelled"), (200, "done"), (200, "failed")])
    def test_copy_id_uses_copies_endpoint(self, parse_argv, patch_get_client, mock_response, capsys, status, state):
        patch_get_client.delete.return_value = mock_response(status, {"success": True, "cp_id": CP_ID, "state": state})
        args = parse_argv(["cancel", "copy", CP_ID])
        args.func(args)
        patch_get_client.delete.assert_called_once_with(f"/copies/{CP_ID}/")
        patch_get_client.get.assert_not_called()
        assert f"Copy {CP_ID}: {state}" in capsys.readouterr().out

    @pytest.mark.parametrize("extra", [{}, {"cp_id": CP_ID, "state": "cancelling"}])
    def test_legacy_instance_id(self, parse_argv, patch_get_client, mock_response, capsys, extra):
        patch_get_client.delete.return_value = mock_response(200, {"success": True, **extra})
        args = parse_argv(["cancel", "copy", "12371"])
        args.func(args)
        patch_get_client.delete.assert_called_once_with(
            "/commands/copy_direct/", json_data={"client_id": "me", "dst_id": "12371"})
        out = capsys.readouterr().out
        assert "Remote copy canceled" not in out
        if extra:
            assert f"Copy {CP_ID}: cancelling" in out

    def test_not_found_propagates(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.delete.return_value = mock_response(404, {"success": False, "error": "not_found"})
        args = parse_argv(["cancel", "copy", CP_ID])
        with pytest.raises(HTTPError):
            args.func(args)


class TestShowInstanceBackupFiles:
    """The table's URLs must be fetchable on their own; --raw must stay a passthrough."""

    PAYLOAD = {
        "success": True,
        "authorization_token": "4_002+abc/def=",
        "expires_in_sec": 3600,
        "truncated": False,
        "files": [
            {"name": "instance_backups/7/42/upper/model.safetensors",
             "size": 2500000,
             "url": "https://f002.backblazeb2.com/file/vast-instance-backups/"
                    "instance_backups/7/42/upper/model.safetensors"},
        ],
    }

    def _rows(self, capsys):
        """The URL column of the printed table, minus row labels and color codes."""
        import re
        out = re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out)
        return re.findall(r"https://\S+", out)

    def test_url_carries_token(self, parse_argv, patch_get_client, mock_response, capsys):
        import copy
        patch_get_client.get.return_value = mock_response(200, copy.deepcopy(self.PAYLOAD))
        args = parse_argv(["show", "instance-backup-files", "42"])
        args.func(args)
        assert "/instance_backups/42/download/" in patch_get_client.get.call_args[0][0]
        # Token is percent-encoded: a raw '+' would decode to a space, and '/' and '='
        # would end up as path/query syntax rather than token bytes.
        assert self._rows(capsys) == [
            "https://f002.backblazeb2.com/file/vast-instance-backups/"
            "instance_backups/7/42/upper/model.safetensors"
            "?Authorization=4_002%2Babc%2Fdef%3D"
        ]

    def test_raw_is_unmodified_passthrough(self, parse_argv, patch_get_client, mock_response):
        import copy
        patch_get_client.get.return_value = mock_response(200, copy.deepcopy(self.PAYLOAD))
        args = parse_argv(["show", "instance-backup-files", "42", "--raw"])
        assert args.func(args) == self.PAYLOAD

    def test_existing_query_string_is_appended_to(self, parse_argv, patch_get_client,
                                                  mock_response, capsys):
        import copy
        payload = copy.deepcopy(self.PAYLOAD)
        payload["files"][0]["url"] += "?b2ContentDisposition=attachment"
        patch_get_client.get.return_value = mock_response(200, payload)
        args = parse_argv(["show", "instance-backup-files", "42"])
        args.func(args)
        assert self._rows(capsys)[0].endswith(
            "?b2ContentDisposition=attachment&Authorization=4_002%2Babc%2Fdef%3D")

    def test_missing_token_leaves_url_alone(self, parse_argv, patch_get_client,
                                            mock_response, capsys):
        import copy
        payload = copy.deepcopy(self.PAYLOAD)
        payload["authorization_token"] = None
        patch_get_client.get.return_value = mock_response(200, payload)
        args = parse_argv(["show", "instance-backup-files", "42"])
        args.func(args)
        assert self._rows(capsys)[0] == payload["files"][0]["url"]
