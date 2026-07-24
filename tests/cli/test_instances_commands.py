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

    def test_show_instances_raw_null_instances(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {"instances": None})
        args = parse_argv(["show", "instances", "--raw"])

        result = args.func(args)

        assert result == []

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

    def test_show_instances_quiet_prints_bare_ids(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {
            "instances": [
                {"id": 1, "gpu_name": "RTX_3090", "actual_status": "running",
                 "start_date": time.time() - 3600, "extra_env": []},
                {"id": 2, "gpu_name": "RTX_4090", "actual_status": "running",
                 "start_date": time.time() - 3600, "extra_env": []},
            ]
        })
        args = parse_argv(["show", "instances", "-q"])
        args.func(args)
        captured = capsys.readouterr()
        assert captured.out == "1\n2\n"

    def test_show_instances_v1_is_hidden_alias(self, parse_argv, patch_get_client, mock_response):
        from vastai.cli.commands.instances import show__instances
        patch_get_client.get.return_value = mock_response(200, {
            "instances": [
                {"id": 1, "gpu_name": "RTX_3090", "actual_status": "running",
                 "start_date": time.time() - 3600, "extra_env": [["KEY", "VAL"]]}
            ]
        })
        args = parse_argv(["show", "instances-v1", "--raw"])
        assert args.func is show__instances
        result = args.func(args)
        assert isinstance(result, list)


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

    def test_show_instance_raw_deleted_instance(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {"instances": None})
        args = parse_argv(["show", "instance", "123", "--raw"])

        result = args.func(args)

        assert result == {"instances": None}

    def test_show_instance_display_deleted_instance(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {"instances": None})
        args = parse_argv(["show", "instance", "123"])

        result = args.func(args)

        assert result == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "Instance 123 not found or no longer exists." in captured.err


class TestDestroyInstance:
    def test_destroy_instance(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.delete.return_value = mock_response(200, {"success": True})
        args = parse_argv(["destroy", "instance", "123", "--raw", "--yes"])
        result = args.func(args)
        patch_get_client.delete.assert_called_once()
        call_args = patch_get_client.delete.call_args
        assert "/instances/123/" in call_args[0][0]

    def test_destroy_instance_confirm_yes(self, parse_argv, patch_get_client, mock_response, capsys, monkeypatch):
        patch_get_client.delete.return_value = mock_response(200, {"success": True})
        monkeypatch.setattr("builtins.input", lambda _: "y")
        args = parse_argv(["destroy", "instance", "123"])
        args.func(args)
        patch_get_client.delete.assert_called_once()
        captured = capsys.readouterr()
        assert "destroying instance 123" in captured.out

    def test_destroy_instance_confirm_no(self, parse_argv, patch_get_client, mock_response, capsys, monkeypatch):
        patch_get_client.delete.return_value = mock_response(200, {"success": True})
        monkeypatch.setattr("builtins.input", lambda _: "n")
        args = parse_argv(["destroy", "instance", "123"])
        args.func(args)
        patch_get_client.delete.assert_not_called()
        captured = capsys.readouterr()
        assert "Aborted" in captured.out


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


# TestAcceptPriceIncrease was rewritten against the per-row backend and moved
# to tests/cli/test_price_increase_commands.py alongside the show + reject
# command tests.
