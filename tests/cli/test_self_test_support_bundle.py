"""Tests for self-test diagnostic support bundles."""

import json
import tarfile
from unittest.mock import Mock

import pytest

from vastai.cli.self_test.support_bundle import create_support_bundle


def test_support_bundle_contains_redacted_result_and_cli_output(tmp_path):
    bundle = create_support_bundle(
        machine_id="42",
        output_dir=str(tmp_path),
        result={
            "machine_id": "42",
            "error": "request failed: https://console.vast.ai/?api_key=secret",
            "diagnostics": {"jupyter_token": "secret-token"},
        },
        cli_output=["Starting self-test", "token=supersecret"],
        run_started_at="20260602T100000Z",
        command=["vastai", "--api-key", "secret", "self-test", "machine", "42"],
        secrets=["secret", "supersecret"],
        include_host_logs=False,
    )

    with tarfile.open(bundle["path"], "r:gz") as tar:
        names = set(tar.getnames())
        result_json = tar.extractfile("self-test-result.json").read().decode()
        output_log = tar.extractfile("self-test-output.log").read().decode()
        manifest = json.loads(tar.extractfile("manifest.json").read().decode())

    assert {"manifest.json", "self-test-result.json", "self-test-output.log", "collection-errors.json"} <= names
    assert "secret" not in result_json
    assert "secret" not in output_log
    assert "REDACTED" in result_json
    assert "REDACTED" in output_log
    assert manifest["machine_id"] == "42"
    assert manifest["run_started_at_utc"] == "20260602T100000Z"
    assert manifest["includes_local_host_artifacts"] is False


def test_support_bundle_sanitizes_archive_names(tmp_path):
    bundle = create_support_bundle(
        machine_id="42",
        output_dir=str(tmp_path),
        extra_files={"../../evil.txt": "payload"},
        include_local_host_artifacts=False,
    )

    with tarfile.open(bundle["path"], "r:gz") as tar:
        names = set(tar.getnames())

    assert "../../evil.txt" not in names
    assert all(".." not in name for name in names)
    assert "_/_/evil.txt" in names


def test_self_test_failure_creates_support_bundle(
    parse_argv, patch_get_client, monkeypatch, tmp_path, capsys
):
    from vastai.cli.commands import machines

    def fake_bundle(**kwargs):
        assert kwargs["machine_id"] == "42"
        assert kwargs["output_dir"] == str(tmp_path)
        assert kwargs["include_local_host_artifacts"] is False
        assert kwargs["extra_files"] == {}
        assert kwargs["extra_errors"] == []
        assert kwargs["result"]["failure_code"] == "preflight_requirements_failed"
        assert any("Preflight diagnostics for machine 42 failed:" in line for line in kwargs["cli_output"])
        return {
            "path": str(tmp_path / "vast_selftest_42_20260602T100000Z.tar.gz"),
            "created_at_utc": "20260602T100000Z",
            "size_bytes": 123,
            "files": ["manifest.json", "self-test-result.json", "self-test-output.log"],
            "collection_errors": [],
        }

    bad_offer = {
        "id": 777,
        "cuda_max_good": "11.7",
        "compute_cap": 750,
        "dlperf": 1,
        "reliability": 0.99,
        "direct_port_count": 1,
        "pcie_bw": 1.0,
        "gpu_total_ram": 6 * 1024,
        "inet_down": 10,
        "inet_up": 10,
        "gpu_ram": 6 * 1024,
        "cpu_ram": 1024,
        "cpu_cores": 1,
        "num_gpus": 1,
        "machine_id": 42,
    }
    monkeypatch.setenv("VAST_SELF_TEST_SUPPORT_BUNDLE", "1")
    monkeypatch.setattr(machines, "create_support_bundle", fake_bundle)
    monkeypatch.setattr(machines.offers_api, "search_offers", Mock(return_value=[bad_offer]))

    args = parse_argv(["self-test", "machine", "42", "--support-bundle-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as exc_info:
        args.func(args)

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert f"Support bundle: {tmp_path / 'vast_selftest_42_20260602T100000Z.tar.gz'}" in captured.out
    assert "self-test-result.json" not in captured.out
    assert "Next: inspect the support bundle or rerun with --log-level debug" in captured.out


def test_self_test_bundle_creation_error_preserves_original_failure(
    parse_argv, patch_get_client, monkeypatch, tmp_path, capsys
):
    from vastai.cli.commands import machines

    bad_offer = {
        "id": 777,
        "cuda_max_good": "11.7",
        "compute_cap": 750,
        "dlperf": 1,
        "reliability": 0.99,
        "direct_port_count": 1,
        "pcie_bw": 1.0,
        "gpu_total_ram": 6 * 1024,
        "inet_down": 10,
        "inet_up": 10,
        "gpu_ram": 6 * 1024,
        "cpu_ram": 1024,
        "cpu_cores": 1,
        "num_gpus": 1,
        "machine_id": 42,
    }

    monkeypatch.setenv("VAST_SELF_TEST_SUPPORT_BUNDLE", "1")
    monkeypatch.setattr(machines, "create_support_bundle", Mock(side_effect=OSError("disk full")))
    monkeypatch.setattr(machines.offers_api, "search_offers", Mock(return_value=[bad_offer]))

    args = parse_argv(["self-test", "machine", "42", "--support-bundle-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as exc_info:
        args.func(args)

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "WARNING: failed to create self-test diagnostic bundle: disk full" in captured.out
    assert "Reason: 8 preflight requirement check(s) failed." in captured.out


def test_self_test_runtime_failure_bundle_includes_instance_logs(
    parse_argv, patch_get_client, monkeypatch, tmp_path, capsys
):
    from vastai.cli.commands import machines

    created = {}
    destroyed = set()

    def fake_bundle(**kwargs):
        created.update(kwargs)
        return {
            "path": str(tmp_path / "vast_selftest_42_20260602T100000Z.tar.gz"),
            "created_at_utc": "20260602T100000Z",
            "size_bytes": 123,
            "files": [
                "manifest.json",
                "self-test-result.json",
                "self-test-output.log",
                "instance/container.log",
                "instance/daemon.log",
                "instance/show-instance.json",
            ],
            "collection_errors": [],
        }

    good_offer = {
        "id": 777,
        "cuda_max_good": "12.8",
        "compute_cap": 750,
        "dlperf": 1,
        "reliability": 0.99,
        "direct_port_count": 3,
        "pcie_bw": 16.0,
        "gpu_total_ram": 12 * 1024,
        "inet_down": 500,
        "inet_up": 500,
        "gpu_ram": 12 * 1024,
        "cpu_ram": 16 * 1024,
        "cpu_cores": 4,
        "num_gpus": 1,
        "machine_id": 42,
    }

    def fake_show_instance(client, id):
        assert client is patch_get_client
        if id in destroyed:
            return {"id": id, "actual_status": "destroyed", "intended_status": "destroyed"}
        return {
            "id": id,
            "actual_status": "created",
            "intended_status": "running",
            "status_msg": (
                "#6 [3/6] RUN export DEBIAN_FRONTEND=noninteractive; "
                "apt-get update || echo 'V220614a: error during apt-get update!';"
            ),
            "label": "vast-self-test-machine-42",
        }

    def fake_logs(client, instance_id, tail=None, filter=None, daemon_logs=False):
        assert client is patch_get_client
        assert instance_id == 123
        assert tail == machines.INSTANCE_LOG_TAIL_LINES
        assert filter is None
        if daemon_logs:
            return "\n".join(
                [
                    "#6 [3/6] RUN export DEBIAN_FRONTEND=noninteractive; apt-get update || echo 'V220614a: error during apt-get update!';",
                    "#6 2.268 Fetched 49.3 MB in 2s (26.6 MB/s)",
                    "#6 DONE 3.3s",
                    "Error response from daemon: failed to inject CDI devices: unresolvable CDI devices D.host/gpu=0, D.host/gpu=1: unknown",
                ]
            )
        return "container startup failure"

    def fake_destroy_instance(client, id):
        assert client is patch_get_client
        destroyed.add(id)
        return {"success": True}

    monkeypatch.setenv("VAST_SELF_TEST_SUPPORT_BUNDLE", "1")
    monkeypatch.setattr(machines, "create_support_bundle", fake_bundle)
    monkeypatch.setattr(machines.offers_api, "search_offers", Mock(return_value=[good_offer]))
    monkeypatch.setattr(machines.instances_api, "create_instance", Mock(return_value={"new_contract": 123}))
    monkeypatch.setattr(machines.instances_api, "show_instance", fake_show_instance)
    monkeypatch.setattr(machines.instances_api, "logs", fake_logs)
    monkeypatch.setattr(machines.instances_api, "destroy_instance", fake_destroy_instance)

    args = parse_argv([
        "self-test",
        "machine",
        "42",
        "--support-bundle-dir",
        str(tmp_path),
        "--log-level",
        "debug",
    ])
    with pytest.raises(SystemExit) as exc_info:
        args.func(args)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert 123 in destroyed
    assert created["include_local_host_artifacts"] is False
    assert created["result"]["failure_code"] == "daemon_startup_failed"
    assert created["result"]["failure"]["summary"] == "Docker/NVIDIA runtime failed before the self-test container could start."
    assert created["result"]["failure"]["startup_evidence"]["apt_update"]["status"] == "completed"
    assert created["extra_files"]["instance/container.log"] == "container startup failure"
    assert "failed to inject CDI devices" in created["extra_files"]["instance/daemon.log"]
    assert '"label": "vast-self-test-machine-42"' in created["extra_files"]["instance/show-instance.json"]
    assert created["extra_errors"] == []
    assert "Runtime failure diagnostics" in captured.out
    assert "  Result:" in captured.out
    assert "  What happened:" in captured.out
    assert "Vast startup wrapper apt-get update completed successfully." in captured.out
    assert "Docker/NVIDIA runtime failed to inject CDI GPU devices for GPUs 0, 1." in captured.out
    assert "  Where to read next:" in captured.out
    assert "instance/daemon.log in the diagnostic bundle" in captured.out
    assert "Reason: Docker/NVIDIA runtime failed before the self-test container could start." in captured.out


def test_dump_logs_command_creates_cli_visible_bundle(parse_argv, monkeypatch, tmp_path):
    from vastai.cli.commands import machines

    created = {}

    def fake_bundle(**kwargs):
        created.update(kwargs)
        return {
            "path": str(tmp_path / "vast_selftest_42_20260602T100000Z.tar.gz"),
            "created_at_utc": "20260602T100000Z",
            "size_bytes": 123,
            "files": ["manifest.json", "self-test-result.json", "self-test-output.log"],
            "collection_errors": [],
        }

    monkeypatch.setattr(machines, "create_support_bundle", fake_bundle)

    args = parse_argv(["dump-logs", "42", "--output-dir", str(tmp_path), "--raw"])
    result = args.func(args)

    assert result["path"].endswith("vast_selftest_42_20260602T100000Z.tar.gz")
    assert created["machine_id"] == "42"
    assert created["output_dir"] == str(tmp_path)
    assert created["include_local_host_artifacts"] is False
    assert created["extra_files"] == {}
    assert created["extra_errors"] == []
    assert created["result"]["stage"] == "manual_dump_logs"
    assert "No --instance-id provided" in "\n".join(created["cli_output"])


def test_dump_logs_bundle_creation_error_is_friendly(parse_argv, monkeypatch, tmp_path, capsys):
    from vastai.cli.commands import machines

    monkeypatch.setattr(machines, "create_support_bundle", Mock(side_effect=OSError("read-only directory")))

    args = parse_argv(["dump-logs", "42", "--output-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as exc_info:
        args.func(args)

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "WARNING: failed to create diagnostic bundle: read-only directory" in captured.out


def test_dump_logs_command_can_pull_instance_logs(
    parse_argv, patch_get_client, monkeypatch, tmp_path
):
    from vastai.cli.commands import machines

    created = {}

    def fake_bundle(**kwargs):
        created.update(kwargs)
        return {
            "path": str(tmp_path / "vast_selftest_42_20260602T100000Z.tar.gz"),
            "created_at_utc": "20260602T100000Z",
            "size_bytes": 123,
            "files": [
                "manifest.json",
                "instance/container.log",
                "instance/daemon.log",
                "instance/show-instance.json",
            ],
            "collection_errors": [],
        }

    def fake_show_instance(client, id):
        assert client is patch_get_client
        assert id == 123
        return {"id": 123, "actual_status": "running", "label": "vast-self-test-machine-42"}

    def fake_logs(client, instance_id, tail=None, filter=None, daemon_logs=False):
        assert client is patch_get_client
        assert instance_id == 123
        assert tail == machines.INSTANCE_LOG_TAIL_LINES
        assert filter is None
        return "daemon log" if daemon_logs else "container log"

    monkeypatch.setattr(machines, "create_support_bundle", fake_bundle)
    monkeypatch.setattr(machines.instances_api, "show_instance", fake_show_instance)
    monkeypatch.setattr(machines.instances_api, "logs", fake_logs)

    args = parse_argv([
        "dump-logs",
        "42",
        "--instance-id",
        "123",
        "--output-dir",
        str(tmp_path),
        "--raw",
    ])
    result = args.func(args)

    assert result["path"].endswith("vast_selftest_42_20260602T100000Z.tar.gz")
    assert created["machine_id"] == "42"
    assert created["include_local_host_artifacts"] is False
    assert created["result"]["instance_id"] == 123
    assert created["extra_files"]["instance/container.log"] == "container log"
    assert created["extra_files"]["instance/daemon.log"] == "daemon log"
    assert '"actual_status": "running"' in created["extra_files"]["instance/show-instance.json"]
    assert created["extra_errors"] == []
