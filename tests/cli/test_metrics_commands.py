"""Tests for the metrics CLI commands with mocked HTTP."""

import json


def _history_payload():
    return {
        "success": True,
        "gpus": {
            "RTX 5090": {
                "stats": {"tflops": 109.2, "dlperf": 199.4, "tflops_per_dollar": 251.6},
                "supply_demand": {
                    "timestamps": [1_700_000_000, 1_700_000_300],
                    "rented_verified": [10, 11],
                    "avail_verified": [5, 4],
                    "rented_unverified": [2, 2],
                    "avail_unverified": [1, 1],
                    "unavail_verified": [3, 2],
                    "unavail_unverified": [1, 0],
                    "total": [22, 20],
                },
                "pricing": {"rented_median": [0.4, 0.41], "avail_median": [0.5, 0.5]},
            }
        },
    }


class TestGpuCurrent:
    def test_other_bucket_is_passed_through(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {"success": True, "gpus": []})
        args = parse_argv(["show", "gpu-metrics", "--num-gpus", "other", "--raw"])
        args.func(args)
        assert patch_get_client.get.call_args.kwargs["query_args"]["num_gpus"] == "other"


class TestGpuTrends:
    def test_raw_rows_carry_unavailable_counts(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, _history_payload())
        args = parse_argv(["show", "gpu-trends", "RTX_5090", "--raw"])
        args.func(args)
        rows = json.loads(capsys.readouterr().out)["RTX 5090"]["rows"]
        assert [r["unavail_verified"] for r in rows] == [3, 2]
        assert [r["unavail_unverified"] for r in rows] == [1, 0]

    def test_table_shows_unavailable_columns(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, _history_payload())
        args = parse_argv(["show", "gpu-trends", "RTX_5090", "--full", "--no-color"])
        args.func(args)
        out = capsys.readouterr().out
        assert "Unr/Ver" in out
        assert "-" not in out.split("\n")[3].split()[3:9]


class TestGpuLocations:
    LOCATIONS = [
        {"gpu_name": "RTX 4090", "state": "rented", "rented": True, "verified": True, "datacenter": False, "num_gpus": 1},
        {"gpu_name": "RTX 4090", "state": "available", "rented": False, "verified": True, "datacenter": False, "num_gpus": 2},
        {"gpu_name": "RTX 4090", "state": "unavailable", "rented": True, "verified": False, "datacenter": False, "num_gpus": 4},
        {"gpu_name": "H100 SXM", "rented": True, "verified": True, "datacenter": True, "num_gpus": 8},
    ]

    def _run(self, parse_argv, patch_get_client, mock_response, capsys, *flags):
        patch_get_client.get.return_value = mock_response(200, {"success": True, "locations": self.LOCATIONS})
        args = parse_argv(["show", "gpu-locations", "--raw", *flags])
        args.func(args)
        return json.loads(capsys.readouterr().out)["locations"]

    def test_rented_false_includes_unavailable(self, parse_argv, patch_get_client, mock_response, capsys):
        got = self._run(parse_argv, patch_get_client, mock_response, capsys, "--rented", "false")
        assert [l["num_gpus"] for l in got] == [2, 4]

    def test_state_filter(self, parse_argv, patch_get_client, mock_response, capsys):
        got = self._run(parse_argv, patch_get_client, mock_response, capsys, "--state", "unavailable")
        assert [l["num_gpus"] for l in got] == [4]

    def test_rented_true_falls_back_to_boolean_without_state(self, parse_argv, patch_get_client, mock_response, capsys):
        got = self._run(parse_argv, patch_get_client, mock_response, capsys, "--rented", "true")
        assert [l["num_gpus"] for l in got] == [1, 8]


class TestOldNames:
    def test_old_name_still_runs_and_prints_a_notice(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {"success": True, "gpus": []})
        args = parse_argv(["metrics", "gpu", "--raw"])
        args.func(args)
        err = capsys.readouterr().err
        assert "`vastai metrics gpu` is now `vastai show gpu-metrics`" in err

    def test_new_name_is_quiet(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {"success": True, "gpus": []})
        args = parse_argv(["show", "gpu-metrics", "--raw"])
        args.func(args)
        assert capsys.readouterr().err == ""

    def test_old_names_are_hidden_from_help(self, cli_parser):
        from vastai.cli.parser import build_command_maps
        verbs, verb_objs, _ = build_command_maps(cli_parser.parser, role="host")
        assert {"gpu-metrics", "gpu-trends", "gpu-locations"} <= verb_objs["show"]
        assert "metrics" not in verbs
