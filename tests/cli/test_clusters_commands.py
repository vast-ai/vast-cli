"""Integration tests for cluster/overlay CLI commands with mocked HTTP."""

import pytest


class TestShowClusters:
    def test_show_clusters_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "clusters": {
                "1": {
                    "subnet": "10.0.0.0/24",
                    "nodes": [
                        {"machine_id": 100, "is_cluster_manager": True, "local_ip": "10.0.0.1"},
                        {"machine_id": 101, "is_cluster_manager": False, "local_ip": "10.0.0.2"},
                    ]
                }
            }
        })
        args = parse_argv(["show", "clusters", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/clusters/" in call_args[0][0]


class TestCreateCluster:
    def test_create_cluster(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.post.return_value = mock_response(200, {"success": True, "msg": "Cluster created"})
        args = parse_argv(["create", "cluster", "10.0.0.0/24", "100"])
        args.func(args)
        patch_get_client.post.assert_called_once()
        call_args = patch_get_client.post.call_args
        assert "/cluster/" in call_args[0][0]
        json_data = call_args[1]["json_data"]
        assert json_data["subnet"] == "10.0.0.0/24"
        assert json_data["manager_id"] == 100


class TestDeleteCluster:
    def test_delete_cluster(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.delete.return_value = mock_response(200, {"success": True, "msg": "Cluster deleted"})
        args = parse_argv(["delete", "cluster", "1"])
        args.func(args)
        patch_get_client.delete.assert_called_once()
        call_args = patch_get_client.delete.call_args
        assert "/cluster/" in call_args[0][0]


class TestShowOverlays:
    def test_show_overlays_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, [
            {"overlay_id": 1, "name": "test-overlay", "subnet": "10.0.0.0/24",
             "cluster_id": 1, "instance_count": 2, "instances": [1, 2]}
        ])
        args = parse_argv(["show", "overlays", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/overlay/" in call_args[0][0]
