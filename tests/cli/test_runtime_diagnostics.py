import pytest

from vastai.cli.self_test import runtime_diagnostics as diag


def test_failure_catalog_contains_stable_runtime_codes():
    catalog = diag.failure_catalog()

    assert set(diag.RUNTIME_FAILURE_CODES) == set(catalog)
    assert catalog[diag.DOCKER_PULL_FAILED]["code"] == diag.DOCKER_PULL_FAILED
    assert catalog[diag.CLEANUP_FAILED]["suggested_steps"]


def test_make_failure_shapes_raw_output_dict():
    endpoint = {"url": "https://1.2.3.4:41001/progress"}
    result = diag.make_failure(
        diag.INSTANCE_STATUS_ERROR,
        stage=diag.STAGE_STARTUP,
        error="Error: status failed",
        underlying_error="backend status_msg",
        progress_endpoint=endpoint,
    )

    assert result["code"] == diag.INSTANCE_STATUS_ERROR
    assert result["stage"] == diag.STAGE_STARTUP
    assert result["summary"]
    assert result["remediation"]
    assert result["suggested_steps"]
    assert result["error"] == "Error: status failed"
    assert result["underlying_error"] == "backend status_msg"
    assert result["progress_endpoint"] == endpoint


def test_make_failure_rejects_unknown_code():
    with pytest.raises(ValueError, match="Unknown runtime failure code"):
        diag.make_failure("not_a_real_failure")


def test_make_progress_endpoint_diagnostic_shapes_and_redacts():
    result = diag.make_progress_endpoint_diagnostic(
        public_ip="1.2.3.4",
        host_port=41001,
        timeout_seconds=10,
        attempt_count=6,
        first_connection_established=False,
        last_error_type="ConnectTimeout",
        last_error="GET https://console.vast.ai/?api_key=secret timed out",
        mapped_ports={"5000/tcp": [{"HostPort": "41001"}], "22/tcp": [{"HostPort": "40022"}]},
    )

    assert result["url"] == "https://1.2.3.4:41001/progress"
    assert result["public_ip"] == "1.2.3.4"
    assert result["container_port"] == diag.PROGRESS_CONTAINER_PORT
    assert result["external_port"] == "41001"
    assert result["host_port"] == "41001"
    assert result["timeout_seconds"] == 10
    assert result["attempt_count"] == 6
    assert result["first_connection_established"] is False
    assert result["last_error_type"] == "ConnectTimeout"
    assert "api_key=secret" not in result["last_error"]
    assert "api_key=REDACTED" in result["last_error"]
    assert result["mapped_ports"] == ["22/tcp", "5000/tcp"]


def test_legacy_parser_tracks_stage_and_classifies_nccl_error():
    parser = diag.LegacyProgressParser()

    assert parser.process_line("Running NCCL distributed test...") is None
    result = parser.process_line("ERROR: NCCL unhandled system error during allreduce")

    assert parser.stage == diag.STAGE_NCCL
    assert result["code"] == diag.NCCL_FAILED
    assert result["stage"] == diag.STAGE_NCCL
    assert result["underlying_error"] == "ERROR: NCCL unhandled system error during allreduce"


@pytest.mark.parametrize(
    ("line", "stage"),
    [
        ("Running ResNet18 test on all GPUs...", diag.STAGE_RESNET),
        ("Running ECC test on all GPUs...", diag.STAGE_ECC),
        ("Running NCCL distributed test with 2 GPUs...", diag.STAGE_NCCL),
        (
            "Running stress-ng and gpu-burn tests simultaneously for 60 seconds...",
            diag.STAGE_STRESS_GPU_BURN,
        ),
    ],
)
def test_legacy_parser_tracks_current_self_test_image_stage_lines(line, stage):
    parser = diag.LegacyProgressParser()

    assert parser.process_line(line) is None

    assert parser.stage == stage


def test_legacy_parser_classifies_unknown_error_as_legacy_progress_error():
    result = diag.parse_legacy_progress(
        "\n".join(
            [
                "Running system requirements test...",
                "ERROR: something unexpected happened",
            ]
        )
    )

    assert len(result) == 1
    assert result[0]["code"] == diag.LEGACY_PROGRESS_ERROR
    assert result[0]["stage"] == diag.STAGE_SYSTEM_REQUIREMENTS


def test_legacy_parser_classifies_nvml_and_nvidia_smi_error():
    result = diag.parse_legacy_progress(
        "\n".join(
            [
                "Running system requirements test...",
                "ERROR: nvidia-smi failed: Failed to initialize NVML",
            ]
        )
    )

    assert result[0]["code"] == diag.NVML_FAILED
    assert result[0]["stage"] == diag.STAGE_SYSTEM_REQUIREMENTS


def test_legacy_parser_classifies_resnet_torch_oom():
    result = diag.parse_legacy_progress(
        "\n".join(
            [
                "Running ResNet50/ResNet18 test...",
                "ERROR: torch RuntimeError: CUDA out of memory",
            ]
        )
    )

    assert result[0]["code"] == diag.RESNET_FAILED
    assert result[0]["stage"] == diag.STAGE_RESNET


def test_legacy_parser_classifies_ecc_error():
    result = diag.parse_legacy_progress(
        "\n".join(
            [
                "Running ECC test...",
                "ERROR: ECC double bit error detected",
            ]
        )
    )

    assert result[0]["code"] == diag.ECC_FAILED
    assert result[0]["stage"] == diag.STAGE_ECC


def test_legacy_parser_classifies_stress_gpu_burn_xid_error():
    result = diag.parse_legacy_progress(
        "\n".join(
            [
                "Running stress-ng and gpu-burn...",
                "ERROR: gpu-burn failed after kernel Xid 79",
            ]
        )
    )

    assert result[0]["code"] == diag.STRESS_GPU_BURN_FAILED
    assert result[0]["stage"] == diag.STAGE_STRESS_GPU_BURN


@pytest.mark.parametrize(
    "status_msg",
    [
        "Error response from daemon: manifest for vastai/test:self-test-cuda-99 not found",
        "pull access denied for private/image, repository does not exist or may require authorization",
        "unauthorized: authentication required",
    ],
)
def test_status_msg_classifies_docker_pull_failures(status_msg):
    result = diag.classify_status_msg(status_msg)

    assert result["code"] == diag.DOCKER_PULL_FAILED
    assert result["stage"] == diag.STAGE_STARTUP
    assert result["underlying_error"] == status_msg


def test_status_msg_classifies_generic_daemon_startup_failure():
    status_msg = "Error: container failed to start: OCI runtime create failed"

    result = diag.classify_status_msg(status_msg)

    assert result["code"] == diag.DAEMON_STARTUP_FAILED
    assert result["stage"] == diag.STAGE_STARTUP
    assert result["underlying_error"] == status_msg


def test_status_msg_classifies_other_errors_as_status_error():
    result = diag.classify_status_msg("Error: host reported an unknown fault")

    assert result["code"] == diag.INSTANCE_STATUS_ERROR
    assert result["stage"] == diag.STAGE_STARTUP


def test_status_msg_ignores_empty_values():
    assert diag.classify_status_msg(None) is None
    assert diag.classify_status_msg("  ") is None
