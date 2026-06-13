"""Tests for the gpu_types catalog integration in ``vastai run benchmarks``.

Covers the table-primary + hardcoded-fallback contract:
  1. Name canonicalization is the union of the query.py constants and the
     /api/v0/gpu_types/ catalog (new SKUs resolve; constants never lost).
  2. Per-card VRAM prefers the catalog's gpu_ram_mb when populated, and falls
     back to the _DEFAULT_GPUS dict when the column is null or the catalog is
     unreachable.
"""

import pytest

from vastai.cli.commands import benchmarks as bench


@pytest.fixture(autouse=True)
def _clear_catalog_caches():
    """The catalog helpers are lru_cached; clear between cases so each test sees
    its own monkeypatched _get_gpu_types.
    """
    bench._canonical_gpu_names.cache_clear()
    bench._catalog_vram_map.cache_clear()
    yield
    bench._canonical_gpu_names.cache_clear()
    bench._catalog_vram_map.cache_clear()


# ---------------------------------------------------------------------------
# Name canonicalization — union of constants + catalog
# ---------------------------------------------------------------------------


def test_canonical_union_adds_catalog_skus(monkeypatch):
    monkeypatch.setattr(bench, "_get_gpu_types", lambda: [
        {"canonical_name": "RTX 6090", "gpu_ram_mb": 49152},
    ])
    canonical = bench._canonical_gpu_names()
    assert canonical["rtx 6090"] == "RTX 6090"   # new SKU sourced from the catalog
    assert canonical["rtx 4090"] == "RTX 4090"   # existing constant preserved by the union


def test_canonical_falls_back_to_constants_when_catalog_unreachable(monkeypatch):
    monkeypatch.setattr(bench, "_get_gpu_types", lambda: None)
    canonical = bench._canonical_gpu_names()
    assert canonical["rtx 4090"] == "RTX 4090"
    assert "rtx 6090" not in canonical


def test_parse_gpu_spec_resolves_catalog_only_name(monkeypatch):
    monkeypatch.setattr(bench, "_get_gpu_types", lambda: [
        {"canonical_name": "RTX 6090", "gpu_ram_mb": 49152},
    ])
    assert bench._parse_gpu_spec("2x rtx_6090", 1) == ("RTX 6090", 2)


# ---------------------------------------------------------------------------
# Per-card VRAM — catalog-primary, dict fallback
# ---------------------------------------------------------------------------


def test_per_card_vram_prefers_populated_catalog(monkeypatch):
    monkeypatch.setattr(bench, "_get_gpu_types", lambda: [
        {"canonical_name": "RTX 4090", "gpu_ram_mb": 24576},
    ])
    assert bench._per_card_vram_mb("RTX 4090") == 24576   # catalog overrides dict's 24564


def test_per_card_vram_falls_back_when_unbackfilled(monkeypatch):
    monkeypatch.setattr(bench, "_get_gpu_types", lambda: [
        {"canonical_name": "RTX 4090", "gpu_ram_mb": None},
    ])
    assert bench._per_card_vram_mb("RTX 4090") == 24564   # _DEFAULT_GPUS fallback


def test_per_card_vram_falls_back_when_catalog_unreachable(monkeypatch):
    monkeypatch.setattr(bench, "_get_gpu_types", lambda: None)
    assert bench._per_card_vram_mb("RTX A6000") == 49140


def test_per_card_vram_none_for_unknown_gpu(monkeypatch):
    monkeypatch.setattr(bench, "_get_gpu_types", lambda: [])
    assert bench._per_card_vram_mb("Totally Fake GPU") is None
