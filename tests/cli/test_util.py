"""Tests for vastai/cli/util.py — parse_env, parse_vast_url, validate_seconds, etc."""

import argparse
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock


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


class TestGetGpuNames:
    def test_returns_none_when_live_lookup_fails(self, monkeypatch, tmp_path):
        from requests.exceptions import HTTPError
        from vastai.cli import util

        response = Mock()
        response.raise_for_status.side_effect = HTTPError("403 Client Error")

        monkeypatch.setattr(util, "CACHE_FILE", str(tmp_path / "missing-cache.json"))
        monkeypatch.setattr(util.requests, "get", Mock(return_value=response))

        assert util._get_gpu_names() is None

    def test_formats_gpu_names_from_live_lookup(self, monkeypatch, tmp_path):
        from vastai.cli import util

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"gpu_names": ["RTX 4090", "H100-SXM"]}

        monkeypatch.setattr(util, "CACHE_FILE", str(tmp_path / "gpu-cache.json"))
        monkeypatch.setattr(util.requests, "get", Mock(return_value=response))

        assert util._get_gpu_names() == ["RTX_4090", "H100_SXM"]


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


class TestRequiredInetMbps:
    # Inputs are gpu_total_ram in MiB (matches ask_contract_offers.gpu_total_ram).
    # Formula: min(500, max(100, 500 * (mib/1024) / 192))

    def test_missing_falls_to_floor(self):
        from vastai.cli.util import required_inet_mbps
        assert required_inet_mbps(None) == 100.0
        assert required_inet_mbps(0) == 100.0

    def test_tiny_vram_floors_at_100(self):
        from vastai.cli.util import required_inet_mbps
        # 8 GiB
        assert required_inet_mbps(8 * 1024) == 100.0

    def test_huge_vram_caps_at_500(self):
        from vastai.cli.util import required_inet_mbps
        # 1 TiB total VRAM
        assert required_inet_mbps(1024 * 1024) == 500.0

    # Single-GPU reference table from the ticket. VRAM expressed as marketing-GiB
    # converted to MiB by multiplying by 1024 (i.e. binary GiB inputs).
    def test_reference_48gib_single_gpu(self):
        from vastai.cli.util import required_inet_mbps
        # A6000 marketing 48 GB
        assert required_inet_mbps(48 * 1024) == pytest.approx(125.0, rel=1e-3)

    def test_reference_80gib_single_gpu(self):
        from vastai.cli.util import required_inet_mbps
        # H100 80 GB
        assert required_inet_mbps(80 * 1024) == pytest.approx(208.33, rel=1e-3)

    def test_reference_96gib_single_gpu(self):
        from vastai.cli.util import required_inet_mbps
        assert required_inet_mbps(96 * 1024) == pytest.approx(250.0, rel=1e-3)

    def test_reference_141gib_single_gpu(self):
        from vastai.cli.util import required_inet_mbps
        # H200 141 GB
        assert required_inet_mbps(141 * 1024) == pytest.approx(367.19, rel=1e-3)

    def test_reference_192gib_single_gpu_hits_cap(self):
        from vastai.cli.util import required_inet_mbps
        # B200 marketing 192 GB, expressed as binary GiB
        assert required_inet_mbps(192 * 1024) == 500.0

    # Multi-GPU machines scale with total VRAM and hit the cap quickly.
    def test_2x_h100_total_160gib(self):
        from vastai.cli.util import required_inet_mbps
        assert required_inet_mbps(2 * 80 * 1024) == pytest.approx(416.67, rel=1e-3)

    def test_4x_h100_total_320gib_caps(self):
        from vastai.cli.util import required_inet_mbps
        assert required_inet_mbps(4 * 80 * 1024) == 500.0

    def test_8x_a6000_total_384gib_caps(self):
        from vastai.cli.util import required_inet_mbps
        assert required_inet_mbps(8 * 48 * 1024) == 500.0

    def test_2x_a6000_total_96gib(self):
        from vastai.cli.util import required_inet_mbps
        assert required_inet_mbps(2 * 48 * 1024) == pytest.approx(250.0, rel=1e-3)

    # Real B200 reports 183359 MiB (~179 GiB) — verifies that actual hardware
    # values land just below the cap rather than hitting it exactly. Documented
    # behavior; cap is reached at 192 GiB total.
    def test_real_b200_mib_lands_below_cap(self):
        from vastai.cli.util import required_inet_mbps
        result = required_inet_mbps(183359)
        assert 460.0 < result < 470.0


class TestRole:
    """get_role / set_role_file — the client/host CLI display preference (CLN-3582)."""

    def test_unset_returns_none(self, tmp_path, monkeypatch):
        from vastai.cli.util import get_role
        monkeypatch.setattr("vastai.cli.util.ROLE_FILE", str(tmp_path / "vast_role"))
        assert get_role() is None

    def test_set_then_get_round_trips(self, tmp_path, monkeypatch):
        from vastai.cli.util import get_role, set_role_file
        monkeypatch.setattr("vastai.cli.util.ROLE_FILE", str(tmp_path / "vast_role"))
        set_role_file("host")
        assert get_role() == "host"

    def test_invalid_role_raises(self, tmp_path, monkeypatch):
        from vastai.cli.util import set_role_file
        monkeypatch.setattr("vastai.cli.util.ROLE_FILE", str(tmp_path / "vast_role"))
        with pytest.raises(ValueError):
            set_role_file("admin")

    def test_corrupt_file_contents_return_none_not_raise(self, tmp_path, monkeypatch):
        from vastai.cli.util import get_role
        role_file = tmp_path / "vast_role"
        role_file.write_text("garbage\nbinary\x00data")
        monkeypatch.setattr("vastai.cli.util.ROLE_FILE", str(role_file))
        assert get_role() is None


class TestEnsureHostRoleDetected:
    """ensure_host_role_detected — lazy role resolution for pre-existing installs (CLN-3582)."""

    def _client(self, tmp_path, monkeypatch, *, show_machines_result=None, show_machines_raises=None):
        monkeypatch.setattr("vastai.cli.util.ROLE_FILE", str(tmp_path / "vast_role"))
        if show_machines_raises is not None:
            monkeypatch.setattr(
                "vastai.api.machines.show_machines",
                lambda client: (_ for _ in ()).throw(show_machines_raises),
            )
        else:
            monkeypatch.setattr(
                "vastai.api.machines.show_machines",
                lambda client: show_machines_result,
            )
        return object()  # stand-in "client"; show_machines is patched to ignore it

    def test_host_account_caches_host(self, tmp_path, monkeypatch):
        from vastai.cli.util import ensure_host_role_detected, get_role
        client = self._client(tmp_path, monkeypatch, show_machines_result=[{"id": 1}])
        ensure_host_role_detected(client)
        assert get_role() == "host"

    def test_client_account_caches_client(self, tmp_path, monkeypatch):
        # This is what brings a pre-existing install (key saved, role never
        # written) up to date: an empty machines list is a real answer, not
        # a "still unknown" — so it gets cached just like a host does.
        from vastai.cli.util import ensure_host_role_detected, get_role
        client = self._client(tmp_path, monkeypatch, show_machines_result=[])
        ensure_host_role_detected(client)
        assert get_role() == "client"

    def test_network_error_leaves_role_undetected(self, tmp_path, monkeypatch):
        from vastai.cli.util import ensure_host_role_detected, get_role
        client = self._client(tmp_path, monkeypatch, show_machines_raises=ConnectionError("offline"))
        ensure_host_role_detected(client)
        assert get_role() is None

    def test_already_resolved_role_is_not_rechecked(self, tmp_path, monkeypatch):
        from vastai.cli.util import ensure_host_role_detected, set_role_file, get_role
        monkeypatch.setattr("vastai.cli.util.ROLE_FILE", str(tmp_path / "vast_role"))
        set_role_file("client")
        called = []
        monkeypatch.setattr(
            "vastai.api.machines.show_machines",
            lambda client: called.append(True) or [{"id": 1}],
        )
        ensure_host_role_detected(object())
        assert called == []
        assert get_role() == "client"  # not flipped to host
