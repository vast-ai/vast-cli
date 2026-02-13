"""parse_query() field alias bug -- v references dict after pop.

The bug: `v = res.setdefault(field, {})` gets a reference to a dict at the
original field name. Then `res.pop(field)` removes it from res. Writing to v
modifies an orphaned dict that's no longer in res.

Fields affected: cuda_vers->cuda_max_good, dph->dph_total, dlperf_usd->dlperf_per_dphtotal

The fix: Resolve alias before calling setdefault.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def test_field_alias_cuda_vers():
    """parse_query correctly aliases cuda_vers to cuda_max_good."""
    from vast import parse_query, offers_fields, offers_alias

    result = parse_query("cuda_vers >= 12.0", {}, offers_fields, offers_alias)
    # The result should have cuda_max_good, NOT cuda_vers
    assert 'cuda_max_good' in result, (
        f"Expected 'cuda_max_good' in result, got keys: {list(result.keys())}. "
        f"Field alias not applied correctly."
    )
    assert 'cuda_vers' not in result, "Old field name 'cuda_vers' should not be in result"
    assert 'gte' in result['cuda_max_good'], (
        f"Expected 'gte' operator in cuda_max_good, got: {result['cuda_max_good']}"
    )


def test_field_alias_dph():
    """parse_query correctly aliases dph to dph_total."""
    from vast import parse_query, offers_fields, offers_alias, offers_mult

    result = parse_query("dph <= 1.5", {}, offers_fields, offers_alias, offers_mult)
    assert 'dph_total' in result, f"Expected 'dph_total', got keys: {list(result.keys())}"
    assert 'dph' not in result
    assert 'lte' in result['dph_total']


def test_field_alias_value_preserved():
    """After alias resolution, the operator value is correctly stored."""
    from vast import parse_query, offers_fields, offers_alias

    result = parse_query("cuda_vers >= 12.0", {}, offers_fields, offers_alias)
    assert result['cuda_max_good']['gte'] == '12.0', (
        f"Expected value '12.0', got: {result['cuda_max_good'].get('gte')}"
    )


def test_non_aliased_field_unaffected():
    """Fields without aliases work normally."""
    from vast import parse_query, offers_fields, offers_alias

    result = parse_query("num_gpus >= 2", {}, offers_fields, offers_alias)
    assert 'num_gpus' in result
    assert 'gte' in result['num_gpus']
    assert result['num_gpus']['gte'] == '2'
