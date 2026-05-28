"""Integration tests for machine CLI commands with mocked HTTP."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests


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
            "ports": {"5000/tcp": [{"HostPort": "5000"}]},
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
        assert "Test passed." in out

    def test_ignore_requirements_warning_in_raw_summary(self, parse_argv, monkeypatch, capsys):
        from vastai.cli.commands import machines

        monkeypatch.setattr(machines.offers_api, "search_offers", Mock(return_value=[]))

        args = parse_argv(["--raw", "self-test", "machine", "0", "--ignore-requirements"])
        with pytest.raises(SystemExit) as exc_info:
            args.func(args)

        assert exc_info.value.code == 0
        raw = json.loads(capsys.readouterr().out)
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
        assert search.call_count == 2

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
        bad_offer = _self_test_offer(gpu_ram=6 * 1024)
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

    def test_default_cuda_mapping_still_selects_official_image(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer(cuda_max_good=12.8, compute_cap=890)
        result, create = _run_self_test_until_create(parse_argv, monkeypatch, offer)

        assert result["diagnostics"]["image"]["override"] is False
        assert create.call_args.kwargs["image"] == "vastai/test:self-test-cuda-12.8"
        assert create.call_args.kwargs["runtype"] == "ssh_direc ssh_proxy"

    def test_cuda_mapping_selects_cuda_133_exact_match(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer(cuda_max_good=13.3, compute_cap=890)
        result, create = _run_self_test_until_create(parse_argv, monkeypatch, offer)

        assert result["diagnostics"]["image"]["override"] is False
        assert create.call_args.kwargs["image"] == "vastai/test:self-test-cuda-13.3"
        assert "exact match" in result["diagnostics"]["image"]["reason"]

    def test_cuda_mapping_steps_down_to_newest_compatible_image(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer(cuda_max_good=13.2, compute_cap=890)
        result, create = _run_self_test_until_create(parse_argv, monkeypatch, offer)

        assert result["diagnostics"]["image"]["override"] is False
        assert create.call_args.kwargs["image"] == "vastai/test:self-test-cuda-13.0"
        assert "selected newest image <= host CUDA (13.0)" in result["diagnostics"]["image"]["reason"]

    def test_cuda_mapping_uses_cuda_133_for_newer_cuda_hosts(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer(cuda_max_good=13.4, compute_cap=890)
        result, create = _run_self_test_until_create(parse_argv, monkeypatch, offer)

        assert result["diagnostics"]["image"]["override"] is False
        assert create.call_args.kwargs["image"] == "vastai/test:self-test-cuda-13.3"
        assert "selected newest image <= host CUDA (13.3)" in result["diagnostics"]["image"]["reason"]

    def test_cuda_mapping_still_clamps_volta_to_cuda_128(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer(cuda_max_good=13.3, compute_cap=700)
        result, create = _run_self_test_until_create(parse_argv, monkeypatch, offer)

        assert result["diagnostics"]["image"]["override"] is False
        assert create.call_args.kwargs["image"] == "vastai/test:self-test-cuda-12.8"
        assert "clamped to 12.8" in result["diagnostics"]["image"]["reason"]

    def test_startup_status_msg_is_classified_in_raw_output(
        self, parse_argv, patch_get_client, monkeypatch
    ):
        offer = _self_test_offer()
        status_msg = "Error response from daemon: manifest for vastai/test:self-test-cuda-99 not found"
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
        assert "- remediation: Inspect docker daemon, OCI runtime, and container startup logs." in captured.out
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
