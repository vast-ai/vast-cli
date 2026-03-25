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
