"""Integration tests for instance CLI commands with mocked HTTP."""

import time
import pytest
from requests.exceptions import HTTPError


class TestShowInstances:
    def test_show_instances_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "instances": [
                {"id": 1, "gpu_name": "RTX_3090", "actual_status": "running",
                 "start_date": time.time() - 3600, "extra_env": [["KEY", "VAL"]]}
            ]
        })
        args = parse_argv(["show", "instances", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/instances" in call_args[0][0]
        assert isinstance(result, list)

    def test_show_instances_display(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {
            "instances": [
                {"id": 1, "gpu_name": "RTX_3090", "actual_status": "running",
                 "start_date": time.time() - 3600, "extra_env": []}
            ]
        })
        args = parse_argv(["show", "instances"])
        args.func(args)
        captured = capsys.readouterr()
        assert "ID" in captured.out


class TestShowInstance:
    def test_show_instance_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "instances": {"id": 123, "gpu_name": "RTX_4090", "start_date": time.time() - 100, "extra_env": []}
        })
        args = parse_argv(["show", "instance", "123", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "123" in call_args[0][0]


class TestDestroyInstance:
    def test_destroy_instance(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.delete.return_value = mock_response(200, {"success": True})
        args = parse_argv(["destroy", "instance", "123", "--raw"])
        result = args.func(args)
        patch_get_client.delete.assert_called_once()
        call_args = patch_get_client.delete.call_args
        assert "/instances/123/" in call_args[0][0]


class TestStartInstance:
    def test_start_instance(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.put.return_value = mock_response(200, {"success": True})
        args = parse_argv(["start", "instance", "123"])
        args.func(args)
        patch_get_client.put.assert_called_once()
        call_args = patch_get_client.put.call_args
        assert "/instances/123/" in call_args[0][0]
        assert call_args[1]["json_data"]["state"] == "running"


class TestStopInstance:
    def test_stop_instance(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.put.return_value = mock_response(200, {"success": True})
        args = parse_argv(["stop", "instance", "123"])
        args.func(args)
        patch_get_client.put.assert_called_once()
        call_args = patch_get_client.put.call_args
        assert "/instances/123/" in call_args[0][0]
        assert call_args[1]["json_data"]["state"] == "stopped"


class TestRebootInstance:
    def test_reboot_instance(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.put.return_value = mock_response(200, {"success": True})
        args = parse_argv(["reboot", "instance", "123"])
        args.func(args)
        patch_get_client.put.assert_called_once()
        call_args = patch_get_client.put.call_args
        assert "/instances/reboot/123/" in call_args[0][0]


class TestRecycleInstance:
    def test_recycle_instance(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.put.return_value = mock_response(200, {"success": True})
        args = parse_argv(["recycle", "instance", "123"])
        args.func(args)
        patch_get_client.put.assert_called_once()
        call_args = patch_get_client.put.call_args
        assert "/instances/recycle/123/" in call_args[0][0]


class TestLabelInstance:
    def test_label_instance(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.put.return_value = mock_response(200, {"success": True})
        args = parse_argv(["label", "instance", "123", "my-label"])
        args.func(args)
        patch_get_client.put.assert_called_once()
        call_args = patch_get_client.put.call_args
        assert call_args[1]["json_data"]["label"] == "my-label"
