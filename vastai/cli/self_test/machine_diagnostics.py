"""Structured diagnostics for ``vastai self-test machine``."""

from vastai.cli.util import required_inet_mbps


DIAGNOSTICS_VERSION = "1"


def safe_float(value):
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def per_gpu_vram_gib(offer):
    """Return per-GPU VRAM in GiB from canonical offer fields when possible."""
    gpu_total_ram = safe_float(offer.get("gpu_total_ram"))
    num_gpus = safe_float(offer.get("num_gpus"))
    if gpu_total_ram > 0 and num_gpus > 0:
        return gpu_total_ram / num_gpus / 1024

    gpu_ram = safe_float(offer.get("gpu_ram"))
    if gpu_ram >= 1024:
        return gpu_ram / 1024
    return gpu_ram


def compact_offer_metadata(offer):
    if not offer:
        return None
    fields = (
        "id",
        "machine_id",
        "gpu_name",
        "num_gpus",
        "dph_total",
        "dlperf",
        "cuda_max_good",
        "compute_cap",
        "reliability",
        "direct_port_count",
        "pcie_bw",
        "inet_down",
        "inet_up",
        "gpu_ram",
        "gpu_total_ram",
        "cpu_ram",
        "cpu_cores",
        "rentable",
        "rented",
    )
    return {field: offer.get(field) for field in fields if field in offer}


def base_result(machine_id):
    return {
        "success": False,
        "reason": "",
        "warning": None,
        "phase": "preflight",
        "diagnostics_version": DIAGNOSTICS_VERSION,
        "machine_id": machine_id,
        "offer": None,
        "checks": [],
        "failure": None,
        "failure_code": None,
        "stage": None,
        "error": None,
        "diagnostics": {},
    }


def _check(
    check_id,
    title,
    actual,
    required,
    operator,
    unit,
    passed,
    purpose,
    remediation,
):
    status = "pass" if passed else "fail"
    return {
        "id": check_id,
        "title": title,
        "status": status,
        "actual": actual,
        "required": required,
        "operator": operator,
        "unit": unit,
        "summary": f"{title}: actual {actual} {unit}, required {operator} {required} {unit}",
        "purpose": purpose,
        "remediation": remediation,
    }


def preflight_requirement_checks(offer):
    gpu_total_ram = safe_float(offer.get("gpu_total_ram"))
    per_gpu_ram_gib = per_gpu_vram_gib(offer)
    required_mbps = required_inet_mbps(gpu_total_ram)
    cpu_ram = safe_float(offer.get("cpu_ram"))
    cpu_cores = int(safe_float(offer.get("cpu_cores")))
    num_gpus = int(safe_float(offer.get("num_gpus")))
    required_cpu_ram = 0.95 * gpu_total_ram
    required_cpu_cores = 2 * num_gpus

    return [
        _check(
            "cuda.version",
            "CUDA version",
            safe_float(offer.get("cuda_max_good")),
            11.8,
            ">=",
            "CUDA",
            safe_float(offer.get("cuda_max_good")) >= 11.8,
            "The self-test image needs a host driver stack compatible with CUDA 11.8 or newer.",
            "Update the NVIDIA driver/CUDA stack, then confirm with: vastai search offers "
            f"'machine_id={offer.get('machine_id') or 'unknown'} rentable=any rented=any'",
        ),
        _check(
            "reliability",
            "Reliability",
            safe_float(offer.get("reliability")),
            0.90,
            ">",
            "ratio",
            safe_float(offer.get("reliability")) > 0.90,
            "Self-test uses reliability as a guardrail before launching a temporary instance.",
            "Let the host stabilize and resolve recent failures before retrying the self-test.",
        ),
        _check(
            "network.direct_ports",
            "Direct port count",
            safe_float(offer.get("direct_port_count")),
            3,
            ">",
            "ports",
            safe_float(offer.get("direct_port_count")) > 3,
            "The tester needs enough directly mapped ports for remote progress and SSH checks.",
            "Open additional direct ports or adjust host firewall/NAT settings, then rerun verification.",
        ),
        _check(
            "pcie.bandwidth",
            "PCIe bandwidth",
            safe_float(offer.get("pcie_bw")),
            2.85,
            ">",
            "GB/s",
            safe_float(offer.get("pcie_bw")) > 2.85,
            "Low PCIe bandwidth can make GPU stress and transfer checks fail or time out.",
            "Check BIOS PCIe generation/lane settings and confirm GPUs are seated in full-speed slots.",
        ),
        _check(
            "network.download",
            "Download speed",
            safe_float(offer.get("inet_down")),
            round(required_mbps, 2),
            ">=",
            "Mb/s",
            safe_float(offer.get("inet_down")) >= required_mbps,
            "The bandwidth floor scales with total VRAM so large GPU hosts can complete data movement tests.",
            "Improve host download bandwidth or reduce contention, then rerun the Vast host verification.",
        ),
        _check(
            "network.upload",
            "Upload speed",
            safe_float(offer.get("inet_up")),
            round(required_mbps, 2),
            ">=",
            "Mb/s",
            safe_float(offer.get("inet_up")) >= required_mbps,
            "The tester needs enough upload bandwidth to report progress and complete network checks.",
            "Improve host upload bandwidth or reduce contention, then rerun the Vast host verification.",
        ),
        _check(
            "gpu.ram",
            "GPU RAM",
            round(per_gpu_ram_gib, 2),
            7,
            ">",
            "GiB",
            per_gpu_ram_gib > 7,
            "The verification workload requires more than 7 GB of VRAM per GPU.",
            "Use a GPU with more VRAM for this self-test.",
        ),
        _check(
            "system.ram",
            "System RAM",
            cpu_ram,
            round(required_cpu_ram, 2),
            ">=",
            "MiB",
            cpu_ram >= required_cpu_ram,
            "System RAM must be close to total VRAM so CPU-side staging does not starve the tests.",
            "Add system RAM or reduce the listed GPU set so system RAM is at least 95% of total VRAM.",
        ),
        _check(
            "cpu.cores",
            "CPU cores",
            cpu_cores,
            required_cpu_cores,
            ">=",
            "cores",
            cpu_cores >= required_cpu_cores,
            "The tester expects at least two CPU cores per GPU for stable orchestration.",
            "Expose more CPU cores to the host or reduce the GPU count for this offer.",
        ),
    ]


def failed_checks(checks):
    return [check for check in checks if check.get("status") == "fail"]


def no_offer_failure(machine_id, broader_offers):
    broad_count = len(broader_offers or [])
    if broad_count:
        summary = f"No currently rentable on-demand offer found for machine {machine_id}."
        causes = [
            "The machine may be listed but not rentable right now.",
            "The offer may be unavailable to new rentals because host state, verification, or pricing changed.",
            "The machine may already be occupied or temporarily unavailable.",
        ]
        code = "no_rentable_offer"
    else:
        summary = f"No on-demand offer found for machine {machine_id}."
        causes = [
            "The machine may be offline.",
            "The machine may not have an active listed offer.",
            "The machine ID may be incorrect or not visible to this account.",
        ]
        code = "no_offer"

    remediation = (
        "Check host state with: vastai show machines. Then inspect offers with: "
        f"vastai search offers 'machine_id={machine_id} rentable=any rented=any'."
    )
    check = {
        "id": "offer.available",
        "title": "Rentable offer available",
        "status": "fail",
        "actual": 0,
        "required": 1,
        "operator": ">=",
        "unit": "offers",
        "summary": summary,
        "purpose": "The self-test needs a selected offer so it can rent one temporary diagnostic instance.",
        "remediation": remediation,
    }
    failure = {
        "code": code,
        "summary": summary,
        "likely_causes": causes,
        "remediation": remediation,
    }
    return check, failure


def requirement_failure(checks):
    failures = failed_checks(checks)
    summary = f"{len(failures)} preflight requirement check(s) failed."
    return {
        "code": "preflight_requirements_failed",
        "summary": summary,
        "failed_check_ids": [check["id"] for check in failures],
        "remediation": "Resolve the failed checks below, or rerun with --ignore-requirements to dogfood anyway.",
    }


def render_preflight_failure(machine_id, checks, failure=None, print_fn=print):
    print_fn(f"Preflight diagnostics for machine {machine_id} failed:")
    for check in failed_checks(checks):
        print_fn(f"- {check['title']}")
        print_fn(f"  actual: {check['actual']} {check['unit']}")
        print_fn(f"  required: {check['operator']} {check['required']} {check['unit']}")
        print_fn(f"  purpose: {check['purpose']}")
        print_fn(f"  remediation: {check['remediation']}")
    if failure and failure.get("likely_causes"):
        print_fn("Likely causes:")
        for cause in failure["likely_causes"]:
            print_fn(f"- {cause}")
