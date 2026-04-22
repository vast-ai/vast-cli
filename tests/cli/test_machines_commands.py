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
