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


def test_self_test_failure_creates_support_bundle(
    parse_argv, patch_get_client, monkeypatch, tmp_path, capsys
):
    from vastai.cli.commands import machines

    def fake_bundle(**kwargs):
        assert kwargs["machine_id"] == "42"
        assert kwargs["output_dir"] == str(tmp_path)
        assert kwargs["include_host_logs"] is True
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
    assert "Self-test diagnostic bundle saved to:" in captured.out
    assert "self-test-result.json" in captured.out
    assert "Review this tarball before sharing it with support." in captured.out


def test_dump_logs_command_creates_same_bundle(parse_argv, monkeypatch, tmp_path):
    from vastai.cli.commands import machines

    created = {}

    def fake_bundle(**kwargs):
        created.update(kwargs)
        return {
            "path": str(tmp_path / "vast_selftest_42_20260602T100000Z.tar.gz"),
            "created_at_utc": "20260602T100000Z",
            "size_bytes": 123,
            "files": ["manifest.json", "host/docker-info.txt"],
            "collection_errors": [],
        }

    monkeypatch.setattr(machines, "create_support_bundle", fake_bundle)

    args = parse_argv(["dump-logs", "42", "--output-dir", str(tmp_path), "--raw"])
    result = args.func(args)

    assert result["path"].endswith("vast_selftest_42_20260602T100000Z.tar.gz")
    assert created["machine_id"] == "42"
    assert created["output_dir"] == str(tmp_path)
    assert created["include_host_logs"] is True
    assert created["result"]["stage"] == "manual_dump_logs"
