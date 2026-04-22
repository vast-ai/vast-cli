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


class TestAcceptPriceIncrease:
    """CLN-3107: client-side accept for host price-increase challenges."""

    def test_single_instance_hits_path_route(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.put.return_value = mock_response(
            200, {"success": True, "accepted_contract_ids": [123], "batch_keys": ["b1"]}
        )
        args = parse_argv(["accept", "price-increase", "123"])
        args.func(args)
        patch_get_client.put.assert_called_once()
        call_args = patch_get_client.put.call_args
        assert "/instances/123/accept-price-increase/" in call_args[0][0]
        assert call_args[1]["json_data"] == {}
        captured = capsys.readouterr()
        assert "Accepted price increase" in captured.out
        assert "123" in captured.out

    def test_multiple_instance_ids_go_to_batch_route(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.put.return_value = mock_response(
            200, {"success": True, "accepted_contract_ids": [1, 2, 3], "batch_keys": []}
        )
        args = parse_argv(["accept", "price-increase", "1", "2", "3"])
        args.func(args)
        patch_get_client.put.assert_called_once()
        call_args = patch_get_client.put.call_args
        assert call_args[0][0].endswith("/instances/accept-price-increase/") or \
               "/instances/accept-price-increase/?" in call_args[0][0]
        assert call_args[1]["json_data"]["instance_ids"] == [1, 2, 3]
        assert "host_id" not in call_args[1]["json_data"]

    def test_host_flag_sends_host_id_only(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.put.return_value = mock_response(
            200, {"success": True, "accepted_contract_ids": [7, 8], "batch_keys": ["b"]}
        )
        args = parse_argv(["accept", "price-increase", "--host", "42"])
        args.func(args)
        patch_get_client.put.assert_called_once()
        call_args = patch_get_client.put.call_args
        assert "/instances/accept-price-increase/" in call_args[0][0]
        assert call_args[1]["json_data"] == {"host_id": 42}

    def test_rejects_no_selector(self, parse_argv, patch_get_client, capsys):
        args = parse_argv(["accept", "price-increase"])
        with pytest.raises(SystemExit):
            args.func(args)
        patch_get_client.put.assert_not_called()
        captured = capsys.readouterr()
        assert "instance IDs or --host" in captured.err

    def test_rejects_both_selectors(self, parse_argv, patch_get_client, capsys):
        args = parse_argv(["accept", "price-increase", "1", "2", "--host", "5"])
        with pytest.raises(SystemExit):
            args.func(args)
        patch_get_client.put.assert_not_called()
        captured = capsys.readouterr()
        assert "not both" in captured.err

    def test_rejects_more_than_64_ids(self, parse_argv, patch_get_client, capsys):
        many = [str(i) for i in range(1, 66)]
        args = parse_argv(["accept", "price-increase", *many])
        with pytest.raises(SystemExit):
            args.func(args)
        patch_get_client.put.assert_not_called()
        captured = capsys.readouterr()
        assert "> 64" in captured.err

    def test_raw_passthrough(self, parse_argv, patch_get_client, mock_response):
        payload = {"success": True, "accepted_contract_ids": [9], "batch_keys": ["b"], "user_id": 11}
        patch_get_client.put.return_value = mock_response(200, payload)
        args = parse_argv(["accept", "price-increase", "9", "--raw"])
        result = args.func(args)
        assert result == payload

    def test_no_accepted_prints_no_pending(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.put.return_value = mock_response(
            200, {"success": True, "accepted_contract_ids": [], "batch_keys": []}
        )
        args = parse_argv(["accept", "price-increase", "--host", "99"])
        args.func(args)
        captured = capsys.readouterr()
        assert "No pending price increases" in captured.out

    def test_failure_prints_msg(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.put.return_value = mock_response(
            200, {"success": False, "msg": "challenge expired"}
        )
        args = parse_argv(["accept", "price-increase", "55"])
        args.func(args)
        captured = capsys.readouterr()
        assert "challenge expired" in captured.out
