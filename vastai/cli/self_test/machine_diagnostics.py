"""Structured diagnostics for ``vastai self-test machine``."""

from vastai.cli.util import required_inet_mbps


DIAGNOSTICS_VERSION = "1"
ROOT_CURRENTLY_RENTED = "currently_rented"
ROOT_DEVERIFIED_OR_BELOW_THRESHOLD = "deverified_or_below_threshold"
ROOT_API_PERMISSION_FAILED = "api_permission_failed"
ROOT_ZERO_ACTIVE_OFFERS = "zero_active_offers"
ROOT_OFFLINE_OR_NOT_LISTED = "offline_or_not_listed"
ROOT_UNKNOWN_NO_RENTABLE_OFFER = "unknown_no_rentable_offer"

NO_OFFER_ROOT_STATES = (
    ROOT_CURRENTLY_RENTED,
    ROOT_DEVERIFIED_OR_BELOW_THRESHOLD,
    ROOT_API_PERMISSION_FAILED,
    ROOT_ZERO_ACTIVE_OFFERS,
    ROOT_OFFLINE_OR_NOT_LISTED,
    ROOT_UNKNOWN_NO_RENTABLE_OFFER,
)

# Very large GPU hosts, such as 8x B300 systems, can exceed 2 TB of total VRAM.
# Once a host has about 2 TB of system RAM, do not disqualify it only because it
# is slightly below 95% of total VRAM.
SYSTEM_RAM_REQUIREMENT_CAP_MIB = 2_000_000


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
        "vericode",
        "verified",
        "verification",
        "error_description",
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


def _info_check(
    check_id,
    title,
    actual,
    recommended,
    operator,
    unit,
    summary,
    purpose,
    remediation,
):
    return {
        "id": check_id,
        "title": title,
        "status": "info",
        "actual": actual,
        "required": recommended,
        "operator": operator,
        "unit": unit,
        "summary": summary,
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
    direct_port_count = safe_float(offer.get("direct_port_count"))
    recommended_max_ports = 64 * num_gpus if num_gpus > 0 else 64
    uncapped_required_cpu_ram = 0.95 * gpu_total_ram
    required_cpu_ram = min(uncapped_required_cpu_ram, SYSTEM_RAM_REQUIREMENT_CAP_MIB)
    required_cpu_cores = 2 * num_gpus

    checks = [
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
            direct_port_count,
            3,
            ">",
            "ports",
            direct_port_count > 3,
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
            (
                "System RAM must be close to total VRAM so CPU-side staging does not starve the tests. "
                "For very large GPU hosts, this requirement is capped at about 2 TB."
            ),
            (
                "Add system RAM or reduce the listed GPU set so system RAM is at least 95% of "
                "total VRAM, up to the 2 TB cap."
            ),
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
    if direct_port_count > recommended_max_ports:
        checks.append(
            _info_check(
                "network.direct_ports.recommended_max",
                "Direct port count advisory",
                direct_port_count,
                recommended_max_ports,
                "<=",
                "ports",
                (
                    f"Direct port count: actual {direct_port_count} ports, recommended <= "
                    f"{recommended_max_ports} ports for {num_gpus or 1} GPU(s)"
                ),
                (
                    "Vast instances can use at most 64 open ports each. Mapping more than "
                    "64 ports per listed GPU is usually wasted effort."
                ),
                (
                    "This is advisory only, not a self-test gate. Keep enough direct ports for "
                    "self-test and normal workloads, but avoid mapping very large unused ranges."
                ),
            )
        )
    return checks


def failed_checks(checks):
    return [check for check in checks if check.get("status") == "fail"]


def informational_checks(checks):
    return [check for check in checks if check.get("status") == "info"]


def _http_status(error):
    if not error:
        return None
    if isinstance(error, dict):
        return error.get("status_code")
    response = getattr(error, "response", None)
    return getattr(response, "status_code", None)


def _machine_lookup_status(machine_lookup):
    if not machine_lookup:
        return None, []
    if isinstance(machine_lookup, dict) and "status" in machine_lookup:
        status = machine_lookup.get("status")
        rows = machine_lookup.get("rows") or []
        if isinstance(rows, dict):
            rows = [rows] if rows else []
        return status, rows
    if isinstance(machine_lookup, list):
        return ("visible", machine_lookup) if machine_lookup else ("empty", [])
    if isinstance(machine_lookup, dict):
        return ("visible", [machine_lookup]) if machine_lookup else ("empty", [])
    return None, []


def diagnose_no_offer_state(machine_id, broader_offers, machine_lookup=None, search_error=None):
    """Infer the most likely no-rentable root state from CLI-visible data.

    This is intentionally heuristic. Public offer search alone cannot prove
    whether a machine is offline, hidden, or has zero active offers, so the
    return value includes a confidence field for UI/host copy.
    """
    offers = broader_offers or []
    evidence = []
    suggested_steps = [
        f"Inspect all visible offers with: vastai search offers 'machine_id={machine_id} rentable=any rented=any'."
    ]

    search_status = _http_status(search_error)
    lookup_status, lookup_rows = _machine_lookup_status(machine_lookup)
    lookup_status_code = machine_lookup.get("status_code") if isinstance(machine_lookup, dict) else None

    if search_status in (401, 403) or lookup_status in ("permission_denied", "unauthorized") or lookup_status_code in (401, 403):
        if search_status:
            evidence.append(f"Offer search failed with HTTP {search_status}.")
        if lookup_status_code:
            evidence.append(f"Machine lookup failed with HTTP {lookup_status_code}.")
        evidence.append("The API key or account could not read the required machine/offer state.")
        suggested_steps = [
            "Check that the API key is valid and has permission to read offers and hosted machines.",
            "Retry after logging in with an account that owns or can inspect this host.",
        ]
        return {
            "root_state": ROOT_API_PERMISSION_FAILED,
            "confidence": "high",
            "evidence": evidence,
            "suggested_steps": suggested_steps,
        }

    if offers:
        evidence.append(f"Found {len(offers)} visible offer(s), but none were currently rentable.")
        rented_offers = [offer for offer in offers if offer.get("rented") is True]
        if rented_offers:
            evidence.append(f"{len(rented_offers)} visible offer(s) are marked rented=true.")
            suggested_steps = [
                "Wait for the current rental to end, then retry the self-test.",
                suggested_steps[0],
            ]
            return {
                "root_state": ROOT_CURRENTLY_RENTED,
                "confidence": "medium",
                "evidence": evidence,
                "suggested_steps": suggested_steps,
            }

        state_evidence = []
        for offer in offers:
            reliability = safe_float(offer.get("reliability"))
            vericode = offer.get("vericode")
            verified = offer.get("verified")
            verification = offer.get("verification")
            error_description = offer.get("error_description")
            if reliability and reliability <= 0.90:
                state_evidence.append(f"Offer reliability is {reliability}, which is at or below the 0.90 self-test threshold.")
            if vericode not in (None, "", 0, "0"):
                state_evidence.append(f"Offer reports vericode={vericode}.")
            if verified is False:
                state_evidence.append("Offer is marked verified=false.")
            if isinstance(verification, str) and verification.lower() not in ("", "verified", "true"):
                state_evidence.append(f"Offer verification state is {verification}.")
            if error_description:
                state_evidence.append(f"Offer error_description is {error_description}.")

        if state_evidence:
            evidence.extend(state_evidence)
            suggested_steps = [
                "Resolve the host verification or reliability issue, then wait for the offer state to refresh.",
                suggested_steps[0],
            ]
            return {
                "root_state": ROOT_DEVERIFIED_OR_BELOW_THRESHOLD,
                "confidence": "medium",
                "evidence": evidence,
                "suggested_steps": suggested_steps,
            }

        evidence.append("Visible offers exist, but their payload did not expose a specific non-rentable reason.")
        suggested_steps = [
            "Refresh the marketplace/host state and retry shortly.",
            suggested_steps[0],
        ]
        return {
            "root_state": ROOT_UNKNOWN_NO_RENTABLE_OFFER,
            "confidence": "low",
            "evidence": evidence,
            "suggested_steps": suggested_steps,
        }

    evidence.append("No visible on-demand offers were returned for this machine.")
    if lookup_status == "visible" and lookup_rows:
        evidence.append("Machine lookup returned a visible machine record.")
        suggested_steps = [
            "List or relist an on-demand offer for this machine, then retry self-test.",
            "Check host listing state with: vastai show machines.",
        ]
        return {
            "root_state": ROOT_ZERO_ACTIVE_OFFERS,
            "confidence": "medium",
            "evidence": evidence,
            "suggested_steps": suggested_steps,
        }

    if lookup_status in ("empty", "not_found") or lookup_status_code == 404:
        if lookup_status_code == 404:
            evidence.append("Machine lookup returned HTTP 404.")
        else:
            evidence.append("Machine lookup returned no visible machine record.")
    elif lookup_status:
        evidence.append(f"Machine lookup status was {lookup_status}.")
    else:
        evidence.append("No authoritative machine lookup result was available.")

    suggested_steps = [
        "Confirm the machine ID is correct and the host is online.",
        "If this is your host, check that it is listed and visible with: vastai show machines.",
        suggested_steps[0],
    ]
    return {
        "root_state": ROOT_OFFLINE_OR_NOT_LISTED,
        "confidence": "low",
        "evidence": evidence,
        "suggested_steps": suggested_steps,
    }


def no_offer_failure(machine_id, broader_offers, machine_lookup=None, search_error=None):
    diagnosis = diagnose_no_offer_state(
        machine_id,
        broader_offers,
        machine_lookup=machine_lookup,
        search_error=search_error,
    )
    broad_count = len(broader_offers or [])
    if diagnosis["root_state"] == ROOT_API_PERMISSION_FAILED:
        summary = f"Could not inspect rentable offers for machine {machine_id} because API authorization failed."
        causes = [
            "The API key may be invalid, expired, or missing permission to read offer/machine state.",
        ]
        code = "api_permission_failed"
        remediation = "Check the API key permissions, then retry with an account that can inspect this host."
    elif broad_count:
        summary = f"No currently rentable on-demand offer found for machine {machine_id}."
        causes = [
            "The machine may be listed but not rentable right now.",
            "The offer may be unavailable to new rentals because host state, verification, or pricing changed.",
            "The machine may already be occupied or temporarily unavailable.",
        ]
        code = "no_rentable_offer"
        remediation = (
            "Check host state with: vastai show machines. Then inspect offers with: "
            f"vastai search offers 'machine_id={machine_id} rentable=any rented=any'."
        )
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
        "root_state": diagnosis["root_state"],
        "confidence": diagnosis["confidence"],
        "evidence": diagnosis["evidence"],
        "suggested_steps": diagnosis["suggested_steps"],
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
    if failure and failure.get("root_state"):
        print_fn(f"Root state: {failure['root_state']} (confidence: {failure.get('confidence', 'unknown')})")
    evidence = failure.get("evidence") if failure else None
    if evidence:
        print_fn("Evidence:")
        for item in evidence:
            print_fn(f"- {item}")
    steps = failure.get("suggested_steps") if failure else None
    if steps:
        print_fn("Suggested steps:")
        for step in steps:
            print_fn(f"- {step}")


def render_preflight_advisories(machine_id, checks, print_fn=print):
    info_checks = informational_checks(checks)
    if not info_checks:
        return
    print_fn(f"Preflight advisory for machine {machine_id}:")
    for check in info_checks:
        print_fn(f"- {check['title']}")
        print_fn(f"  actual: {check['actual']} {check['unit']}")
        print_fn(f"  recommended: {check['operator']} {check['required']} {check['unit']}")
        print_fn(f"  purpose: {check['purpose']}")
        print_fn(f"  note: {check['remediation']}")
