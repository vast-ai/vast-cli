"""Integration tests for machine CLI commands with mocked HTTP."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests


@pytest.fixture(autouse=True)
def _self_test_udp_probe_success(monkeypatch):
    """Default self-test machine tests to a successful external UDP echo probe."""
    from vastai.cli.commands import machines

    monkeypatch.setattr(machines, "CLI_VERSION", machines.SELF_TEST_MIN_CLI_VERSION)

    def _probe(public_ip, host_port, *, mapped_ports=None, attempts=3, timeout_seconds=2):
        return True, {
            "url": f"udp://{public_ip}:{host_port}",
            "public_ip": public_ip,
            "container_port": "5001/udp",
            "external_port": str(host_port),
            "host_port": str(host_port),
            "timeout_seconds": timeout_seconds,
            "attempt_count": 1,
            "response_received": True,
            "last_error_type": None,
            "last_error": None,
            "mapped_ports": sorted((mapped_ports or {}).keys()),
        }

    monkeypatch.setattr(machines, "probe_udp_echo", _probe)


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
            "ports": {"5000/tcp": [{"HostPort": "5000"}], "5001/udp": [{"HostPort": "5001"}]},
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

    def test_successful_runtime_reports_cleanup_failure_when_destroy_fails(
        self, parse_argv, monkeypatch
    ):
        from vastai.cli.commands import machines

        offer = _self_test_offer()
        running_instance = {
            "id": 123,
            "actual_status": "running",
            "intended_status": "running",
            "public_ipaddr": "127.0.0.1",
            "ports": {"5000/tcp": [{"HostPort": "5000"}], "5001/udp": [{"HostPort": "5001"}]},
            "status_msg": "",
        }

        monkeypatch.setattr(machines.offers_api, "search_offers", Mock(return_value=[offer]))
        monkeypatch.setattr(machines.instances_api, "create_instance", Mock(return_value={"new_contract": 123}))
        monkeypatch.setattr(machines.instances_api, "show_instance", Mock(return_value=running_instance))
        destroy_instance = Mock(side_effect=RuntimeError("api destroy failed"))
        monkeypatch.setattr(machines.instances_api, "destroy_instance", destroy_instance)
        monkeypatch.setattr(machines.requests, "get", lambda *_, **__: SimpleNamespace(status_code=200, text="DONE"))
        monkeypatch.setattr(machines.time, "sleep", lambda *_: None)

        args = parse_argv(["self-test", "machine", "46368", "--raw"])
        result = args.func(args)

        assert result["success"] is False
        assert result["failure_code"] == "cleanup_failed"
        assert result["stage"] == "cleanup"
        assert "failed to destroy test instance 123" in result["reason"]
        assert destroy_instance.call_count >= 10


class TestListMachineEpilogDoesNotPromiseEmail:
    """Regression: epilogs must not reference the email that no longer carries details."""

    def _epilog_lower(self, cli_parser, command):
        # The two-word command name keys into the registered subparser tree.
        sp = cli_parser.subparsers().choices[command]
        return (sp.epilog or "").lower()

    def test_list_machine_epilog_no_email(self, cli_parser):
        assert "email" not in self._epilog_lower(cli_parser, "list machine")

    def test_list_machines_epilog_no_email(self, cli_parser):
        assert "email" not in self._epilog_lower(cli_parser, "list machines")


class TestSelfTestMachineIgnoreRequirements:
    def test_ignore_requirements_warns_on_success(self, parse_argv, monkeypatch, capsys):
        from vastai.cli.commands import machines

        offer = {
            "id": 202,
            "dlperf": 1.0,
            "cuda_max_good": 13.0,
            "compute_cap": 1200,
            "reliability": 0.99,
            "direct_port_count": 10,
            "pcie_bw": 4.0,
            "gpu_total_ram": 32 * 1024,
            "inet_down": 200.0,
            "inet_up": 200.0,
            "gpu_ram": 32,
            "cpu_ram": 64 * 1024,
            "cpu_cores": 8,
            "num_gpus": 1,
        }
        instance = {
            "intended_status": "running",
            "actual_status": "running",
            "public_ipaddr": "203.0.113.10",
            "ports": {"5000/tcp": [{"HostPort": "5000"}], "5001/udp": [{"HostPort": "5001"}]},
        }

        monkeypatch.setattr(machines.offers_api, "search_offers", Mock(return_value=[offer]))
        monkeypatch.setattr(machines.instances_api, "create_instance", Mock(return_value={"new_contract": 303}))
        monkeypatch.setattr(machines.instances_api, "show_instance", Mock(return_value=instance))
        monkeypatch.setattr(machines.instances_api, "destroy_instance", Mock(return_value={"success": True}))
        monkeypatch.setattr(machines.requests, "get", lambda *_, **__: SimpleNamespace(status_code=200, text="DONE"))
        monkeypatch.setattr(machines.time, "sleep", lambda *_: None)

        args = parse_argv(["self-test", "machine", "123", "--ignore-requirements"])
        with pytest.raises(SystemExit) as exc_info:
            args.func(args)

        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "WARNING: --ignore-requirements is set." in out
        assert "Requirement checks are skipped as a pass/fail gate" in out
        assert "does not qualify this machine for verification" in out
        assert out.count("does not qualify this machine for verification") >= 2
        assert "Machine ID 123 passed the self-test." in out

    def test_ignore_requirements_warning_in_raw_summary(self, parse_argv, monkeypatch, capsys):
        from vastai.cli.commands import machines

        monkeypatch.setattr(machines.offers_api, "search_offers", Mock(return_value=[]))

        args = parse_argv(["--raw", "self-test", "machine", "0", "--ignore-requirements"])
        result = args.func(args)

        assert result["success"] is False
        assert capsys.readouterr().out == ""
        raw = result
        assert raw["success"] is False
        assert "warning" in raw
        assert "Requirement checks are skipped as a pass/fail gate" in raw["warning"]
        assert "does not qualify this machine for verification" in raw["warning"]


def _self_test_offer(**overrides):
    offer = {
        "id": 1001,
        "machine_id": "42",
        "gpu_name": "RTX_4090",
        "num_gpus": 1,
        "dph_total": 0.5,
        "dlperf": 100,
        "cuda_max_good": 12.8,
        "compute_cap": 890,
        "reliability": 0.99,
        "direct_port_count": 4,
        "pcie_bw": 3.2,
        "inet_down": 200,
        "inet_up": 200,
        "gpu_ram": 24,
        "gpu_total_ram": 24 * 1024,
        "cpu_ram": 32 * 1024,
        "cpu_cores": 4,
    }
    offer.update(overrides)
    return offer


def _http_error(status_code, message=None):
    response = Mock(status_code=status_code)
    error = requests.exceptions.HTTPError(
        message or f"{status_code} Client Error for url: https://console.vast.ai/api/v0/bundles/?api_key=secret"
    )
    error.response = response
    return error


def _run_self_test_until_create(parse_argv, monkeypatch, offer):
    monkeypatch.delenv("VAST_SELF_TEST_IMAGE", raising=False)
    monkeypatch.setattr(
        "vastai.cli.commands.machines.offers_api.search_offers",
        Mock(return_value=[offer]),
    )
    create = Mock(side_effect=RuntimeError("stop before live rental"))
    monkeypatch.setattr("vastai.cli.commands.machines.instances_api.create_instance", create)

    args = parse_argv(["self-test", "machine", "42", "--raw"])
    result = args.func(args)
    return result, create


class TestSelfTestMachineDiagnostics:
    def test_no_offer_raw_returns_structured_failure(
        self, parse_argv, patch_get_client, monkeypatch, capsys
    ):
        search = Mock(side_effect=[[], []])
        monkeypatch.setattr("vastai.cli.commands.machines.offers_api.search_offers", search)

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        captured = capsys.readouterr()
        assert captured.out == ""
        assert result["success"] is False
        assert result["reason"] == "No on-demand offer found for machine 42."
        assert result["failure_code"] == "no_offer"
        assert result["phase"] == "preflight"
        assert result["machine_id"] == "42"
        assert result["checks"][0]["id"] == "offer.available"
        assert result["failure"]["likely_causes"]
        assert result["failure"]["root_state"] == "offline_or_not_listed"
        assert result["failure"]["confidence"] == "low"
        assert search.call_count == 2

    def test_no_offer_with_visible_machine_reports_zero_active_offers(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        search = Mock(side_effect=[[], []])
        monkeypatch.setattr("vastai.cli.commands.machines.offers_api.search_offers", search)
        monkeypatch.setattr(
            "vastai.cli.commands.machines.machines_api.show_machine",
            Mock(return_value=[{"id": 42, "hostname": "host-42"}]),
        )

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        assert result["failure_code"] == "no_offer"
        assert result["failure"]["root_state"] == "zero_active_offers"
        assert result["failure"]["confidence"] == "medium"
        assert "Machine lookup returned a visible machine record." in result["failure"]["evidence"]
        assert result["diagnostics"]["offer_search"]["machine_lookup"]["row_count"] == 1

    def test_offer_search_permission_error_reports_api_permission_failed(
        self, parse_argv, patch_get_client, monkeypatch, capsys
    ):
        search = Mock(side_effect=_http_error(401))
        monkeypatch.setattr("vastai.cli.commands.machines.offers_api.search_offers", search)

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        captured = capsys.readouterr()
        assert captured.out == ""
        assert result["failure_code"] == "api_permission_failed"
        assert result["failure"]["root_state"] == "api_permission_failed"
        assert result["failure"]["confidence"] == "high"
        assert result["diagnostics"]["offer_search"]["search_error"]["status_code"] == 401
        assert "api_key=secret" not in str(result)
        assert search.call_count == 1

    def test_machine_lookup_permission_error_reports_api_permission_failed(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        search = Mock(side_effect=[[], []])
        monkeypatch.setattr("vastai.cli.commands.machines.offers_api.search_offers", search)
        monkeypatch.setattr(
            "vastai.cli.commands.machines.machines_api.show_machine",
            Mock(side_effect=_http_error(403)),
        )

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        assert result["failure_code"] == "api_permission_failed"
        assert result["failure"]["root_state"] == "api_permission_failed"
        assert result["diagnostics"]["offer_search"]["machine_lookup"]["status_code"] == 403

    def test_machine_lookup_transport_error_is_recorded_without_aborting(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        search = Mock(side_effect=[[], []])
        monkeypatch.setattr("vastai.cli.commands.machines.offers_api.search_offers", search)
        monkeypatch.setattr(
            "vastai.cli.commands.machines.machines_api.show_machine",
            Mock(
                side_effect=requests.exceptions.Timeout(
                    "timeout for url: https://console.vast.ai/api/v0/machines/42/?api_key=secret"
                )
            ),
        )

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        lookup = result["diagnostics"]["offer_search"]["machine_lookup"]
        assert result["failure_code"] == "no_offer"
        assert result["failure"]["root_state"] == "offline_or_not_listed"
        assert lookup["status"] == "lookup_error"
        assert lookup["status_code"] is None
        assert "api_key=REDACTED" in lookup["error"]
        assert "api_key=secret" not in str(result)

    def test_no_rentable_offer_reports_currently_rented_state(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        broader_offer = _self_test_offer(rentable=False, rented=True)
        search = Mock(side_effect=[[], [broader_offer]])
        monkeypatch.setattr("vastai.cli.commands.machines.offers_api.search_offers", search)

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        assert result["failure_code"] == "no_rentable_offer"
        assert result["failure"]["root_state"] == "currently_rented"
        assert result["failure"]["confidence"] == "medium"
        assert any("rented=true" in item for item in result["failure"]["evidence"])

    def test_no_rentable_offer_reports_deverified_or_below_threshold(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        broader_offer = _self_test_offer(
            rentable=False,
            rented=False,
            reliability=0.89,
            vericode=8,
            verified=False,
            error_description="direct port verification failed",
        )
        search = Mock(side_effect=[[], [broader_offer]])
        monkeypatch.setattr("vastai.cli.commands.machines.offers_api.search_offers", search)

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        assert result["failure_code"] == "no_rentable_offer"
        assert result["failure"]["root_state"] == "deverified_or_below_threshold"
        assert result["diagnostics"]["offer_search"]["broader_offers"][0]["vericode"] == 8
        assert result["diagnostics"]["offer_search"]["broader_offers"][0]["verified"] is False
        assert any("vericode=8" in item for item in result["failure"]["evidence"])

    def test_no_offer_non_raw_renders_once_without_stale_placeholders(
        self, parse_argv, patch_get_client, monkeypatch, capsys
    ):
        broader_offer = _self_test_offer(rentable=False, rented=True)
        search = Mock(side_effect=[[], [broader_offer]])
        monkeypatch.setattr("vastai.cli.commands.machines.offers_api.search_offers", search)

        args = parse_argv(["self-test", "machine", "42"])
        with pytest.raises(SystemExit) as exc_info:
            args.func(args)

        captured = capsys.readouterr()
        assert exc_info.value.code == 1
        assert captured.out.count("Preflight diagnostics for machine 42 failed:") == 1
        assert "actual: 0 offers" in captured.out
        assert "required: >= 1 offers" in captured.out
        assert "vastai search offers 'machine_id=42 rentable=any rented=any'" in captured.out
        assert "Root state: currently_rented" in captured.out
        assert "Suggested steps:" in captured.out
        assert "{machine_id}" not in captured.out
        assert "--filter" not in captured.out

    def test_preflight_outputs_actual_required_once(
        self, parse_argv, patch_get_client, monkeypatch, capsys
    ):
        bad_offer = _self_test_offer(cuda_max_good=11.7, reliability=0.9)
        search = Mock(return_value=[bad_offer])
        monkeypatch.setattr("vastai.cli.commands.machines.offers_api.search_offers", search)

        args = parse_argv(["self-test", "machine", "42"])
        with pytest.raises(SystemExit) as exc_info:
            args.func(args)

        captured = capsys.readouterr()
        assert exc_info.value.code == 1
        assert captured.out.count("Preflight diagnostics for machine 42 failed:") == 1
        assert "- CUDA version" in captured.out
        assert "actual: 11.7 CUDA" in captured.out
        assert "required: >= 11.8 CUDA" in captured.out
        assert "{machine_id}" not in captured.out
        assert "--filter" not in captured.out
        assert search.call_count == 1

    def test_selected_offer_is_reused_for_rental(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        lower_offer = _self_test_offer(id=1001, dlperf=10)
        selected_offer = _self_test_offer(id=2002, dlperf=50)
        search = Mock(return_value=[lower_offer, selected_offer])
        create = Mock(side_effect=RuntimeError("stop before live rental"))
        monkeypatch.setattr("vastai.cli.commands.machines.offers_api.search_offers", search)
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.create_instance", create)

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        assert result["failure_code"] == "instance_create_failed"
        assert search.call_count == 1
        create.assert_called_once()
        assert create.call_args.kwargs["id"] == 2002
        assert create.call_args.kwargs["runtype"] == "ssh_direc ssh_proxy"
        assert create.call_args.kwargs["jupyter_lab"] is False
        assert result["diagnostics"]["launch"]["runtype"] == "ssh_direc ssh_proxy"

    def test_preflight_normalizes_api_gpu_ram_units(
        self, parse_argv, patch_get_client, monkeypatch, capsys
    ):
        bad_offer = _self_test_offer(gpu_ram=6 * 1024, gpu_total_ram=0)
        search = Mock(return_value=[bad_offer])
        monkeypatch.setattr("vastai.cli.commands.machines.offers_api.search_offers", search)

        args = parse_argv(["self-test", "machine", "42"])
        with pytest.raises(SystemExit) as exc_info:
            args.func(args)

        captured = capsys.readouterr()
        assert exc_info.value.code == 1
        assert "- GPU RAM" in captured.out
        assert "actual: 6.0 GiB" in captured.out
        assert "required: > 7 GiB" in captured.out

    def test_preflight_uses_canonical_vram_for_b300(
        self, parse_argv, patch_get_client, monkeypatch, capsys
    ):
        offer = _self_test_offer(
            gpu_name="B300",
            gpu_ram=288,
            gpu_total_ram=288 * 1024,
            num_gpus=1,
            reliability=0.9,
            cpu_ram=320 * 1024,
        )
        search = Mock(return_value=[offer])
        monkeypatch.setattr("vastai.cli.commands.machines.offers_api.search_offers", search)

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        captured = capsys.readouterr()
        gpu_ram_check = next(check for check in result["checks"] if check["id"] == "gpu.ram")
        raw = json.dumps(result)
        assert result["failure_code"] == "preflight_requirements_failed"
        assert gpu_ram_check["status"] == "pass"
        assert gpu_ram_check["actual"] == 288
        assert "0.28" not in captured.out
        assert "0.28125" not in captured.out
        assert "0.28" not in raw
        assert "0.28125" not in raw

    def test_preflight_uses_canonical_total_ram_per_gpu(self):
        from vastai.cli.self_test.machine_diagnostics import preflight_requirement_checks

        offer = _self_test_offer(
            gpu_ram=288,
            gpu_total_ram=8 * 80 * 1024,
            num_gpus=8,
            cpu_ram=700 * 1024,
            cpu_cores=24,
        )

        checks = preflight_requirement_checks(offer)
        gpu_ram_check = next(check for check in checks if check["id"] == "gpu.ram")
        assert gpu_ram_check["status"] == "pass"
        assert gpu_ram_check["actual"] == 80

    def test_preflight_direct_port_overage_is_not_advisory_or_gate(self):
        from vastai.cli.self_test.machine_diagnostics import (
            failed_checks,
            informational_checks,
            preflight_requirement_checks,
        )

        offer = _self_test_offer(
            num_gpus=8,
            gpu_ram=24 * 1024,
            gpu_total_ram=8 * 24 * 1024,
            cpu_ram=256 * 1024,
            cpu_cores=32,
            direct_port_count=1000,
            inet_down=600,
            inet_up=600,
        )

        checks = preflight_requirement_checks(offer)
        direct_ports = next(check for check in checks if check["id"] == "network.direct_ports")

        assert direct_ports["status"] == "pass"
        assert informational_checks(checks) == []
        assert direct_ports not in failed_checks(checks)

    def test_preflight_direct_port_minimum_scales_by_gpu_count(self):
        from vastai.cli.self_test.machine_diagnostics import preflight_requirement_checks

        offer = _self_test_offer(
            num_gpus=8,
            gpu_ram=24 * 1024,
            gpu_total_ram=8 * 24 * 1024,
            cpu_ram=256 * 1024,
            cpu_cores=32,
            direct_port_count=20,
            inet_down=600,
            inet_up=600,
        )

        checks = preflight_requirement_checks(offer)
        direct_ports = next(check for check in checks if check["id"] == "network.direct_ports")

        assert direct_ports["status"] == "fail"
        assert direct_ports["actual"] == 20
        assert direct_ports["required"] == 24
        assert direct_ports["operator"] == ">="
        assert "3 directly mapped ports per listed GPU" in direct_ports["purpose"]

    def test_preflight_does_not_gate_on_virtual_cpu_count(self):
        from vastai.cli.self_test.machine_diagnostics import (
            failed_checks,
            preflight_requirement_checks,
        )

        offer = _self_test_offer(
            num_gpus=8,
            gpu_ram=24 * 1024,
            gpu_total_ram=8 * 24 * 1024,
            cpu_ram=256 * 1024,
            cpu_cores=1,
            direct_port_count=24,
            inet_down=600,
            inet_up=600,
        )

        checks = preflight_requirement_checks(offer)

        assert "cpu.cores" not in {check["id"] for check in checks}
        assert failed_checks(checks) == []

    def test_preflight_direct_port_overage_does_not_render_advisory(
        self, parse_argv, patch_get_client, monkeypatch, capsys
    ):
        offer = _self_test_offer(
            num_gpus=8,
            gpu_ram=24 * 1024,
            gpu_total_ram=8 * 24 * 1024,
            cpu_ram=256 * 1024,
            cpu_cores=32,
            direct_port_count=1000,
            inet_down=600,
            inet_up=600,
            reliability=0.9,
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )

        args = parse_argv(["self-test", "machine", "42"])
        with pytest.raises(SystemExit) as exc_info:
            args.func(args)

        captured = capsys.readouterr()
        assert exc_info.value.code == 1
        assert "Preflight advisory for machine 42:" not in captured.out
        assert "Direct port count advisory" not in captured.out
        assert "recommended: <= 512 ports" not in captured.out

    def test_preflight_caps_system_ram_requirement_for_huge_vram_hosts(self):
        from vastai.cli.self_test.machine_diagnostics import preflight_requirement_checks

        offer = _self_test_offer(
            gpu_name="B300 SXM6 AC",
            num_gpus=8,
            gpu_ram=275040,
            gpu_total_ram=2200320,
            cpu_ram=2063831,
            cpu_cores=192,
            direct_port_count=998,
            inet_down=600,
            inet_up=600,
        )

        checks = preflight_requirement_checks(offer)
        system_ram = next(check for check in checks if check["id"] == "system.ram")

        assert system_ram["status"] == "pass"
        assert system_ram["actual"] == 2063831
        assert system_ram["required"] == 2000000
        assert "2 TB" in system_ram["purpose"]

    def test_preflight_system_ram_cap_still_fails_below_two_tb(self):
        from vastai.cli.self_test.machine_diagnostics import preflight_requirement_checks

        offer = _self_test_offer(
            gpu_name="B300 SXM6 AC",
            num_gpus=8,
            gpu_ram=275040,
            gpu_total_ram=2200320,
            cpu_ram=1900000,
            cpu_cores=192,
            direct_port_count=998,
            inet_down=600,
            inet_up=600,
        )

        checks = preflight_requirement_checks(offer)
        system_ram = next(check for check in checks if check["id"] == "system.ram")

        assert system_ram["status"] == "fail"
        assert system_ram["actual"] == 1900000
        assert system_ram["required"] == 2000000

    def test_ignore_requirements_includes_failed_checks_and_continues(
        self, parse_argv, patch_get_client, monkeypatch, capsys
    ):
        bad_offer = _self_test_offer(reliability=0.9)
        search = Mock(return_value=[bad_offer])
        create = Mock(side_effect=RuntimeError("stop before live rental"))
        monkeypatch.setattr("vastai.cli.commands.machines.offers_api.search_offers", search)
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.create_instance", create)

        args = parse_argv(["self-test", "machine", "42", "--ignore-requirements"])
        with pytest.raises(SystemExit) as exc_info:
            args.func(args)

        captured = capsys.readouterr()
        assert exc_info.value.code == 1
        assert "Continuing despite unmet requirements because --ignore-requirements is set." in captured.out
        assert "WARNING: --ignore-requirements is set." in captured.out
        assert "does not qualify this machine for verification" in captured.out
        create.assert_called_once()
        assert search.call_count == 1

    def test_ignore_requirements_runtime_success_preserves_preflight_as_metadata(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        from vastai.cli.commands import machines

        bad_offer = _self_test_offer(gpu_ram=6 * 1024, gpu_total_ram=6 * 1024, inet_up=98)
        running_instance = {
            "id": 123,
            "actual_status": "running",
            "intended_status": "running",
            "public_ipaddr": "127.0.0.1",
            "ports": {"5000/tcp": [{"HostPort": "5000"}], "5001/udp": [{"HostPort": "5001"}]},
            "status_msg": "",
        }
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[bad_offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.create_instance",
            Mock(return_value={"new_contract": 123}),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.show_instance",
            Mock(side_effect=[running_instance, running_instance, None]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.destroy_instance",
            Mock(return_value={"success": True}),
        )
        monkeypatch.setattr(machines.requests, "get", lambda *_, **__: SimpleNamespace(status_code=200, text="DONE"))
        monkeypatch.setattr(machines.time, "sleep", lambda *_: None)

        args = parse_argv(["self-test", "machine", "42", "--ignore-requirements", "--raw"])
        result = args.func(args)

        assert result["success"] is True
        assert result["failure_code"] is None
        assert result["failure"] is None
        assert result["warning"]
        assert result["diagnostics"]["requirements_ignored"] is True
        assert result["diagnostics"]["preflight_failure"]["code"] == "preflight_requirements_failed"
        assert result["diagnostics"].get("runtime_failure") is None
        assert {check["id"] for check in result["checks"] if check["status"] == "fail"} == {
            "network.upload",
            "gpu.ram",
        }

    def test_test_image_option_overrides_default_mapping(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer()
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        create = Mock(side_effect=RuntimeError("stop before live rental"))
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.create_instance", create)

        args = parse_argv(["self-test", "machine", "42", "--test-image", "vastai/test:p3-dogfood", "--raw"])
        result = args.func(args)

        assert result["diagnostics"]["image"]["override"] is True
        assert create.call_args.kwargs["image"] == "vastai/test:p3-dogfood"
        assert create.call_args.kwargs["runtype"] == "ssh_direc ssh_proxy"

    def test_env_test_image_overrides_default_mapping(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer()
        monkeypatch.setenv("VAST_SELF_TEST_IMAGE", "vastai/test:p3-env")
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        create = Mock(side_effect=RuntimeError("stop before live rental"))
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.create_instance", create)

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        assert result["diagnostics"]["image"]["override"] is True
        assert create.call_args.kwargs["image"] == "vastai/test:p3-env"
        assert create.call_args.kwargs["runtype"] == "ssh_direc ssh_proxy"

    def test_status_poll_timeout_reports_status_poll_failure(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer()
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.create_instance",
            Mock(return_value={"new_contract": 123}),
        )
        show = Mock(
            side_effect=[
                RuntimeError("status API unavailable"),
                {"id": 123, "actual_status": "running", "intended_status": "running"},
            ]
        )
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.show_instance", show)
        destroy = Mock(return_value={"success": True})
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.destroy_instance", destroy)
        monkeypatch.setattr("vastai.cli.commands.machines.time.sleep", lambda *_: None)
        monkeypatch.setattr(
            "vastai.cli.commands.machines.time.time",
            Mock(side_effect=[0, 0, 901]),
        )

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        assert result["success"] is False
        assert result["failure_code"] == "instance_status_poll_failed"
        assert result["stage"] == "startup"
        assert "status API unavailable" in result["reason"]
        assert result["failure"]["underlying_error"] == "RuntimeError: status API unavailable"
        destroy.assert_called_once()

    def test_unexpected_self_test_exception_is_structured_and_redacted(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer()
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.preflight_requirement_checks",
            Mock(side_effect=RuntimeError("boom https://console.vast.ai/?api_key=secret")),
        )

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        assert result["success"] is False
        assert result["failure_code"] == "unexpected_error"
        assert result["failure"]["code"] == "unexpected_error"
        assert result["diagnostics"]["runtime_failure"]["code"] == "unexpected_error"
        assert result["failure"]["stage"] == "preflight_checks"
        assert "api_key=secret" not in result["reason"]
        assert "api_key=REDACTED" in result["reason"]

    def test_default_cuda_mapping_still_selects_official_image(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer(cuda_max_good=12.8, compute_cap=890)
        result, create = _run_self_test_until_create(parse_argv, monkeypatch, offer)

        assert result["diagnostics"]["image"]["override"] is False
        assert create.call_args.kwargs["image"] == "vastai/test:self-test-cli-1.2.2-cuda-12.8"
        assert create.call_args.kwargs["runtype"] == "ssh_direc ssh_proxy"
        assert create.call_args.kwargs["label"] == "vast-self-test-machine-42"
        assert result["diagnostics"]["launch"]["label"] == "vast-self-test-machine-42"
        assert result["diagnostics"]["launch"]["ports"] == ["5000/tcp", "1234/tcp", "5001/udp"]
        assert result["diagnostics"]["cli"]["self_test_min_cli_version"] == "1.2.2"
        assert result["diagnostics"]["cli"]["self_test_contract_version"] == "1.2.2"
        assert result["diagnostics"]["cli"]["self_test_image_tag_prefix"] == "self-test-cli-1.2.2-cuda"
        env = create.call_args.kwargs["env"]
        assert env["VAST_SELF_TEST_CLI_VERSION"] == "1.2.2"
        assert env["VAST_SELF_TEST_CLI_CONTRACT_VERSION"] == "1.2.2"

    def test_cuda_mapping_selects_cuda_133_exact_match(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer(cuda_max_good=13.3, compute_cap=890)
        result, create = _run_self_test_until_create(parse_argv, monkeypatch, offer)

        assert result["diagnostics"]["image"]["override"] is False
        assert create.call_args.kwargs["image"] == "vastai/test:self-test-cli-1.2.2-cuda-13.3"
        assert "exact match" in result["diagnostics"]["image"]["reason"]

    def test_cuda_mapping_steps_down_to_newest_compatible_image(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer(cuda_max_good=13.2, compute_cap=890)
        result, create = _run_self_test_until_create(parse_argv, monkeypatch, offer)

        assert result["diagnostics"]["image"]["override"] is False
        assert create.call_args.kwargs["image"] == "vastai/test:self-test-cli-1.2.2-cuda-13.0"
        assert "selected newest image <= host CUDA (13.0)" in result["diagnostics"]["image"]["reason"]

    def test_cuda_mapping_uses_cuda_133_for_newer_cuda_hosts(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer(cuda_max_good=13.4, compute_cap=890)
        result, create = _run_self_test_until_create(parse_argv, monkeypatch, offer)

        assert result["diagnostics"]["image"]["override"] is False
        assert create.call_args.kwargs["image"] == "vastai/test:self-test-cli-1.2.2-cuda-13.3"
        assert "selected newest image <= host CUDA (13.3)" in result["diagnostics"]["image"]["reason"]

    def test_cuda_mapping_still_clamps_volta_to_cuda_128(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer(cuda_max_good=13.3, compute_cap=700)
        result, create = _run_self_test_until_create(parse_argv, monkeypatch, offer)

        assert result["diagnostics"]["image"]["override"] is False
        assert create.call_args.kwargs["image"] == "vastai/test:self-test-cli-1.2.2-cuda-12.8"
        assert "clamped to 12.8" in result["diagnostics"]["image"]["reason"]

    def test_startup_status_msg_is_classified_in_raw_output(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer()
        status_msg = "Error response from daemon: manifest for vastai/test:self-test-cli-1.2.2-cuda-99 not found"
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.create_instance",
            Mock(return_value={"new_contract": 123}),
        )
        show = Mock(
            side_effect=[
                {
                    "id": 123,
                    "status_msg": status_msg,
                    "actual_status": "created",
                    "intended_status": "running",
                },
                {"id": 123, "actual_status": "running", "intended_status": "running"},
                {"id": 123, "actual_status": "destroyed", "intended_status": "destroyed"},
            ]
        )
        destroy = Mock(return_value={"success": True})
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.show_instance", show)
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.destroy_instance", destroy)

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        assert result["success"] is False
        assert result["failure_code"] == "docker_pull_failed"
        assert result["failure"]["underlying_error"] == status_msg
        assert result["diagnostics"]["runtime_failure"]["code"] == "docker_pull_failed"
        destroy.assert_called_once()

    def test_startup_daemon_output_is_compact_without_debugging(
        self, parse_argv, patch_get_client, monkeypatch, capsys
    ):
        offer = _self_test_offer()
        status_msg = (
            "#7 0.829   libappstream5 libargon2-1 libbrotli1 libcap2-bin libcbor0.10\n"
            "#7 0.829   liberror-perl libevent-core-2.1-7t64 libfdisk1 libfido2-1"
        )
        failed_instance = {
            "id": 123,
            "status_msg": status_msg,
            "actual_status": "error",
            "intended_status": "running",
        }
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.create_instance",
            Mock(return_value={"new_contract": 123}),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.show_instance",
            Mock(side_effect=[failed_instance, failed_instance]),
        )
        destroy = Mock(return_value={"success": True})
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.destroy_instance", destroy)

        args = parse_argv(["self-test", "machine", "42"])
        with pytest.raises(SystemExit) as exc_info:
            args.func(args)

        captured = capsys.readouterr()
        assert exc_info.value.code == 1
        assert "- code: daemon_startup_failed" in captured.out
        assert "- daemon/status output: captured in raw output and the diagnostic bundle; use --debugging to print it." in captured.out
        assert "#7 0.829" not in captured.out
        assert "liberror-perl" not in captured.out
        destroy.assert_called_once()

    def test_startup_daemon_output_prints_raw_evidence_with_debugging(
        self, parse_argv, patch_get_client, monkeypatch, capsys
    ):
        offer = _self_test_offer()
        status_msg = (
            "#7 0.829   libappstream5 libargon2-1 libbrotli1 libcap2-bin libcbor0.10\n"
            "#7 0.829   liberror-perl libevent-core-2.1-7t64 libfdisk1 libfido2-1"
        )
        failed_instance = {
            "id": 123,
            "status_msg": status_msg,
            "actual_status": "error",
            "intended_status": "running",
        }
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.create_instance",
            Mock(return_value={"new_contract": 123}),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.show_instance",
            Mock(side_effect=[failed_instance, failed_instance]),
        )
        destroy = Mock(return_value={"success": True})
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.destroy_instance", destroy)

        args = parse_argv(["self-test", "machine", "42", "--debugging"])
        with pytest.raises(SystemExit) as exc_info:
            args.func(args)

        captured = capsys.readouterr()
        assert exc_info.value.code == 1
        assert "- code: daemon_startup_failed" in captured.out
        assert "- raw daemon/status text:" in captured.out
        assert "#7 0.829   libappstream5" in captured.out
        assert "#7 0.829   liberror-perl" in captured.out
        destroy.assert_called_once()

    def test_self_test_debuging_alias_enables_debugging(self, parse_argv):
        args = parse_argv(["self-test", "machine", "42", "--debuging"])

        assert args.debugging is True

    def test_stopped_startup_status_is_classified_without_waiting_for_timeout(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer()
        status_msg = "docker_build() error writing dockerfile"
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.create_instance",
            Mock(return_value={"new_contract": 123}),
        )
        stopped_instance = {
            "id": 123,
            "status_msg": status_msg,
            "actual_status": "loading",
            "intended_status": "stopped",
        }
        show = Mock(side_effect=[stopped_instance, stopped_instance, None])
        destroy = Mock(return_value={"success": True})
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.show_instance", show)
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.destroy_instance", destroy)

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        assert result["success"] is False
        assert result["failure_code"] == "daemon_startup_failed"
        assert result["failure"]["underlying_error"] == status_msg
        assert result["diagnostics"]["runtime_failure"]["code"] == "daemon_startup_failed"
        assert show.call_count == 3
        destroy.assert_called_once()

    def test_cleanup_404_after_destroy_is_not_reported_as_leak(
        self, parse_argv, patch_get_client, monkeypatch, capsys
    ):
        offer = _self_test_offer()
        status_msg = "Error: container failed to start: OCI runtime create failed"
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.create_instance",
            Mock(return_value={"new_contract": 123}),
        )
        response = Mock(status_code=404)
        gone = requests.exceptions.HTTPError("404 Client Error: Not Found for url: https://example.test/?api_key=secret")
        gone.response = response
        show = Mock(
            side_effect=[
                {
                    "id": 123,
                    "status_msg": status_msg,
                    "actual_status": "created",
                    "intended_status": "running",
                },
                {"id": 123, "actual_status": "running", "intended_status": "running"},
                gone,
            ]
        )
        destroy = Mock(return_value={"success": True})
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.show_instance", show)
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.destroy_instance", destroy)

        args = parse_argv(["self-test", "machine", "42"])
        with pytest.raises(SystemExit) as exc_info:
            args.func(args)

        captured = capsys.readouterr()
        assert exc_info.value.code == 1
        assert "Runtime failure diagnostics:" in captured.out
        assert "- code: daemon_startup_failed" in captured.out
        assert "- remediation: Inspect docker daemon, OCI runtime, container startup, and host daemon logs." in captured.out
        assert "WARNING: failed to destroy test instance" not in captured.out
        assert "api_key=secret" not in captured.out
        destroy.assert_called_once()

    def test_create_instance_error_redacts_api_key(
        self, parse_argv, patch_get_client, monkeypatch, capsys
    ):
        offer = _self_test_offer()
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        create = Mock(
            side_effect=RuntimeError(
                "404 Client Error: Not Found for url: https://console.vast.ai/api/v0/instances/?api_key=secret"
            )
        )
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.create_instance", create)

        args = parse_argv(["self-test", "machine", "42"])
        with pytest.raises(SystemExit) as exc_info:
            args.func(args)

        captured = capsys.readouterr()
        assert exc_info.value.code == 1
        assert "api_key=secret" not in captured.out
        assert "api_key=REDACTED" in captured.out

    def test_missing_progress_port_reports_available_ports(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer()
        running_instance = {
            "id": 123,
            "actual_status": "running",
            "intended_status": "running",
            "public_ipaddr": "127.0.0.1",
            "ports": {"22/tcp": [{"HostPort": "40022"}]},
            "status_msg": "",
        }
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.create_instance",
            Mock(return_value={"new_contract": 123}),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.show_instance",
            Mock(return_value=running_instance),
        )
        destroy = Mock(return_value={"success": True})
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.destroy_instance", destroy)
        monkeypatch.setattr("vastai.cli.commands.machines.time.sleep", lambda *_: None)

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        endpoint = result["diagnostics"]["progress_endpoint"]
        assert result["failure_code"] == "progress_port_not_mapped"
        assert endpoint["container_port"] == "5000/tcp"
        assert endpoint["external_port"] is None
        assert endpoint["host_port"] is None
        assert endpoint["mapped_ports"] == ["22/tcp"]
        assert result["diagnostics"]["runtime_failure"]["progress_endpoint"] == endpoint
        assert destroy.call_count >= 1

    def test_missing_udp_port_reports_available_ports(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer()
        running_instance = {
            "id": 123,
            "actual_status": "running",
            "intended_status": "running",
            "public_ipaddr": "127.0.0.1",
            "ports": {"5000/tcp": [{"HostPort": "45000"}], "22/tcp": [{"HostPort": "40022"}]},
            "status_msg": "",
        }
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.create_instance",
            Mock(return_value={"new_contract": 123}),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.show_instance",
            Mock(return_value=running_instance),
        )
        destroy = Mock(return_value={"success": True})
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.destroy_instance", destroy)
        monkeypatch.setattr("vastai.cli.commands.machines.time.sleep", lambda *_: None)

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        udp_probe = result["diagnostics"]["udp_probe"]
        assert result["failure_code"] == "udp_port_not_mapped"
        assert udp_probe["container_port"] == "5001/udp"
        assert udp_probe["external_port"] is None
        assert udp_probe["mapped_ports"] == ["22/tcp", "5000/tcp"]
        assert result["diagnostics"]["runtime_failure"]["udp_probe"] == udp_probe
        assert destroy.call_count >= 1

    def test_udp_probe_failure_after_tcp_success_is_distinct(
        self, parse_argv, patch_get_client, monkeypatch, capsys
    ):
        offer = _self_test_offer()
        running_instance = {
            "id": 123,
            "actual_status": "running",
            "intended_status": "running",
            "public_ipaddr": "127.0.0.1",
            "ports": {"5000/tcp": [{"HostPort": "45000"}], "5001/udp": [{"HostPort": "45001"}]},
            "status_msg": "",
        }
        udp_diagnostic = {
            "url": "udp://127.0.0.1:45001",
            "public_ip": "127.0.0.1",
            "container_port": "5001/udp",
            "external_port": "45001",
            "host_port": "45001",
            "timeout_seconds": 2,
            "attempt_count": 3,
            "response_received": False,
            "last_error_type": "TimeoutError",
            "last_error": "timed out",
            "mapped_ports": ["5000/tcp", "5001/udp"],
        }
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.create_instance",
            Mock(return_value={"new_contract": 123}),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.show_instance",
            Mock(return_value=running_instance),
        )
        destroy = Mock(return_value={"success": True})
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.destroy_instance", destroy)
        monkeypatch.setattr("vastai.cli.commands.machines.time.sleep", lambda *_: None)
        monkeypatch.setattr(
            "vastai.cli.commands.machines.requests.get",
            Mock(return_value=SimpleNamespace(status_code=200, text="Starting tests...")),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.probe_udp_echo",
            Mock(return_value=(False, udp_diagnostic)),
        )

        args = parse_argv(["self-test", "machine", "42"])
        with pytest.raises(SystemExit) as exc_info:
            args.func(args)

        captured = capsys.readouterr()
        assert exc_info.value.code == 1
        assert "Successfully established HTTPS connection to the server." in captured.out
        assert "UDP self-test probe failed after TCP progress endpoint was reachable." in captured.out
        assert "External UDP port tested: 45001" in captured.out
        assert "- code: udp_probe_failed" in captured.out
        assert "- UDP tried: udp://127.0.0.1:45001" in captured.out
        assert destroy.call_count >= 1

    def test_wait_for_instance_loading_status_is_compact_without_debugging(
        self, parse_argv, patch_get_client, monkeypatch, capsys
    ):
        offer = _self_test_offer()
        loading_instance = {
            "id": 123,
            "actual_status": "loading",
            "intended_status": "running",
            "status_msg": "ff81e2caff08: Verifying Checksum\nff81e2caff08: Download complete",
        }
        running_instance = {
            "id": 123,
            "actual_status": "running",
            "intended_status": "running",
            "public_ipaddr": "127.0.0.1",
            "ports": {"5000/tcp": [{"HostPort": "45000"}], "5001/udp": [{"HostPort": "45001"}]},
            "status_msg": "",
        }
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.create_instance",
            Mock(return_value={"new_contract": 123}),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.show_instance",
            Mock(side_effect=[loading_instance, loading_instance, running_instance, running_instance]),
        )
        destroy = Mock(return_value={"success": True})
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.destroy_instance", destroy)
        monkeypatch.setattr("vastai.cli.commands.machines.requests.get", Mock(return_value=SimpleNamespace(status_code=200, text="DONE")))
        monkeypatch.setattr("vastai.cli.commands.machines.time.sleep", lambda *_: None)

        args = parse_argv(["self-test", "machine", "42"])
        with pytest.raises(SystemExit) as exc_info:
            args.func(args)

        captured = capsys.readouterr()
        assert exc_info.value.code == 0
        assert "Instance 123 is loading; waiting for running status..." in captured.out
        assert "Still loading... 0s elapsed" in captured.out
        assert "Instance 123 is ready after 0s." in captured.out
        assert "status: loading" not in captured.out
        assert "status_msg:" not in captured.out
        assert "Verifying Checksum" not in captured.out
        assert destroy.call_count >= 1

    def test_wait_for_instance_does_not_treat_liberror_package_as_startup_error(
        self, parse_argv, patch_get_client, monkeypatch, capsys
    ):
        offer = _self_test_offer()
        daemon_build_output = (
            "#7 0.829   libappstream5 libargon2-1 libbrotli1 libcap2-bin libcbor0.10\n"
            "#7 0.829   liberror-perl libevent-core-2.1-7t64 libfdisk1 libfido2-1"
        )
        loading_instance = {
            "id": 123,
            "actual_status": "loading",
            "intended_status": "running",
            "status_msg": daemon_build_output,
        }
        running_instance = {
            "id": 123,
            "actual_status": "running",
            "intended_status": "running",
            "public_ipaddr": "127.0.0.1",
            "ports": {"5000/tcp": [{"HostPort": "45000"}], "5001/udp": [{"HostPort": "45001"}]},
            "status_msg": "",
        }
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.create_instance",
            Mock(return_value={"new_contract": 123}),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.show_instance",
            Mock(side_effect=[loading_instance, running_instance, running_instance]),
        )
        destroy = Mock(return_value={"success": True})
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.destroy_instance", destroy)
        monkeypatch.setattr(
            "vastai.cli.commands.machines.requests.get",
            Mock(return_value=SimpleNamespace(status_code=200, text="DONE")),
        )
        monkeypatch.setattr("vastai.cli.commands.machines.time.sleep", lambda *_: None)

        args = parse_argv(["self-test", "machine", "42"])
        with pytest.raises(SystemExit) as exc_info:
            args.func(args)

        captured = capsys.readouterr()
        assert exc_info.value.code == 0
        assert "reported a startup failure" not in captured.out
        assert "liberror-perl" not in captured.out
        assert destroy.call_count >= 1

    def test_wait_for_instance_loading_status_is_verbose_with_debugging(
        self, parse_argv, patch_get_client, monkeypatch, capsys
    ):
        offer = _self_test_offer()
        loading_instance = {
            "id": 123,
            "actual_status": "loading",
            "intended_status": "running",
            "status_msg": "ff81e2caff08: Verifying Checksum\nff81e2caff08: Download complete",
        }
        running_instance = {
            "id": 123,
            "actual_status": "running",
            "intended_status": "running",
            "public_ipaddr": "127.0.0.1",
            "ports": {"5000/tcp": [{"HostPort": "45000"}], "5001/udp": [{"HostPort": "45001"}]},
            "status_msg": "",
        }
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.create_instance",
            Mock(return_value={"new_contract": 123}),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.show_instance",
            Mock(side_effect=[loading_instance, running_instance, running_instance]),
        )
        destroy = Mock(return_value={"success": True})
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.destroy_instance", destroy)
        monkeypatch.setattr("vastai.cli.commands.machines.requests.get", Mock(return_value=SimpleNamespace(status_code=200, text="DONE")))
        monkeypatch.setattr("vastai.cli.commands.machines.time.sleep", lambda *_: None)

        args = parse_argv(["self-test", "machine", "42", "--debugging"])
        with pytest.raises(SystemExit) as exc_info:
            args.func(args)

        captured = capsys.readouterr()
        assert exc_info.value.code == 0
        assert "Instance 123 status: loading / intended: running; waiting for 'running' status." in captured.out
        assert "status_msg: ff81e2caff08: Verifying Checksum" in captured.out
        assert "Instance 123 is loading; waiting for running status" not in captured.out
        assert "Still loading..." not in captured.out
        assert destroy.call_count >= 1

    def test_progress_endpoint_never_reachable_records_endpoint_diagnostic(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer()
        running_instance = {
            "id": 123,
            "actual_status": "running",
            "intended_status": "running",
            "public_ipaddr": "127.0.0.1",
            "ports": {"5000/tcp": [{"HostPort": "45000"}], "22/tcp": [{"HostPort": "40022"}], "5001/udp": [{"HostPort": "45001"}]},
            "status_msg": "",
        }
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.create_instance",
            Mock(return_value={"new_contract": 123}),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.show_instance",
            Mock(return_value=running_instance),
        )
        destroy = Mock(return_value={"success": True})
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.destroy_instance", destroy)
        monkeypatch.setattr("vastai.cli.commands.machines.time.sleep", lambda *_: None)
        monkeypatch.setattr(
            "vastai.cli.commands.machines.requests.get",
            Mock(side_effect=requests.exceptions.ConnectTimeout("timed out for ?api_key=secret")),
        )

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        endpoint = result["diagnostics"]["progress_endpoint"]
        assert result["failure_code"] == "progress_endpoint_unreachable"
        assert endpoint["url"] == "https://127.0.0.1:45000/progress"
        assert endpoint["public_ip"] == "127.0.0.1"
        assert endpoint["external_port"] == "45000"
        assert endpoint["host_port"] == "45000"
        assert endpoint["attempt_count"] >= 6
        assert endpoint["first_connection_established"] is False
        assert endpoint["last_error_type"] == "ConnectTimeout"
        assert "api_key=secret" not in endpoint["last_error"]
        assert "api_key=REDACTED" in endpoint["last_error"]
        assert endpoint["mapped_ports"] == ["22/tcp", "5000/tcp", "5001/udp"]
        assert result["diagnostics"]["runtime_failure"]["progress_endpoint"] == endpoint
        assert destroy.call_count >= 1

    def test_progress_endpoint_failure_prints_external_port(
        self, parse_argv, patch_get_client, monkeypatch, capsys
    ):
        offer = _self_test_offer()
        running_instance = {
            "id": 123,
            "actual_status": "running",
            "intended_status": "running",
            "public_ipaddr": "127.0.0.1",
            "ports": {"5000/tcp": [{"HostPort": "45000"}], "22/tcp": [{"HostPort": "40022"}], "5001/udp": [{"HostPort": "45001"}]},
            "status_msg": "",
        }
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.create_instance",
            Mock(return_value={"new_contract": 123}),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.show_instance",
            Mock(return_value=running_instance),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.destroy_instance",
            Mock(return_value={"success": True}),
        )
        monkeypatch.setattr("vastai.cli.commands.machines.time.sleep", lambda *_: None)
        monkeypatch.setattr(
            "vastai.cli.commands.machines.requests.get",
            Mock(side_effect=requests.exceptions.ConnectTimeout("timed out")),
        )

        args = parse_argv(["self-test", "machine", "42"])
        with pytest.raises(SystemExit) as exc_info:
            args.func(args)

        captured = capsys.readouterr()
        assert exc_info.value.code == 1
        assert "External port tested: 45000" in captured.out
        assert "- external port tested: 45000" in captured.out
        assert "- mapped container ports: 22/tcp, 5000/tcp, 5001/udp" in captured.out

    def test_progress_endpoint_lost_after_success_records_different_failure(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer()
        running_instance = {
            "id": 123,
            "actual_status": "running",
            "intended_status": "running",
            "public_ipaddr": "127.0.0.1",
            "ports": {"5000/tcp": [{"HostPort": "45000"}], "5001/udp": [{"HostPort": "45001"}]},
            "status_msg": "",
        }
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.create_instance",
            Mock(return_value={"new_contract": 123}),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.show_instance",
            Mock(return_value=running_instance),
        )
        destroy = Mock(return_value={"success": True})
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.destroy_instance", destroy)
        monkeypatch.setattr("vastai.cli.commands.machines.time.sleep", lambda *_: None)
        get = Mock(
            side_effect=[
                SimpleNamespace(status_code=200, text="Starting tests..."),
                requests.exceptions.ConnectionError("connection refused"),
                requests.exceptions.ConnectionError("connection refused"),
                requests.exceptions.ConnectionError("connection refused"),
                requests.exceptions.ConnectionError("connection refused"),
                requests.exceptions.ConnectionError("connection refused"),
                requests.exceptions.ConnectionError("connection refused"),
            ]
        )
        monkeypatch.setattr("vastai.cli.commands.machines.requests.get", get)

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        endpoint = result["diagnostics"]["progress_endpoint"]
        assert result["failure_code"] == "progress_endpoint_lost"
        assert endpoint["first_connection_established"] is True
        assert endpoint["last_error_type"] == "ConnectionError"
        assert endpoint["attempt_count"] >= 7
        assert result["diagnostics"]["runtime_failure"]["progress_endpoint"] == endpoint
        assert destroy.call_count >= 1

    def test_progress_endpoint_http_non_200_records_status_code(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer()
        running_instance = {
            "id": 123,
            "actual_status": "running",
            "intended_status": "running",
            "public_ipaddr": "127.0.0.1",
            "ports": {"5000/tcp": [{"HostPort": "45000"}], "5001/udp": [{"HostPort": "45001"}]},
            "status_msg": "",
        }
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.create_instance",
            Mock(return_value={"new_contract": 123}),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.show_instance",
            Mock(return_value=running_instance),
        )
        destroy = Mock(return_value={"success": True})
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.destroy_instance", destroy)
        monkeypatch.setattr("vastai.cli.commands.machines.time.sleep", lambda *_: None)
        monkeypatch.setattr(
            "vastai.cli.commands.machines.requests.get",
            Mock(return_value=SimpleNamespace(status_code=500, text="server error")),
        )

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        endpoint = result["diagnostics"]["progress_endpoint"]
        assert result["failure_code"] == "progress_endpoint_unreachable"
        assert endpoint["last_status_code"] == 500
        assert endpoint["last_error_type"] == "HTTPStatus"
        assert endpoint["last_error"] == "HTTP 500 from progress endpoint"
        assert result["diagnostics"]["runtime_failure"]["progress_endpoint"] == endpoint
        assert destroy.call_count >= 1

    def test_progress_endpoint_empty_200_records_empty_timeout(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer()
        running_instance = {
            "id": 123,
            "actual_status": "running",
            "intended_status": "running",
            "public_ipaddr": "127.0.0.1",
            "ports": {"5000/tcp": [{"HostPort": "45000"}], "5001/udp": [{"HostPort": "45001"}]},
            "status_msg": "",
        }
        monkeypatch.setattr(
            "vastai.cli.commands.machines.offers_api.search_offers",
            Mock(return_value=[offer]),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.create_instance",
            Mock(return_value={"new_contract": 123}),
        )
        monkeypatch.setattr(
            "vastai.cli.commands.machines.instances_api.show_instance",
            Mock(return_value=running_instance),
        )
        destroy = Mock(return_value={"success": True})
        monkeypatch.setattr("vastai.cli.commands.machines.instances_api.destroy_instance", destroy)
        monkeypatch.setattr("vastai.cli.commands.machines.time.sleep", lambda *_: None)
        monkeypatch.setattr(
            "vastai.cli.commands.machines.requests.get",
            Mock(return_value=SimpleNamespace(status_code=200, text="")),
        )

        args = parse_argv(["self-test", "machine", "42", "--raw"])
        result = args.func(args)

        endpoint = result["diagnostics"]["progress_endpoint"]
        assert result["failure_code"] == "progress_empty_timeout"
        assert endpoint["first_connection_established"] is True
        assert endpoint["last_status_code"] == 200
        assert endpoint["last_error_type"] is None
        assert result["diagnostics"]["runtime_failure"]["progress_endpoint"] == endpoint
        assert destroy.call_count >= 1
