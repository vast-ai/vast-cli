"""Tests for georegion query expansion and result annotation.

These tests verify that the georegion functionality ported from the original
vastai_sdk (commit 6575803) works identically to the old implementation.
"""

import pytest
from vastai.utils import (
    _regions,
    _regions_rev,
    preprocess_search_query,
    postprocess_search_results,
)


class TestRegionsMappings:
    """Verify the region data itself is correct."""

    def test_all_region_codes_present(self):
        assert set(_regions.keys()) == {'AF', 'AS', 'EU', 'LC', 'NA', 'OC'}

    def test_na_countries(self):
        assert _regions['NA'] == 'CA,US'

    def test_reverse_mapping_us(self):
        assert _regions_rev['US'] == 'NA'

    def test_reverse_mapping_de(self):
        assert _regions_rev['DE'] == 'EU'

    def test_reverse_mapping_jp(self):
        assert _regions_rev['JP'] == 'AS'

    def test_reverse_mapping_br(self):
        assert _regions_rev['BR'] == 'LC'

    def test_reverse_mapping_au(self):
        # AU appears in both AS and OC in the original data; OC is processed
        # last so it wins in the reverse mapping.
        assert _regions_rev['AU'] in ('AS', 'OC')

    def test_reverse_mapping_za(self):
        assert _regions_rev['ZA'] == 'AF'

    def test_every_country_maps_back(self):
        """Every country in _regions must appear in _regions_rev."""
        for code, countries_str in _regions.items():
            for country in countries_str.split(','):
                assert country in _regions_rev, f"{country} from region {code} not in reverse mapping"


class TestExpandQueryDirectives:
    """Test the pre-processing query expansion hook."""

    def test_none_query(self):
        geo, chunked, q = preprocess_search_query(None)
        assert geo is False
        assert chunked is False
        assert q is None

    def test_no_georegion_flag(self):
        geo, chunked, q = preprocess_search_query('num_gpus = 1 gpu_name = RTX_4090')
        assert geo is False
        assert chunked is False
        assert q == 'num_gpus = 1 gpu_name = RTX_4090'

    def test_georegion_na_expansion(self):
        geo, chunked, q = preprocess_search_query('num_gpus = 1 geolocation = NA georegion = true')
        assert geo is True
        assert chunked is False
        assert 'georegion' not in q
        assert 'geolocation in [CA,US]' in q
        assert 'num_gpus = 1' in q

    def test_georegion_eu_expansion(self):
        geo, chunked, q = preprocess_search_query('geolocation = EU georegion = true')
        assert geo is True
        assert 'geolocation in [' in q
        assert 'DE' in q
        assert 'FR' in q
        assert 'GB' in q

    def test_georegion_preserves_other_fields(self):
        geo, chunked, q = preprocess_search_query('num_gpus = 2 gpu_name = A100 geolocation = NA georegion = true')
        assert geo is True
        assert 'num_gpus = 2' in q
        assert 'gpu_name = A100' in q

    def test_georegion_false_not_set(self):
        """georegion=false or georegion=anything-else should not trigger expansion."""
        geo, chunked, q = preprocess_search_query('geolocation = NA georegion = false')
        assert geo is False

    def test_georegion_without_geolocation(self):
        """georegion=true but no geolocation field — just strips georegion."""
        geo, chunked, q = preprocess_search_query('num_gpus = 1 georegion = true')
        assert geo is True
        assert 'georegion' not in q
        assert 'num_gpus = 1' in q

    def test_chunked_only(self):
        geo, chunked, q = preprocess_search_query('num_gpus = 1 chunked = true')
        assert geo is False
        assert chunked is True
        assert 'chunked' not in q
        assert 'num_gpus = 1' in q

    def test_georegion_and_chunked(self):
        geo, chunked, q = preprocess_search_query('geolocation = NA georegion = true chunked = true')
        assert geo is True
        assert chunked is True
        assert 'georegion' not in q
        assert 'chunked' not in q
        assert 'geolocation in [CA,US]' in q


class TestAnnotateSearchResults:
    """Test the post-processing result annotation hook."""

    def test_datacenter_field_always_added(self):
        results = [{'hosting_type': 1, 'id': 1}, {'hosting_type': 0, 'id': 2}]
        annotated = postprocess_search_results(results)
        assert annotated[0]['datacenter'] is True
        assert annotated[1]['datacenter'] is False

    def test_annotate_us(self):
        results = [{'geolocation': 'US', 'hosting_type': 0, 'id': 1}]
        annotated = postprocess_search_results(results, georegion_active=True)
        assert annotated[0]['geolocation'] == 'US, NA'

    def test_annotate_de(self):
        results = [{'geolocation': 'DE', 'hosting_type': 0, 'id': 2}]
        annotated = postprocess_search_results(results, georegion_active=True)
        assert annotated[0]['geolocation'] == 'DE, EU'

    def test_annotate_multiple(self):
        results = [
            {'geolocation': 'US', 'hosting_type': 1, 'id': 1},
            {'geolocation': 'DE', 'hosting_type': 0, 'id': 2},
            {'geolocation': 'JP', 'hosting_type': 0, 'id': 3},
        ]
        annotated = postprocess_search_results(results, georegion_active=True)
        assert annotated[0]['geolocation'] == 'US, NA'
        assert annotated[1]['geolocation'] == 'DE, EU'
        assert annotated[2]['geolocation'] == 'JP, AS'

    def test_annotate_unknown_country(self):
        """Unknown countries should be left unchanged (not crash)."""
        results = [{'geolocation': 'XX', 'hosting_type': 0, 'id': 1}]
        annotated = postprocess_search_results(results, georegion_active=True)
        assert annotated[0]['geolocation'] == 'XX'

    def test_annotate_empty_geolocation(self):
        results = [{'geolocation': '', 'hosting_type': 0, 'id': 1}]
        annotated = postprocess_search_results(results, georegion_active=True)
        assert annotated[0]['geolocation'] == ''

    def test_annotate_missing_geolocation(self):
        results = [{'hosting_type': 0, 'id': 1}]
        annotated = postprocess_search_results(results, georegion_active=True)
        assert 'geolocation' not in annotated[0] or annotated[0].get('geolocation', '') == ''

    def test_annotate_longer_geolocation_string(self):
        """Handles geolocation values like 'California, US' by taking last 2 chars."""
        results = [{'geolocation': 'California, US', 'hosting_type': 0, 'id': 1}]
        annotated = postprocess_search_results(results, georegion_active=True)
        assert annotated[0]['geolocation'] == 'California, US, NA'

    def test_chunked_filters_low_resources(self):
        results = [
            {'hosting_type': 1, 'cpu_ram': 128 * 1024, 'cpu_cores': 64, 'min_bid': 1, 'gpu_ram': 24576, 'disk_space': 500, 'id': 1},
            {'hosting_type': 0, 'cpu_ram': 16 * 1024, 'cpu_cores': 8, 'min_bid': 0, 'gpu_ram': 8192, 'disk_space': 100, 'id': 2},
        ]
        annotated = postprocess_search_results(results, chunked=True)
        # Second result should be filtered out (cpu_ram < 64*1024)
        assert len(annotated) == 1
        assert annotated[0]['id'] == 1

    def test_chunked_rounds_gpu_ram_and_disk(self):
        results = [
            {'hosting_type': 1, 'cpu_ram': 128 * 1024, 'cpu_cores': 64, 'min_bid': 1, 'gpu_ram': 24577, 'disk_space': 513, 'id': 1},
        ]
        annotated = postprocess_search_results(results, chunked=True)
        assert annotated[0]['gpu_ram'] == 24577 & 0xffffffffff0
        assert annotated[0]['disk_space'] == 513 & 0xffffffffffc0

    def test_no_georegion_skips_annotation(self):
        """Without georegion_active, geolocation should not be modified."""
        results = [{'geolocation': 'US', 'hosting_type': 0, 'id': 1}]
        annotated = postprocess_search_results(results, georegion_active=False)
        assert annotated[0]['geolocation'] == 'US'


class TestEndToEndGeoregionFlow:
    """Test the full expand → parse_query → annotate pipeline."""

    def test_full_pipeline_na(self):
        from vastai.api.query import parse_query, offers_fields, offers_alias, offers_mult

        # Step 1: Expand
        geo, chunked, query_str = preprocess_search_query(
            'num_gpus = 1 geolocation = NA georegion = true'
        )
        assert geo is True

        # Step 2: Parse into query dict
        query = parse_query(query_str, {}, offers_fields, offers_alias, offers_mult)
        assert 'geolocation' in query
        assert 'in' in query['geolocation']
        countries = query['geolocation']['in']
        assert 'CA' in countries
        assert 'US' in countries

        # Step 3: Annotate results
        fake_results = [
            {'geolocation': 'US', 'hosting_type': 1, 'id': 1},
            {'geolocation': 'CA', 'hosting_type': 0, 'id': 2},
        ]
        annotated = postprocess_search_results(fake_results, georegion_active=True)
        assert annotated[0]['geolocation'] == 'US, NA'
        assert annotated[1]['geolocation'] == 'CA, NA'

    def test_full_pipeline_no_georegion(self):
        from vastai.api.query import parse_query, offers_fields, offers_alias, offers_mult

        geo, chunked, query_str = preprocess_search_query('num_gpus = 1 gpu_name = RTX_4090')
        assert geo is False

        query = parse_query(query_str, {}, offers_fields, offers_alias, offers_mult)
        assert 'georegion' not in query
        assert query['num_gpus'] == {'eq': '1'}
