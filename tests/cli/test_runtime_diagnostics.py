import pytest

from vastai.cli.self_test import runtime_diagnostics as diag


CUDA_ERROR_CONTAINED_CODE = "cuda_error_contained"
CUDA_ERROR_CONTAINED_TEXT = (
    "torch.AcceleratorError: CUDA error: Invalid access of peer GPU memory "
    "over nvlink or a hardware error (cudaErrorContained). Next: inspect "
    "NVLink/NVSwitch, Fabric Manager/NVLSM, and Xid/ECC/driver logs"
)


def test_failure_catalog_contains_stable_runtime_codes():
    catalog = diag.failure_catalog()

    assert set(diag.RUNTIME_FAILURE_CODES) == set(catalog)
    assert catalog[diag.DOCKER_PULL_FAILED]["code"] == diag.DOCKER_PULL_FAILED
    assert catalog[diag.CUDA_ERROR_TOO_MANY_PEERS]["code"] == diag.CUDA_ERROR_TOO_MANY_PEERS
    assert catalog[CUDA_ERROR_CONTAINED_CODE]["code"] == CUDA_ERROR_CONTAINED_CODE
    assert diag.CUDA_ERROR_CONTAINED == CUDA_ERROR_CONTAINED_CODE
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


def test_legacy_parser_promotes_known_image_failure_marker_and_stage():
    parser = diag.LegacyProgressParser()
    line = (
        "ERROR 2: Test All GPU ResNet18 failed. "
        "SELF_TEST_FAILURE[cuda_error_too_many_peers]: "
        "All-GPU ResNet18 failed on all 10 visible GPUs."
    )

    parser.process_line("Running system requirements test...")
    result = parser.process_line(line)

    assert result["code"] == diag.CUDA_ERROR_TOO_MANY_PEERS
    assert result["stage"] == diag.STAGE_RESNET
    assert result["underlying_error"] == line
    assert "peer-mapping resources" in result["summary"]


def test_legacy_parser_promotes_cuda_error_contained_marker_with_exact_detail():
    parser = diag.LegacyProgressParser()
    line = (
        "ERROR 2: Test All GPU ResNet18 failed. "
        f"SELF_TEST_FAILURE[{CUDA_ERROR_CONTAINED_CODE}]: "
        f"{CUDA_ERROR_CONTAINED_TEXT}"
    )

    parser.process_line("Running ResNet18 test on all GPUs...")
    result = parser.process_line(line)

    assert result["code"] == CUDA_ERROR_CONTAINED_CODE
    assert result["stage"] == diag.STAGE_RESNET
    assert result["error"] == line
    assert result["underlying_error"] == line
    assert "NVLink" in result["summary"]
    assert "not CUDA out-of-memory or VRAM exhaustion" in result["summary"]
    assert "terminate" in result["remediation"].lower()
    assert "relaunch" in result["remediation"].lower()
    steps = " ".join(result["suggested_steps"])
    assert "all-pairs P2P" in steps
    assert "Fabric Manager/NVLSM" in steps
    assert "Xid/ECC" in steps


@pytest.mark.parametrize(
    "marker_code",
    [
        diag.CUDA_ERROR_TOO_MANY_PEERS,
        CUDA_ERROR_CONTAINED_CODE,
        diag.CUDA_OUT_OF_MEMORY,
        diag.CUDA_DEVICE_UNAVAILABLE,
        diag.CUDA_DRIVER_OR_INITIALIZATION_ERROR,
        diag.CUDA_KERNEL_INCOMPATIBLE,
        diag.CUDA_DEVICE_EXECUTION_FAILED,
        diag.CUDA_RUNTIME_ERROR,
        diag.PYTORCH_RUNTIME_ERROR,
        diag.RESNET_PROCESS_ERROR,
    ],
)
def test_legacy_parser_preserves_all_known_resnet_failure_markers(marker_code):
    parser = diag.LegacyProgressParser()
    line = (
        "ERROR 2: Test All GPU ResNet18 failed. "
        f"SELF_TEST_FAILURE[{marker_code}]: captured diagnostic"
    )

    parser.process_line("Running system requirements test...")
    result = parser.process_line(line)

    assert result["code"] == marker_code
    assert result["stage"] == diag.STAGE_RESNET
    assert result["underlying_error"] == line


@pytest.mark.parametrize("marker_code", ["future_untrusted_code", diag.CLEANUP_FAILED])
def test_legacy_parser_rejects_non_image_failure_marker(marker_code):
    parser = diag.LegacyProgressParser()
    parser.process_line("Running ResNet18 test on all GPUs...")

    result = parser.process_line(
        f"ERROR 2: ResNet failed. SELF_TEST_FAILURE[{marker_code}]: CUDA error"
    )

    assert result["code"] == diag.RESNET_FAILED
    assert result["stage"] == diag.STAGE_RESNET


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


def test_legacy_parser_recognizes_unmarked_cuda_error_contained_signature():
    parser = diag.LegacyProgressParser()
    parser.process_line("Running ResNet18 test on all GPUs...")

    result = parser.process_line(f"ERROR 2: ResNet failed. {CUDA_ERROR_CONTAINED_TEXT}")

    assert result["code"] == CUDA_ERROR_CONTAINED_CODE
    assert result["stage"] == diag.STAGE_RESNET
    assert result["underlying_error"].endswith(CUDA_ERROR_CONTAINED_TEXT)


def test_legacy_parser_active_resnet_stage_beats_broad_hardware_error_pattern():
    parser = diag.LegacyProgressParser()
    parser.process_line("Running ResNet18 test on all GPUs...")

    result = parser.process_line(
        "ERROR 2: ResNet failed after an otherwise unclassified hardware error"
    )

    assert result["code"] == diag.RESNET_FAILED
    assert result["stage"] == diag.STAGE_RESNET


@pytest.mark.parametrize(
    ("line", "expected_code", "expected_stage"),
    [
        ("ERROR 4: NCCL distributed test failed.", diag.NCCL_FAILED, diag.STAGE_NCCL),
        ("ERROR 3: ECC test failed.", diag.ECC_FAILED, diag.STAGE_ECC),
        (
            "ERROR 6: gpu-burn test failed with a hardware error.",
            diag.STRESS_GPU_BURN_FAILED,
            diag.STAGE_STRESS_GPU_BURN,
        ),
    ],
)
def test_legacy_parser_explicit_failure_beats_stale_resnet_stage(
    line, expected_code, expected_stage
):
    result = diag.classify_legacy_error_line(line, stage=diag.STAGE_RESNET)

    assert result["code"] == expected_code
    assert result["stage"] == expected_stage


def test_unmarked_cuda_error_contained_beats_overlapping_nvml_text():
    line = (
        "ERROR 2: cudaErrorContained after invalid access of peer GPU memory over "
        "NVLink; secondary log text: driver/library version mismatch"
    )

    result = diag.classify_legacy_error_line(line, stage=diag.STAGE_RESNET)

    assert result["code"] == CUDA_ERROR_CONTAINED_CODE
    assert result["stage"] == diag.STAGE_RESNET


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


@pytest.mark.parametrize(
    "status_msg",
    [
        "Error response from daemon: manifest for image not found",
        "#7 ERROR: failed to solve: process exited with code 1",
        "docker_build() error writing dockerfile",
        "container startup failed: OCI runtime create failed",
        "pull access denied for private/image",
        "unauthorized: authentication required",
        "mount setup: permission denied",
        "Failed to pull image vastai/test:self-test",
        "rpc error: code = Unknown desc = failed to pull and unpack image",
        "manifest unknown: manifest unknown",
        "no matching manifest for linux/amd64 in the manifest list entries",
        "denied: requested access to the resource is denied",
        "docker: Error response from daemon: could not select device driver",
        "invalid reference format",
    ],
)
def test_status_message_error_marker_detects_explicit_failures(status_msg):
    assert diag.status_message_is_error(status_msg) is True


@pytest.mark.parametrize(
    "status_msg",
    [
        "#7 4.226 Get:70 http://archive.ubuntu.com/ubuntu noble/main "
        "amd64 liberror-perl all 0.17029-2 [25.6 kB]",
        "#7 9.425 Unpacking liberror-perl (0.17029-2) ...",
        "#8 1.250 Collecting exceptiongroup",
        "#8 2.500 Successfully installed exceptiongroup-1.3.0",
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
    ],
)
def test_status_message_error_marker_ignores_build_progress(status_msg):
    assert diag.status_message_is_error(status_msg) is False


def test_status_msg_ignores_empty_values():
    assert diag.classify_status_msg(None) is None
    assert diag.classify_status_msg("  ") is None
    assert diag.status_message_is_error(None) is False
    assert diag.status_message_is_error("  ") is False
