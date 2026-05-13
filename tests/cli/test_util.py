"""Tests for vastai/cli/util.py — parse_env, parse_vast_url, validate_seconds, etc."""

import argparse
import pytest
from datetime import datetime, timedelta


class TestParseEnv:
    def test_key_value(self):
        from vastai.cli.util import parse_env
        result = parse_env("-e KEY=val")
        assert result["KEY"] == "val"

    def test_multiple_vars(self):
        from vastai.cli.util import parse_env
        result = parse_env("-e A=1 -e B=2")
        assert result["A"] == "1"
        assert result["B"] == "2"

    def test_port_mapping(self):
        from vastai.cli.util import parse_env
        result = parse_env("-p 8080:8080/tcp")
        assert "-p 8080:8080/tcp" in result

    def test_volume_mapping(self):
        from vastai.cli.util import parse_env
        result = parse_env("-v /host:/container")
        assert "-v /host:/container" in result

    def test_none_input(self):
        from vastai.cli.util import parse_env
        result = parse_env(None)
        assert result == {}

    def test_equals_in_value(self):
        from vastai.cli.util import parse_env
        result = parse_env("-e KEY=val=with=equals")
        assert result["KEY"] == "val=with=equals"


class TestParseVastUrl:
    def test_id_with_path(self):
        from vastai.cli.util import parse_vast_url
        instance_id, path = parse_vast_url("123:/data/model")
        assert instance_id == "123"
        assert path == "/data/model"

    def test_id_only(self):
        from vastai.cli.util import parse_vast_url
        instance_id, path = parse_vast_url("123")
        assert instance_id == 123
        assert path == "/"

    def test_path_only(self):
        from vastai.cli.util import parse_vast_url
        instance_id, path = parse_vast_url("/data/model")
        assert instance_id is None
        assert path == "/data/model"

    def test_invalid_vrl_raises(self):
        from vastai.cli.util import parse_vast_url, VRLException
        with pytest.raises(VRLException):
            parse_vast_url("a:b:c")

    def test_invalid_path_raises(self):
        from vastai.cli.util import parse_vast_url, VRLException
        with pytest.raises(VRLException, match="not a valid Unix"):
            parse_vast_url("123:\x00bad")


class TestValidateSeconds:
    def test_valid_timestamp(self):
        from vastai.cli.util import validate_seconds
        now = int(datetime.now().timestamp())
        assert validate_seconds(str(now)) == now

    def test_too_old_raises(self):
        from vastai.cli.util import validate_seconds
        with pytest.raises(argparse.ArgumentTypeError):
            validate_seconds("1000")

    def test_too_far_future_raises(self):
        from vastai.cli.util import validate_seconds
        with pytest.raises(argparse.ArgumentTypeError):
            validate_seconds("99999999999")

    def test_non_numeric_raises(self):
        from vastai.cli.util import validate_seconds
        with pytest.raises(argparse.ArgumentTypeError):
            validate_seconds("not_a_number")


class TestSmartSplit:
    def test_simple(self):
        from vastai.cli.util import smart_split
        result = smart_split("a b c", " ")
        assert result == ["a", "b", "c"]

    def test_double_quoted(self):
        from vastai.cli.util import smart_split
        result = smart_split('a "b c" d', " ")
        assert result == ["a", '"b c"', "d"]

    def test_single_quoted(self):
        from vastai.cli.util import smart_split
        result = smart_split("a 'b c' d", " ")
        assert result == ["a", "'b c'", "d"]


class TestSplitList:
    def test_even(self):
        from vastai.cli.util import split_list
        result = split_list([1, 2, 3, 4], 2)
        assert result == [[1, 2], [3, 4]]

    def test_uneven(self):
        from vastai.cli.util import split_list
        result = split_list([1, 2, 3, 4, 5], 2)
        assert result == [[1, 2], [3, 4], [5]]

    def test_empty(self):
        from vastai.cli.util import split_list
        result = split_list([], 3)
        assert result == []


class TestParseVersion:
    def test_standard(self):
        from vastai.cli.util import parse_version
        assert parse_version("1.2.3") == (1, 2, 3)

    def test_large_numbers(self):
        from vastai.cli.util import parse_version
        assert parse_version("10.20.30") == (10, 20, 30)


class TestParseDayCronStyle:
    def test_valid_day(self):
        from vastai.cli.util import parse_day_cron_style
        assert parse_day_cron_style("3") == 3

    def test_wildcard(self):
        from vastai.cli.util import parse_day_cron_style
        assert parse_day_cron_style("*") is None

    def test_invalid_raises(self):
        from vastai.cli.util import parse_day_cron_style
        with pytest.raises(argparse.ArgumentTypeError):
            parse_day_cron_style("7")

    def test_boundary_zero(self):
        from vastai.cli.util import parse_day_cron_style
        assert parse_day_cron_style("0") == 0

    def test_boundary_six(self):
        from vastai.cli.util import parse_day_cron_style
        assert parse_day_cron_style("6") == 6


class TestParseHourCronStyle:
    def test_valid_hour(self):
        from vastai.cli.util import parse_hour_cron_style
        assert parse_hour_cron_style("14") == 14

    def test_wildcard(self):
        from vastai.cli.util import parse_hour_cron_style
        assert parse_hour_cron_style("*") is None

    def test_invalid_raises(self):
        from vastai.cli.util import parse_hour_cron_style
        with pytest.raises(argparse.ArgumentTypeError):
            parse_hour_cron_style("24")

    def test_boundary_zero(self):
        from vastai.cli.util import parse_hour_cron_style
        assert parse_hour_cron_style("0") == 0

    def test_boundary_23(self):
        from vastai.cli.util import parse_hour_cron_style
        assert parse_hour_cron_style("23") == 23


class TestConvertDatesToTimestamps:
    def _args(self, start=None, end=None):
        return argparse.Namespace(start_date=start, end_date=end)

    def test_date_only_input_is_utc_midnight(self):
        from vastai.cli.util import convert_dates_to_timestamps
        start, end = convert_dates_to_timestamps(self._args(start="2024-01-15", end="2024-01-16"))
        # 2024-01-15 00:00 UTC and 2024-01-16 00:00 UTC
        assert start == 1705276800.0
        assert end == 1705363200.0

    def test_date_only_input_unaffected_by_local_tz(self, monkeypatch):
        import time as _time
        if not hasattr(_time, "tzset"):
            pytest.skip("tzset unavailable on this platform")
        monkeypatch.setenv("TZ", "America/Los_Angeles")
        _time.tzset()
        try:
            from vastai.cli.util import convert_dates_to_timestamps
            start, end = convert_dates_to_timestamps(self._args(start="2024-01-15", end="2024-01-16"))
            assert start == 1705276800.0
            assert end == 1705363200.0
        finally:
            _time.tzset()

    def test_aware_input_keeps_its_offset(self):
        from vastai.cli.util import convert_dates_to_timestamps
        # 2024-01-15 00:00 -05:00 = 2024-01-15 05:00 UTC
        start, _ = convert_dates_to_timestamps(self._args(start="2024-01-15T00:00:00-05:00"))
        assert start == 1705276800.0 + 5 * 3600


class TestScheduledJobsDisplayUtc:
    def test_start_time_formats_in_utc(self, monkeypatch):
        import time as _time
        if not hasattr(_time, "tzset"):
            pytest.skip("tzset unavailable on this platform")
        monkeypatch.setenv("TZ", "America/Los_Angeles")
        _time.tzset()
        try:
            from vastai.cli.display import scheduled_jobs_fields
            formatter = dict((f[0], f[3]) for f in scheduled_jobs_fields)["start_time"]
            # 1705276800 = 2024-01-15 00:00 UTC
            assert formatter(1705276800) == "2024-01-15/00:00"
        finally:
            _time.tzset()
