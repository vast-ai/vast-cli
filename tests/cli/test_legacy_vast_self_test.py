from argparse import Namespace
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import vast

from vastai.cli.commands import machines
from vastai.cli.self_test.machine_diagnostics import (
    SYSTEM_RAM_REQUIREMENT_CAP_MIB as PACKAGED_SYSTEM_RAM_REQUIREMENT_CAP_MIB,
)
from vastai.cli.self_test.runtime_diagnostics import (
    CUDA_ERROR_CONTAINED,
    status_message_is_error,
)


CUDA_ERROR_CONTAINED_MARKER = (
    "ERROR 2: Contained CUDA device fault in all-GPU ResNet18 "
    "(possible peer-memory/NVLink access or hardware fault); not CUDA "
    "out-of-memory/VRAM exhaustion. SELF_TEST_FAILURE[cuda_error_contained]: "
    "Cause: AcceleratorError: CUDA error: Invalid access of peer GPU memory over "
    "nvlink or a hardware error cudaErrorContained. Restart the failed "
    "process/container; then check GPU topology and all-pairs CUDA P2P, "
    "NVLink/NVSwitch, Fabric Manager/NVLSM, and Xid/ECC/driver logs."
)
_MISSING = object()


def _args():
    return Namespace(
        debugging=False,
        explain=False,
        raw=True,
        retry=3,
        url="https://example.invalid",
    )


def _b300_offer(**overrides):
    offer = {
        "cpu_cores": 192,
        "cpu_ram": 2_063_831,
        "cuda_max_good": 13.2,
        "direct_port_count": 16_385,
        "dlperf": 665.8,
        "gpu_ram": 275_040,
        "gpu_total_ram": 2_200_320,
        "inet_down": 3_417.3,
        "inet_up": 6_399.6,
        "num_gpus": 8,
        "pcie_bw": 53.0,
        "reliability": 0.984,
    }
    offer.update(overrides)
    return offer


def _check(monkeypatch, offer):
    monkeypatch.setattr(vast, "search__offers", lambda _args: [offer])
    return vast.check_requirements("144396", "test-api-key", _args())


def test_legacy_system_ram_cap_matches_packaged_cli():
    assert (
        vast.SYSTEM_RAM_REQUIREMENT_CAP_MIB
        == PACKAGED_SYSTEM_RAM_REQUIREMENT_CAP_MIB
        == 2_000_000
    )


def test_legacy_self_test_contract_matches_packaged_cli(monkeypatch):
    monkeypatch.delenv("VAST_SELF_TEST_LABEL", raising=False)
    monkeypatch.delenv("VAST_SELF_TEST_OFFER_ID", raising=False)
    assert vast.SELF_TEST_MIN_CLI_VERSION == machines.SELF_TEST_MIN_CLI_VERSION
    assert (
        vast.SELF_TEST_CLI_CONTRACT_VERSION
        == machines.SELF_TEST_CLI_CONTRACT_VERSION
        == "1.2.3"
    )
    assert vast.SELF_TEST_IMAGE_TAG_PREFIX == machines.SELF_TEST_IMAGE_TAG_PREFIX
    assert (
        vast.SELF_TEST_INSTANCE_LABEL_MAX_LENGTH
        == machines.SELF_TEST_INSTANCE_LABEL_MAX_LENGTH
        == 64
    )
    assert (
        vast.resolve_self_test_instance_label("42")
        == machines.resolve_self_test_instance_label("42")
        == "vast-self-test-machine-42"
    )
    max_length_label = "vast-self-test-" + ("a" * 49)
    monkeypatch.setenv("VAST_SELF_TEST_LABEL", max_length_label)
    assert len(max_length_label) == 64
    assert (
        vast.resolve_self_test_instance_label("42")
        == machines.resolve_self_test_instance_label("42")
        == max_length_label
    )
    assert vast.SELF_TEST_CUDA_ERROR_CONTAINED == CUDA_ERROR_CONTAINED
    assert (
        vast.SELF_TEST_OFFER_ID_OVERRIDE_ENV
        == machines.SELF_TEST_OFFER_ID_OVERRIDE_ENV
        == "VAST_SELF_TEST_OFFER_ID"
    )
    assert vast.resolve_self_test_offer_id() is None
    assert machines.resolve_self_test_offer_id() is None


def test_legacy_b300_mapping_uses_the_versioned_contract_image():
    image, reason = vast.self_test_cuda_map_to_image(13.2, compute_cap=1030)

    assert image == "vastai/test:self-test-cli-1.2.3-cuda-13.0"
    assert "selected newest image <= host CUDA (13.0)" in reason


def test_legacy_launch_passes_the_image_contract():
    env = vast.self_test_launch_env("1.4.4")

    assert "-e VAST_SELF_TEST_CLI_VERSION=1.4.4" in env
    assert "-e VAST_SELF_TEST_CLI_CONTRACT_VERSION=1.2.3" in env
    assert "-p 5001:5001/udp" in env
    assert "-p 1234:1234" not in env


def test_legacy_gpu_name_lookup_is_safe_when_offline(monkeypatch, tmp_path):
    from requests.exceptions import ConnectTimeout

    monkeypatch.setattr(vast, "CACHE_FILE", str(tmp_path / "missing-cache.json"))
    monkeypatch.setattr(
        vast.requests,
        "get",
        Mock(side_effect=ConnectTimeout("offline")),
    )

    assert vast._get_gpu_names() is None


def test_legacy_preflight_caps_system_ram_requirement_for_b300(monkeypatch):
    passed, reasons = _check(monkeypatch, _b300_offer())
    assert passed is True
    assert reasons == []

    passed, reasons = _check(monkeypatch, _b300_offer(cpu_ram=1_900_000))
    assert passed is False
    assert "System RAM is less than total VRAM." in reasons


def test_legacy_preflight_keeps_95_percent_requirement_below_cap(monkeypatch):
    passed, reasons = _check(
        monkeypatch,
        _b300_offer(gpu_total_ram=1_800_000, cpu_ram=1_710_000),
    )
    assert passed is True
    assert reasons == []

    passed, reasons = _check(
        monkeypatch,
        _b300_offer(gpu_total_ram=1_800_000, cpu_ram=1_709_999),
    )
    assert passed is False
    assert "System RAM is less than total VRAM." in reasons


def test_legacy_preflight_direct_port_minimum_is_four(monkeypatch):
    passed, reasons = _check(monkeypatch, _b300_offer(direct_port_count=4))
    assert passed is True
    assert "Direct port count < 4" not in reasons

    passed, reasons = _check(monkeypatch, _b300_offer(direct_port_count=3))
    assert passed is False
    assert "Direct port count < 4" in reasons


def test_legacy_startup_status_ignores_liberror_build_progress(monkeypatch):
    loading = {
        "actual_status": "loading",
        "intended_status": "running",
        "status_msg": (
            "#7 4.226 Get:70 http://archive.ubuntu.com/ubuntu noble/main "
            "amd64 liberror-perl all 0.17029-2 [25.6 kB]"
        ),
    }
    running = {
        "actual_status": "running",
        "intended_status": "running",
        "status_msg": "",
    }
    show = Mock(side_effect=[loading, running])
    destroy = Mock()
    monkeypatch.setattr(vast, "show__instance", show)
    monkeypatch.setattr(vast, "destroy_instance_silent", destroy)
    monkeypatch.setattr(vast.time, "sleep", lambda *_: None)

    instance, reason = vast.wait_for_instance(
        123,
        "test-api-key",
        _args(),
        Namespace(),
        timeout=1,
        interval=0,
    )

    assert instance == running
    assert reason is None
    destroy.assert_not_called()


def test_legacy_running_state_ignores_stale_error_text(monkeypatch):
    running = {
        "actual_status": "running",
        "intended_status": "running",
        "status_msg": "Error response from daemon: stale build status",
    }
    destroy = Mock()
    monkeypatch.setattr(vast, "show__instance", Mock(return_value=running))
    monkeypatch.setattr(vast, "destroy_instance_silent", destroy)

    instance, reason = vast.wait_for_instance(
        123,
        "test-api-key",
        _args(),
        Namespace(),
        timeout=1,
        interval=0,
    )

    assert instance == running
    assert reason is None
    destroy.assert_not_called()


def test_legacy_status_error_detection_matches_packaged_cli():
    messages = [
        "#7 4.226 Get:70 amd64 liberror-perl all 0.17029-2 [25.6 kB]",
        "#8 1.250 Collecting unauthorized",
        "#8 2.500 Successfully installed unauthorized-1.3.0",
        "Generating documentation for unauthorized clients",
        "Error-prone package metadata generated successfully",
        (
            "#7 5.2 W: Failed to fetch http://archive.ubuntu.com/index\n"
            "#7 5.2 W: Some index files failed to download. They have been "
            "ignored, or old ones used instead."
        ),
        "Failed to fetch package metadata; using cached index",
        "rpc error: code = Unknown desc = failed to pull and unpack image",
        "manifest unknown: manifest unknown",
        "no matching manifest for linux/amd64 in the manifest list entries",
        "denied: requested access to the resource is denied",
        "docker: Error response from daemon: could not select device driver",
        "invalid reference format",
    ]

    for message in messages:
        assert (
            vast.self_test_status_message_is_error(message)
            is status_message_is_error(message)
        )


def test_legacy_terminal_status_fails_with_normal_build_text(monkeypatch):
    terminal = {
        "actual_status": "error",
        "intended_status": "running",
        "status_msg": (
            "#7 4.226 Get:70 http://archive.ubuntu.com/ubuntu noble/main "
            "amd64 liberror-perl all 0.17029-2 [25.6 kB]"
        ),
    }
    destroy = Mock()
    monkeypatch.setattr(vast, "show__instance", Mock(return_value=terminal))
    monkeypatch.setattr(vast, "instance_exist", Mock(return_value=True))
    monkeypatch.setattr(vast, "destroy_instance_silent", destroy)

    instance, reason = vast.wait_for_instance(
        123,
        "test-api-key",
        _args(),
        Namespace(),
        timeout=1,
        interval=0,
    )

    assert instance is False
    assert "actual=error" in reason
    destroy.assert_called_once()


def test_legacy_runtime_classifier_handles_contained_marker_and_resnet_precedence():
    diagnostic = vast.self_test_classify_runtime_failure(
        CUDA_ERROR_CONTAINED_MARKER,
        stage="system_requirements",
    )

    assert diagnostic["code"] == "cuda_error_contained"
    assert diagnostic["stage"] == "resnet"
    assert diagnostic["underlying_error"] == CUDA_ERROR_CONTAINED_MARKER
    assert "not CUDA out-of-memory or VRAM exhaustion" in diagnostic["summary"]
    assert "tenant VRAM" in diagnostic["remediation"]
    steps = " ".join(diagnostic["suggested_steps"])
    assert "all-pairs P2P" in steps
    assert "Fabric Manager/NVLSM" in steps
    assert "Xid/ECC" in steps

    generic = vast.self_test_classify_runtime_failure(
        "ERROR 2: ResNet failed after an otherwise unclassified hardware error",
        stage="resnet",
    )
    assert generic["code"] == "resnet_failed"
    assert generic["stage"] == "resnet"


def _patch_legacy_contained_self_test(
    monkeypatch, tmp_path, *, raw, test_image=_MISSING
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VAST_SELF_TEST_IMAGE", raising=False)
    monkeypatch.delenv("VAST_SELF_TEST_LABEL", raising=False)
    monkeypatch.delenv("VAST_SELF_TEST_OFFER_ID", raising=False)
    monkeypatch.setattr(vast, "check_requirements", lambda *_: (True, []))
    monkeypatch.setattr(
        vast,
        "search__offers",
        lambda *_: [
            {
                "id": 777,
                "cuda_max_good": 12.8,
                "compute_cap": 800,
                "dlperf": 1,
            }
        ],
    )
    create_response = vast.requests.Response()
    create_response.status_code = 200
    create_response._content = b'{"new_contract": 123}'
    created_images = []
    created_labels = []
    created_offer_ids = []

    def create_instance(create_args):
        created_images.append(create_args.image)
        created_labels.append(create_args.label)
        created_offer_ids.append(create_args.id)
        return create_response

    monkeypatch.setattr(vast, "create__instance", create_instance)

    instance = {
        "id": 123,
        "actual_status": "running",
        "intended_status": "running",
        "public_ipaddr": "127.0.0.1",
        "ports": {"5000/tcp": [{"HostPort": "45000"}]},
    }
    monkeypatch.setattr(vast, "wait_for_instance", lambda *_: (instance, None))
    destroyed = set()

    def show_instance(_args):
        return None if 123 in destroyed else instance

    def destroy_instance(instance_id, _args):
        destroyed.add(int(instance_id))
        return {"success": True}

    monkeypatch.setattr(vast, "show__instance", show_instance)
    monkeypatch.setattr(vast, "destroy_instance_silent", destroy_instance)
    monkeypatch.setattr(
        vast.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(
            status_code=200,
            text="\n".join(
                (
                    "Starting tests...",
                    "Running ResNet18 test on all GPUs...",
                    CUDA_ERROR_CONTAINED_MARKER,
                )
            ),
        ),
    )
    monkeypatch.setattr(vast.time, "sleep", lambda *_: None)

    args = Namespace(
        machine_id="42",
        debugging=False,
        explain=False,
        raw=raw,
        retry=3,
        url="https://example.invalid",
        ignore_requirements=False,
        api_key="test-api-key",
        curl=False,
    )
    if test_image is not _MISSING:
        args.test_image = test_image
    return args, destroyed, created_images, created_labels, created_offer_ids


def test_legacy_contained_failure_renders_once_exits_one_and_cleans_up(
    monkeypatch, tmp_path, capsys
):
    args, destroyed, _created_images, _created_labels, _created_offer_ids = _patch_legacy_contained_self_test(
        monkeypatch,
        tmp_path,
        raw=False,
    )

    with pytest.raises(SystemExit) as exc_info:
        vast.self_test__machine(args)

    output = capsys.readouterr().out
    assert exc_info.value.code == 1
    assert output.count(CUDA_ERROR_CONTAINED_MARKER) == 1
    assert "- code: cuda_error_contained" in output
    assert "not CUDA out-of-memory or VRAM exhaustion" in output
    assert "tenant VRAM" in output
    assert "all-pairs P2P" in output
    assert "Fabric Manager/NVLSM" in output
    assert "Xid/ECC" in output
    assert "Test failed with error:" not in output
    assert destroyed == {123}


def test_legacy_contained_failure_raw_preserves_detail_and_exit_contract(
    monkeypatch, tmp_path, capsys
):
    args, destroyed, _created_images, _created_labels, _created_offer_ids = _patch_legacy_contained_self_test(
        monkeypatch,
        tmp_path,
        raw=True,
    )

    with pytest.raises(SystemExit) as exc_info:
        vast.self_test__machine(args)

    result = json.loads(capsys.readouterr().out)
    assert exc_info.value.code == 0
    assert result["success"] is False
    assert result["reason"] == CUDA_ERROR_CONTAINED_MARKER
    assert result["failure_code"] == "cuda_error_contained"
    assert result["stage"] == "resnet"
    assert result["failure"]["underlying_error"] == CUDA_ERROR_CONTAINED_MARKER
    assert destroyed == {123}


def test_legacy_custom_test_image_override_reaches_instance_launch(
    monkeypatch, tmp_path, capsys
):
    candidate = "vastai/test@sha256:" + ("a" * 64)
    args, destroyed, created_images, created_labels, _created_offer_ids = _patch_legacy_contained_self_test(
        monkeypatch,
        tmp_path,
        raw=True,
        test_image=candidate,
    )
    monkeypatch.setenv(
        "VAST_SELF_TEST_IMAGE",
        "vastai/test@sha256:" + ("b" * 64),
    )
    monkeypatch.setattr(
        vast,
        "self_test_cuda_map_to_image",
        lambda *_: (_ for _ in ()).throw(AssertionError("mapping should be bypassed")),
    )

    with pytest.raises(SystemExit) as exc_info:
        vast.self_test__machine(args)

    result = json.loads(capsys.readouterr().out)
    assert exc_info.value.code == 0
    assert result["failure_code"] == "cuda_error_contained"
    assert created_images == [candidate]
    assert created_labels == ["vast-self-test-machine-42"]
    assert destroyed == {123}


def test_legacy_parser_accepts_custom_test_image_option():
    candidate = "vastai/test@sha256:" + ("c" * 64)

    args = vast.parser.parse_args(
        ["self-test", "machine", "42", "--test-image", candidate, "--raw"]
    )

    assert args.test_image == candidate
    assert args.func is vast.self_test__machine


def test_legacy_environment_test_image_override_supports_old_namespace(
    monkeypatch, tmp_path, capsys
):
    candidate = "vastai/test@sha256:" + ("d" * 64)
    args, destroyed, created_images, created_labels, _created_offer_ids = _patch_legacy_contained_self_test(
        monkeypatch,
        tmp_path,
        raw=True,
    )
    assert not hasattr(args, "test_image")
    monkeypatch.setenv("VAST_SELF_TEST_IMAGE", candidate)

    with pytest.raises(SystemExit) as exc_info:
        vast.self_test__machine(args)

    result = json.loads(capsys.readouterr().out)
    assert exc_info.value.code == 0
    assert result["failure_code"] == "cuda_error_contained"
    assert created_images == [candidate]
    assert created_labels == ["vast-self-test-machine-42"]
    assert destroyed == {123}


def test_legacy_environment_self_test_label_reaches_launch_and_exact_id_cleanup(
    monkeypatch, tmp_path, capsys
):
    label = "vast-self-test-pr458.41526-a1_b2"
    args, destroyed, _created_images, created_labels, _created_offer_ids = (
        _patch_legacy_contained_self_test(
            monkeypatch,
            tmp_path,
            raw=True,
        )
    )
    monkeypatch.setenv("VAST_SELF_TEST_LABEL", label)
    original_create = vast.create__instance
    created_bid_prices = []

    def create_with_recorded_price(create_args):
        created_bid_prices.append(create_args.bid_price)
        return original_create(create_args)

    monkeypatch.setattr(vast, "create__instance", create_with_recorded_price)

    with pytest.raises(SystemExit) as exc_info:
        vast.self_test__machine(args)

    result = json.loads(capsys.readouterr().out)
    assert exc_info.value.code == 0
    assert result["failure_code"] == "cuda_error_contained"
    assert created_labels == [label]
    assert created_bid_prices == [None]
    assert destroyed == {123}


def test_legacy_default_offer_selection_still_prefers_highest_dlperf(
    monkeypatch, tmp_path, capsys
):
    args, destroyed, _images, _labels, created_offer_ids = (
        _patch_legacy_contained_self_test(monkeypatch, tmp_path, raw=True)
    )
    monkeypatch.delenv("VAST_SELF_TEST_OFFER_ID", raising=False)
    search = Mock(
        return_value=[
            {"id": 1001, "cuda_max_good": 12.8, "compute_cap": 800, "dlperf": 10},
            {"id": 2002, "cuda_max_good": 12.8, "compute_cap": 800, "dlperf": 50},
        ]
    )
    monkeypatch.setattr(vast, "search__offers", search)

    with pytest.raises(SystemExit) as exc_info:
        vast.self_test__machine(args)

    result = json.loads(capsys.readouterr().out)
    assert exc_info.value.code == 0
    assert result["failure_code"] == "cuda_error_contained"
    assert created_offer_ids == [2002]
    assert search.call_count == 1
    assert destroyed == {123}


def test_legacy_valid_environment_offer_pin_overrides_dlperf_selection(
    monkeypatch, tmp_path, capsys
):
    args, destroyed, _images, _labels, created_offer_ids = (
        _patch_legacy_contained_self_test(monkeypatch, tmp_path, raw=True)
    )
    search = Mock(
        return_value=[
            {"id": "1001", "cuda_max_good": 12.8, "compute_cap": 800, "dlperf": 10},
            {"id": 2002, "cuda_max_good": 12.8, "compute_cap": 800, "dlperf": 50},
        ]
    )
    monkeypatch.setenv("VAST_SELF_TEST_OFFER_ID", "001001")
    monkeypatch.setattr(vast, "search__offers", search)

    with pytest.raises(SystemExit) as exc_info:
        vast.self_test__machine(args)

    result = json.loads(capsys.readouterr().out)
    assert exc_info.value.code == 0
    assert result["failure_code"] == "cuda_error_contained"
    assert created_offer_ids == [1001]
    assert search.call_count == 1
    search_args = search.call_args.args[0]
    assert search_args.query == [
        "machine_id=42",
        "verified=any",
        "rentable=true",
        "rented=any",
    ]
    assert search_args.type == "on-demand"
    assert search_args.storage == 5.0
    assert destroyed == {123}


@pytest.mark.parametrize("invalid_offer_id", ["", "0", "-1", "+1", "1.5", "abc", " 1"])
def test_legacy_invalid_environment_offer_pin_is_rejected_before_search(
    monkeypatch, tmp_path, capsys, invalid_offer_id
):
    args, destroyed, _images, _labels, _created_offer_ids = (
        _patch_legacy_contained_self_test(monkeypatch, tmp_path, raw=True)
    )
    search = Mock()
    create = Mock()
    monkeypatch.setenv("VAST_SELF_TEST_OFFER_ID", invalid_offer_id)
    monkeypatch.setattr(vast, "search__offers", search)
    monkeypatch.setattr(vast, "create__instance", create)

    with pytest.raises(SystemExit) as exc_info:
        vast.self_test__machine(args)

    result = json.loads(capsys.readouterr().out)
    assert exc_info.value.code == 0
    assert result["success"] is False
    assert result["stage"] == "validate_offer_id"
    assert "VAST_SELF_TEST_OFFER_ID" in result["reason"]
    search.assert_not_called()
    create.assert_not_called()
    assert destroyed == set()


def test_legacy_absent_environment_offer_pin_fails_before_create(
    monkeypatch, tmp_path, capsys
):
    args, destroyed, _images, _labels, _created_offer_ids = (
        _patch_legacy_contained_self_test(monkeypatch, tmp_path, raw=True)
    )
    search = Mock(
        return_value=[
            {"id": 1001, "cuda_max_good": 12.8, "compute_cap": 800, "dlperf": 10},
            {"id": 2002, "cuda_max_good": 12.8, "compute_cap": 800, "dlperf": 50},
        ]
    )
    create = Mock()
    monkeypatch.setenv("VAST_SELF_TEST_OFFER_ID", "3003")
    monkeypatch.setattr(vast, "search__offers", search)
    monkeypatch.setattr(vast, "create__instance", create)

    with pytest.raises(SystemExit) as exc_info:
        vast.self_test__machine(args)

    result = json.loads(capsys.readouterr().out)
    assert exc_info.value.code == 0
    assert result["success"] is False
    assert result["stage"] == "select_offer"
    assert result["failure_code"] == "pinned_offer_not_available"
    assert "Offer 3003" in result["reason"]
    assert search.call_count == 1
    create.assert_not_called()
    assert destroyed == set()


def test_legacy_invalid_environment_offer_pin_non_raw_exits_one(
    monkeypatch, tmp_path, capsys
):
    args, destroyed, _images, _labels, _created_offer_ids = (
        _patch_legacy_contained_self_test(monkeypatch, tmp_path, raw=False)
    )
    search = Mock()
    monkeypatch.setenv("VAST_SELF_TEST_OFFER_ID", "not-an-id")
    monkeypatch.setattr(vast, "search__offers", search)

    with pytest.raises(SystemExit) as exc_info:
        vast.self_test__machine(args)

    assert exc_info.value.code == 1
    assert "VAST_SELF_TEST_OFFER_ID must be a positive integer" in capsys.readouterr().out
    search.assert_not_called()
    assert destroyed == set()


@pytest.mark.parametrize(
    "invalid_label",
    [
        "",
        "self-test-missing-prefix",
        "vast-self-test-has space",
        "vast-self-test-has/slash",
        "vast-self-test-non-ascii-é",
        "vast-self-test-" + ("a" * 50),
    ],
)
def test_legacy_invalid_environment_self_test_label_is_rejected_before_search(
    monkeypatch, tmp_path, capsys, invalid_label
):
    args, destroyed, _created_images, _created_labels, _created_offer_ids = (
        _patch_legacy_contained_self_test(
            monkeypatch,
            tmp_path,
            raw=True,
        )
    )
    search = Mock(return_value=[])
    create = Mock()
    monkeypatch.setenv("VAST_SELF_TEST_LABEL", invalid_label)
    monkeypatch.setattr(vast, "search__offers", search)
    monkeypatch.setattr(vast, "create__instance", create)

    with pytest.raises(SystemExit) as exc_info:
        vast.self_test__machine(args)

    result = json.loads(capsys.readouterr().out)
    assert exc_info.value.code == 0
    assert result["success"] is False
    assert result["stage"] == "validate_label"
    assert "VAST_SELF_TEST_LABEL" in result["reason"]
    search.assert_not_called()
    create.assert_not_called()
    assert destroyed == set()
