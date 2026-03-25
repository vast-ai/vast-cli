"""Tests for vastai/api/query.py — parse_query, field definitions, numeric_version."""

import pytest
from vastai.api.query import (
    parse_query, numeric_version, string_to_unix_epoch, fix_date_fields,
    offers_fields, offers_alias, offers_mult,
    benchmarks_fields, templates_fields, invoices_fields,
)


class TestNumericVersion:
    def test_standard(self):
        assert numeric_version("1.2.3") == 1002003

    def test_zero_padded(self):
        assert numeric_version("12.0.1") == 12000001

    def test_large(self):
        assert numeric_version("535.129.3") == 535129003

    def test_invalid_returns_none(self, capsys):
        result = numeric_version("bad")
        assert result is None


class TestStringToUnixEpoch:
    def test_none_returns_none(self):
        assert string_to_unix_epoch(None) is None

    def test_float_string(self):
        assert string_to_unix_epoch("1700000000.0") == 1700000000.0

    def test_date_string(self):
        result = string_to_unix_epoch("01/15/2024")
        assert isinstance(result, float)
        assert result > 0


class TestFixDateFields:
    def test_converts_date_fields(self):
        query = {"when": {"gte": "1700000000"}, "name": {"eq": "test"}}
        result = fix_date_fields(query, ["when"])
        assert result["when"]["gte"] == 1700000000.0
        assert result["name"]["eq"] == "test"

    def test_leaves_non_date_fields(self):
        query = {"score": {"gt": "5"}}
        result = fix_date_fields(query, ["when"])
        assert result["score"]["gt"] == "5"


class TestParseQuery:
    def test_equality(self):
        result = parse_query("num_gpus=1", fields=offers_fields)
        assert result["num_gpus"]["eq"] == "1"

    def test_double_equals(self):
        result = parse_query("num_gpus==1", fields=offers_fields)
        assert result["num_gpus"]["eq"] == "1"

    def test_gt(self):
        result = parse_query("reliability>0.98", fields=offers_fields)
        assert result["reliability"]["gt"] == "0.98"

    def test_gte(self):
        result = parse_query("reliability>=0.98", fields=offers_fields)
        assert result["reliability"]["gte"] == "0.98"

    def test_lt(self):
        result = parse_query("dph_total<1.0", fields=offers_fields)
        assert result["dph_total"]["lt"] == "1.0"

    def test_lte(self):
        result = parse_query("dph_total<=1.0", fields=offers_fields)
        assert result["dph_total"]["lte"] == "1.0"

    def test_neq(self):
        result = parse_query("gpu_name!=RTX_3090", fields=offers_fields)
        assert result["gpu_name"]["neq"] == "RTX 3090"

    def test_boolean_true(self):
        result = parse_query("rentable=true", fields=offers_fields)
        assert result["rentable"]["eq"] is True

    def test_boolean_false(self):
        result = parse_query("rented=false", fields=offers_fields)
        assert result["rented"]["eq"] is False

    def test_null_value(self):
        result = parse_query("external=None", fields=offers_fields)
        assert result["external"]["eq"] is None

    def test_wildcard_any_deletes_field(self):
        result = parse_query("gpu_name=any", res={"gpu_name": {"eq": "RTX_3090"}}, fields=offers_fields)
        assert "gpu_name" not in result

    def test_wildcard_star(self):
        result = parse_query("gpu_name=*", res={"gpu_name": {"eq": "RTX_3090"}}, fields=offers_fields)
        assert "gpu_name" not in result

    def test_field_alias(self):
        result = parse_query("cuda_vers>=12.0", fields=offers_fields, field_alias=offers_alias)
        assert "cuda_max_good" in result

    def test_field_multiplier(self):
        result = parse_query("cpu_ram>=16", fields=offers_fields, field_multiplier=offers_mult)
        assert result["cpu_ram"]["gte"] == 16000.0

    def test_duration_multiplier(self):
        result = parse_query("duration>=1", fields=offers_fields, field_multiplier=offers_mult)
        assert result["duration"]["gte"] == 86400.0

    def test_list_input(self):
        result = parse_query(["num_gpus=1", "gpu_name=RTX_3090"], fields=offers_fields)
        assert "num_gpus" in result
        assert "gpu_name" in result

    def test_res_accumulation(self):
        res = {"verified": {"eq": True}}
        result = parse_query("num_gpus=1", res=res, fields=offers_fields)
        assert result["verified"]["eq"] is True
        assert result["num_gpus"]["eq"] == "1"

    def test_unconsumed_text_raises(self):
        with pytest.raises(ValueError, match="Unconsumed"):
            parse_query("bad query ^^^ stuff", fields=offers_fields)

    def test_driver_version_converted(self):
        result = parse_query("driver_version>=535.129.3", fields=offers_fields)
        assert result["driver_version"]["gte"] == 535129003

    def test_quoted_string(self):
        result = parse_query('gpu_name="RTX 4090"', fields=offers_fields)
        assert result["gpu_name"]["eq"] == "RTX 4090"

    def test_none_returns_res(self):
        res = {"x": {"eq": 1}}
        assert parse_query(None, res=res) is res

    def test_empty_string(self):
        result = parse_query("", fields=offers_fields)
        assert result == {}

    def test_underscore_replaced_with_space_in_value(self):
        result = parse_query("gpu_name=RTX_4090", fields=offers_fields)
        assert result["gpu_name"]["eq"] == "RTX 4090"


class TestFieldSets:
    def test_offers_fields_not_empty(self):
        assert len(offers_fields) > 0

    def test_offers_fields_has_expected(self):
        assert "gpu_name" in offers_fields
        assert "num_gpus" in offers_fields
        assert "dph_total" in offers_fields

    def test_benchmarks_fields_not_empty(self):
        assert len(benchmarks_fields) > 0
        assert "score" in benchmarks_fields

    def test_templates_fields_not_empty(self):
        assert len(templates_fields) > 0
        assert "image" in templates_fields

    def test_invoices_fields_not_empty(self):
        assert len(invoices_fields) > 0
        assert "amount_cents" in invoices_fields

    def test_offers_alias_maps_correctly(self):
        assert offers_alias["cuda_vers"] == "cuda_max_good"
        assert offers_alias["dph"] == "dph_total"

    def test_offers_mult_values(self):
        assert offers_mult["cpu_ram"] == 1000
        assert offers_mult["duration"] == 86400.0
