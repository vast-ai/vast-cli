"""Integration tests for machine CLI commands with mocked HTTP."""

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
        patch_get_client.get.return_value = mock_response(200, {"id": 1, "gpu_name": "RTX_3090"})
        args = parse_argv(["show", "machine", "1", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/machines/" in call_args[0][0]
