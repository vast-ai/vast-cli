"""Integration tests for machine CLI commands with mocked HTTP."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest


class TestShowMachines:
    def test_show_machines_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "machines": [
                {"id": 1, "gpu_name": "RTX_3090", "num_gpus": 4, "hostname": "host1"}
            ]
        })
        args = parse_argv(["show", "machines", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/machines" in call_args[0][0]

    def test_show_machines_display(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {
            "machines": [
                {"id": 1, "gpu_name": "RTX_3090", "num_gpus": 4, "hostname": "host1",
                 "disk_space": 100, "driver_version": "535.0", "reliability2": 0.99,
                 "verification": "verified", "public_ipaddr": "1.2.3.4",
                 "geolocation": "US", "num_reports": 0, "listed_gpu_cost": 0.5,
                 "min_bid_price": 0.3, "credit_discount_max": 0.1,
                 "listed_inet_up_cost": 0.01, "listed_inet_down_cost": 0.01,
                 "gpu_occupancy": "2/4"}
            ]
        })
        args = parse_argv(["show", "machines"])
        args.func(args)
        captured = capsys.readouterr()
        assert "ID" in captured.out


class TestShowMachine:
    def test_show_machine_raw(self, parse_argv, patch_get_client, mock_response):
        # Backend returns a bare one-element list for GET /machines/{id}
        patch_get_client.get.return_value = mock_response(200, [{"id": 1, "gpu_name": "RTX_3090"}])
        args = parse_argv(["show", "machine", "1", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/machines/" in call_args[0][0]
        assert result == [{"id": 1, "gpu_name": "RTX_3090"}]


class TestListMachineMinChunkDefault:
    # Backend web/views/machines.py:53 does `int(params.get("min_chunk", 1))` — if the
    # key is present but null, int(None) raises and is caught as HTTPBadRequest
    # ("Invalid machine id or min_chunk"). The CLI must send 1 when --min_chunk is
    # omitted, matching the backend's implicit default.
    def test_list_machine_defaults_min_chunk_to_one(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.put.return_value = mock_response(200, {"success": True})
        args = parse_argv(["list", "machine", "42", "-g", "0.5"])
        args.func(args)
        patch_get_client.put.assert_called_once()
        body = patch_get_client.put.call_args[1]["json_data"]
        assert body["min_chunk"] == 1, f"min_chunk={body['min_chunk']!r} would trigger backend 400"

    def test_list_machines_defaults_min_chunk_to_one(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.put.return_value = mock_response(200, {"success": True})
        args = parse_argv(["list", "machines", "11", "22", "-g", "0.5"])
        args.func(args)
        assert patch_get_client.put.call_count == 2
        for call in patch_get_client.put.call_args_list:
            assert call[1]["json_data"]["min_chunk"] == 1

    def test_list_machine_explicit_min_chunk_wins(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.put.return_value = mock_response(200, {"success": True})
        args = parse_argv(["list", "machine", "42", "-g", "0.5", "-m", "4"])
        args.func(args)
        body = patch_get_client.put.call_args[1]["json_data"]
        assert body["min_chunk"] == 4


class TestSelfTestMachineCleanup:
    def test_successful_destroy_does_not_warn_when_instance_is_already_gone(
        self, parse_argv, monkeypatch, capsys
    ):
        from vastai.cli.commands import machines

        offer = {
            "id": 777,
            "cuda_max_good": "13.0",
            "compute_cap": 860,
            "dlperf": 1,
            "reliability": 0.99,
            "direct_port_count": 4,
            "pcie_bw": 3.0,
            "gpu_total_ram": 12288,
            "inet_down": 500,
            "inet_up": 500,
            "gpu_ram": 8,
            "cpu_ram": 16000,
            "cpu_cores": 4,
            "num_gpus": 1,
        }
        running_instance = {
            "id": 123,
            "actual_status": "running",
            "intended_status": "running",
            "public_ipaddr": "127.0.0.1",
            "ports": {"5000/tcp": [{"HostPort": "5000"}]},
            "status_msg": "",
        }

        monkeypatch.setattr(machines.offers_api, "search_offers", Mock(return_value=[offer]))
        monkeypatch.setattr(machines.instances_api, "create_instance", Mock(return_value={"new_contract": 123}))
        monkeypatch.setattr(machines.instances_api, "show_instance", Mock(side_effect=[
            running_instance,
            running_instance,
            None,
        ]))
        destroy_instance = Mock(return_value={"success": True})
        monkeypatch.setattr(machines.instances_api, "destroy_instance", destroy_instance)
        monkeypatch.setattr(machines.requests, "get", lambda *_, **__: SimpleNamespace(status_code=200, text="DONE"))
        monkeypatch.setattr(machines.time, "sleep", lambda *_: None)

        args = parse_argv(["self-test", "machine", "46368"])
        with pytest.raises(SystemExit) as exit_info:
            args.func(args)

        assert exit_info.value.code == 0
        assert destroy_instance.call_count == 1
        captured = capsys.readouterr()
        assert "Instance 123 destroyed successfully on attempt 1." in captured.out
        assert "WARNING: failed to destroy test instance 123" not in captured.out
