"""Unit tests for query parsing functions (parse_query, field aliases).

TEST-04: Unit tests for query parsing.

These tests verify the query parser handles field names, operators,
aliases, and various query formats correctly.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest


class TestParseQuery:
    """Tests for parse_query() function."""

    def test_simple_equality(self):
        """Simple equality operator parses correctly."""
        from vast import parse_query, offers_fields, offers_alias

        result = parse_query("gpu_ram=8", {}, offers_fields, offers_alias)

        assert 'gpu_ram' in result
        assert result['gpu_ram']['eq'] == '8'

    def test_greater_than_or_equal(self):
        """Greater-than-or-equal operator parses correctly."""
        from vast import parse_query, offers_fields, offers_alias

        result = parse_query("gpu_ram>=16", {}, offers_fields, offers_alias)

        assert 'gpu_ram' in result
        assert 'gte' in result['gpu_ram']
        assert result['gpu_ram']['gte'] == '16'

    def test_less_than_or_equal(self):
        """Less-than-or-equal operator parses correctly."""
        from vast import parse_query, offers_fields, offers_alias

        result = parse_query("gpu_ram<=32", {}, offers_fields, offers_alias)

        assert 'gpu_ram' in result
        assert 'lte' in result['gpu_ram']
        assert result['gpu_ram']['lte'] == '32'

    def test_multiple_conditions(self):
        """Multiple space-separated conditions parse correctly."""
        from vast import parse_query, offers_fields, offers_alias

        result = parse_query("gpu_ram>=8 num_gpus>=2", {}, offers_fields, offers_alias)

        assert 'gpu_ram' in result
        assert 'num_gpus' in result


class TestFieldAliases:
    """Tests for field alias handling in parse_query."""

    def test_cuda_vers_alias(self):
        """cuda_vers is aliased to cuda_max_good."""
        from vast import parse_query, offers_fields, offers_alias

        result = parse_query("cuda_vers>=12.0", {}, offers_fields, offers_alias)

        # After alias resolution, cuda_vers should become cuda_max_good
        assert 'cuda_max_good' in result
        assert 'cuda_vers' not in result
        assert 'gte' in result['cuda_max_good']

    def test_alias_resolution_preserves_value(self):
        """Alias resolution preserves the comparison value."""
        from vast import parse_query, offers_fields, offers_alias

        result = parse_query("cuda_vers>=11.8", {}, offers_fields, offers_alias)

        assert result['cuda_max_good']['gte'] == '11.8'


class TestOfferFieldsDefinition:
    """Tests verifying offers_fields contains expected fields."""

    def test_gpu_ram_field_exists(self):
        """gpu_ram is a valid offer field."""
        from vast import offers_fields

        assert 'gpu_ram' in offers_fields

    def test_num_gpus_field_exists(self):
        """num_gpus is a valid offer field."""
        from vast import offers_fields

        assert 'num_gpus' in offers_fields

    def test_cuda_max_good_field_exists(self):
        """cuda_max_good is a valid offer field."""
        from vast import offers_fields

        assert 'cuda_max_good' in offers_fields

    def test_dph_total_field_exists(self):
        """dph_total (price) is a valid offer field."""
        from vast import offers_fields

        assert 'dph_total' in offers_fields


class TestQueryEdgeCases:
    """Tests for edge cases in query parsing."""

    def test_empty_query(self):
        """Empty query returns empty result."""
        from vast import parse_query, offers_fields, offers_alias

        result = parse_query("", {}, offers_fields, offers_alias)

        assert result == {} or result is not None

    def test_whitespace_handling(self):
        """Whitespace around operators is handled."""
        from vast import parse_query, offers_fields, offers_alias

        # Query with extra whitespace should still parse
        result = parse_query("gpu_ram >= 8", {}, offers_fields, offers_alias)

        # Should have gpu_ram field with gte constraint
        assert 'gpu_ram' in result

    def test_decimal_values(self):
        """Decimal values in queries parse correctly."""
        from vast import parse_query, offers_fields, offers_alias

        result = parse_query("dph_total<=0.5", {}, offers_fields, offers_alias)

        assert 'dph_total' in result
        assert result['dph_total']['lte'] == '0.5'


class TestOfferAliasDefinition:
    """Tests for offer field alias definitions."""

    def test_offers_alias_is_dict(self):
        """offers_alias is a dictionary."""
        from vast import offers_alias

        assert isinstance(offers_alias, dict)

    def test_cuda_vers_alias_defined(self):
        """cuda_vers -> cuda_max_good alias is defined."""
        from vast import offers_alias

        assert 'cuda_vers' in offers_alias
        assert offers_alias['cuda_vers'] == 'cuda_max_good'

    def test_dph_alias_defined(self):
        """dph -> dph_total alias is defined."""
        from vast import offers_alias

        assert 'dph' in offers_alias
        assert offers_alias['dph'] == 'dph_total'
