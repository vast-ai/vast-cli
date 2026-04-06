"""Unit tests for Query.unparse_query() — verifies roundtrip with parse_query."""

import re
import sys
from typing import Dict

import pytest

from vastai.data.query import Query, Column


# ---------------------------------------------------------------------------
# Local copy of parse_query (from vast/web/parse.py) so vast-sdk tests don't
# depend on the vast repo at runtime.
# ---------------------------------------------------------------------------

def numeric_version(version_str):
    try:
        major, minor, patch = version_str.split('.')
        major = major.zfill(3)
        minor = minor.zfill(3)
        patch = patch.zfill(3)
        return int(f"{major}{minor}{patch}")
    except ValueError:
        return None

offers_fields = {
    "bw_nvlink", "compute_cap", "cpu_arch", "cpu_cores", "cpu_cores_effective",
    "cpu_ghz", "cpu_ram", "cuda_max_good", "datacenter", "direct_port_count",
    "driver_version", "disk_bw", "disk_space", "dlperf", "dlperf_per_dphtotal",
    "dph_total", "duration", "external", "flops_per_dphtotal", "gpu_arch",
    "gpu_display_active", "gpu_frac", "gpu_mem_bw", "gpu_name", "gpu_ram",
    "gpu_total_ram", "gpu_max_power", "gpu_max_temp", "has_avx", "host_id",
    "id", "inet_down", "inet_down_cost", "inet_up", "inet_up_cost",
    "machine_id", "min_bid", "mobo_name", "num_gpus", "pci_gen", "pcie_bw",
    "reliability", "rentable", "rented", "storage_cost", "static_ip",
    "total_flops", "ubuntu_version", "verification", "verified", "geolocation",
}

offers_alias = {
    "cuda_vers": "cuda_max_good",
    "display_active": "gpu_display_active",
    "dlperf_usd": "dlperf_per_dphtotal",
    "dph": "dph_total",
    "flops_usd": "flops_per_dphtotal",
}

offers_mult = {
    "cpu_ram": 1000,
    "gpu_ram": 1000,
    "gpu_total_ram": 1000,
    "duration": 24.0 * 60.0 * 60.0,
}


def parse_query(query_str: str, res: Dict = None) -> Dict:
    if query_str is None:
        return res
    if res is None:
        res = {}
    if type(query_str) == list:
        query_str = " ".join(query_str)
    query_str = query_str.strip()

    pattern = r"([a-zA-Z0-9_]+)( *[=><!]+| +(?:[lg]te?|nin|neq|eq|not ?eq|not ?in|in) )?( *)(\[[^\]]+\]|\"[^\"]+\"|[^ ]+)?( *)"
    opts = re.findall(pattern, query_str)

    op_names = {
        ">=": "gte", ">": "gt", "gt": "gt", "gte": "gte",
        "<=": "lte", "<": "lt", "lt": "lt", "lte": "lte",
        "!=": "neq", "==": "eq", "=": "eq", "eq": "eq",
        "neq": "neq", "noteq": "neq", "not eq": "neq",
        "notin": "notin", "not in": "notin", "nin": "notin",
        "in": "in",
    }

    joined = "".join("".join(x) for x in opts)
    if joined != query_str:
        raise ValueError("Unconsumed text. Did you forget to quote your query? " + repr(joined) + " != " + repr(query_str))

    for field, op, _, value, _ in opts:
        value = value.strip(",[]")
        v = res.setdefault(field, {})
        op = op.strip()
        op_name = op_names.get(op)

        if field in offers_alias:
            res.pop(field)
            field = offers_alias[field]

        if (field == "driver_version") and ('.' in value):
            value = numeric_version(value)

        if not op_name:
            raise ValueError("Unknown operator. Did you forget to quote your query? " + repr(op).strip("u"))
        if op_name in ["in", "notin"]:
            value = [x.strip() for x in value.split(",") if x.strip()]
        if not value:
            raise ValueError("Value cannot be blank. Did you forget to quote your query? " + repr((field, op, value)))
        if not field:
            raise ValueError("Field cannot be blank. Did you forget to quote your query? " + repr((field, op, value)))
        if value in ["?", "*", "any"]:
            if op_name != "eq":
                raise ValueError("Wildcard only makes sense with equals.")
            if field in v:
                del v[field]
            if field in res:
                del res[field]
            continue

        if isinstance(value, str):
            value = value.replace('_', ' ')
            value = value.strip('\"')
        elif isinstance(value, list):
            value = [x.replace('_', ' ') for x in value]
            value = [x.strip('\"') for x in value]

        if field in offers_mult:
            value = float(value) * offers_mult[field]
            v[op_name] = value
        else:
            if (value == 'true') or (value == 'True'):
                v[op_name] = True
            elif (value == 'false') or (value == 'False'):
                v[op_name] = False
            elif (value == 'None') or (value == 'null'):
                v[op_name] = None
            else:
                v[op_name] = value

        if field not in res:
            res[field] = v
        else:
            res[field].update(v)
    return res


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def assert_roundtrip(query: Query):
    """Assert that unparsing then re-parsing yields the original query dict."""
    unparsed = query.unparse_query()
    reparsed = parse_query(unparsed)
    assert reparsed == query.query, (
        f"Roundtrip failed.\n"
        f"  unparsed string: {unparsed!r}\n"
        f"  reparsed dict:   {reparsed}\n"
        f"  original dict:   {query.query}"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestUnparseQueryRoundtrip:
    """Each test builds a Query by hand and checks parse_query(q.unparse_query()) == q.query."""

    def test_eq_string(self):
        assert_roundtrip(Query({"gpu_name": {"eq": "RTX 3090"}}))

    def test_eq_numeric_string(self):
        assert_roundtrip(Query({"num_gpus": {"eq": "2"}}))

    def test_eq_boolean_true(self):
        assert_roundtrip(Query({"rentable": {"eq": True}}))

    def test_eq_boolean_false(self):
        assert_roundtrip(Query({"rented": {"eq": False}}))

    def test_eq_none(self):
        assert_roundtrip(Query({"verification": {"eq": None}}))

    def test_gte(self):
        assert_roundtrip(Query({"num_gpus": {"gte": "4"}}))

    def test_lte(self):
        assert_roundtrip(Query({"num_gpus": {"lte": "8"}}))

    def test_gt(self):
        assert_roundtrip(Query({"reliability": {"gt": "0.95"}}))

    def test_lt(self):
        assert_roundtrip(Query({"dph_total": {"lt": "1.5"}}))

    def test_neq(self):
        assert_roundtrip(Query({"gpu_name": {"neq": "RTX 3090"}}))

    def test_in_list(self):
        assert_roundtrip(Query({"gpu_name": {"in": ["RTX 3090", "RTX 4090"]}}))

    def test_notin_list(self):
        assert_roundtrip(Query({"gpu_name": {"notin": ["RTX 3090", "A100"]}}))

    def test_in_single_element(self):
        assert_roundtrip(Query({"gpu_name": {"in": ["RTX 4090"]}}))

    def test_mult_field_cpu_ram(self):
        """cpu_ram is multiplied by 1000 during parsing — verify roundtrip."""
        assert_roundtrip(Query({"cpu_ram": {"gte": 32000.0}}))

    def test_mult_field_gpu_ram(self):
        assert_roundtrip(Query({"gpu_ram": {"gte": 24000.0, "lte": 48000.0}}))

    def test_mult_field_gpu_total_ram(self):
        assert_roundtrip(Query({"gpu_total_ram": {"gte": 80000.0}}))

    def test_mult_field_duration(self):
        """duration is multiplied by 86400 during parsing."""
        assert_roundtrip(Query({"duration": {"gte": 259200.0}}))

    def test_multiple_columns(self):
        assert_roundtrip(Query({
            "num_gpus": {"gte": "4"},
            "gpu_ram": {"gte": 24000.0},
            "rentable": {"eq": True},
            "rented": {"eq": False},
        }))

    def test_multiple_ops_same_column(self):
        assert_roundtrip(Query({"gpu_ram": {"gte": 8000.0, "lte": 48000.0}}))

    def test_search_defaults(self):
        """The common search_defaults() query should roundtrip."""
        assert_roundtrip(Query.search_defaults())

    def test_search_defaults_extended(self):
        q = Query.search_defaults()
        q.extend(Column("num_gpus") >= "4")
        q.extend(Column("gpu_ram") >= 24000.0)
        assert_roundtrip(q)

    def test_string_with_spaces(self):
        """Values containing spaces are encoded as underscores in query strings."""
        assert_roundtrip(Query({"gpu_name": {"eq": "NVIDIA A100"}}))

    def test_empty_query(self):
        q = Query({})
        assert q.unparse_query() == ""
        assert parse_query("") == {}

    def test_all_comparison_ops(self):
        """Verify every operator kind in a single query."""
        q = Query({
            "num_gpus": {"eq": "4"},
            "gpu_ram": {"gte": 16000.0},
            "cpu_ram": {"lte": 128000.0},
            "reliability": {"gt": "0.9"},
            "dph_total": {"lt": "2.0"},
            "gpu_name": {"neq": "RTX 3060"},
            "gpu_arch": {"in": ["ampere", "hopper"]},
            "cpu_arch": {"notin": ["arm"]},
        })
        assert_roundtrip(q)

    def test_fractional_mult_value(self):
        """Non-integer multiplied values (e.g. 0.5 days = 43200s) roundtrip."""
        assert_roundtrip(Query({"duration": {"gte": 43200.0}}))
