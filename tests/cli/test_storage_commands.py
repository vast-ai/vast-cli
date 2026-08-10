"""Integration tests for storage/volume CLI commands with mocked HTTP."""

import pytest


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
