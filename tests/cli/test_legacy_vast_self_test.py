from argparse import Namespace

import vast

from vastai.cli.self_test.machine_diagnostics import (
    SYSTEM_RAM_REQUIREMENT_CAP_MIB as PACKAGED_SYSTEM_RAM_REQUIREMENT_CAP_MIB,
)


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
