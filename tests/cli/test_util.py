"""Tests for vastai/cli/util.py — parse_env, parse_vast_url, validate_seconds, etc."""

import argparse
import errno
import os
import stat

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock


class TestWriteSecretFile:
    @pytest.mark.skipif(os.name == "nt", reason="POSIX file mode test")
    def test_atomically_replaces_file_with_owner_only_permissions(self, tmp_path):
        from vastai.cli.util import write_secret_file

        secret_file = tmp_path / "secret"
        secret_file.write_bytes(b"old-secret")
        secret_file.chmod(0o644)
        old_inode = secret_file.stat().st_ino

        old_umask = os.umask(0o022)
        try:
            write_secret_file(secret_file, "new-secret")
        finally:
            os.umask(old_umask)

        assert secret_file.read_bytes() == b"new-secret"
        assert stat.S_IMODE(secret_file.stat().st_mode) == 0o600
        assert secret_file.stat().st_ino != old_inode

    def test_no_clobber_publish_preserves_existing_file(self, tmp_path):
        from vastai.cli.util import write_secret_file

        secret_file = tmp_path / "secret"
        secret_file.write_bytes(b"existing-secret")

        with pytest.raises(FileExistsError):
            write_secret_file(secret_file, b"new-secret", overwrite=False)

        assert secret_file.read_bytes() == b"existing-secret"
        assert list(tmp_path.iterdir()) == [secret_file]

    def test_no_clobber_falls_back_when_hard_links_are_unsupported(
        self, tmp_path, monkeypatch
    ):
        from vastai.cli import util

        secret_file = tmp_path / "secret"
        monkeypatch.setattr(
            util.os,
            "link",
            Mock(side_effect=OSError(errno.EPERM, "hard links unsupported")),
        )

        util.write_secret_file(secret_file, b"secret", overwrite=False)

        assert secret_file.read_bytes() == b"secret"
        assert list(tmp_path.iterdir()) == [secret_file]

    def test_removes_temporary_file_after_replace_failure(self, tmp_path, monkeypatch):
        from vastai.cli import util

        secret_file = tmp_path / "secret"
        monkeypatch.setattr(util.os, "replace", Mock(side_effect=OSError("replace failed")))

        with pytest.raises(OSError, match="replace failed"):
            util.write_secret_file(secret_file, "secret")

        assert list(tmp_path.iterdir()) == []


class TestLegacyApiKeyMigration:
    def test_migrates_and_removes_legacy_file(self, tmp_path, monkeypatch):
        from vastai.cli import util

        legacy_file = tmp_path / ".vast_api_key"
        key_file = tmp_path / "vast_api_key"
        legacy_file.write_bytes(b"legacy-key")
        monkeypatch.setattr(util, "APIKEY_FILE_HOME", str(legacy_file))
        monkeypatch.setattr(util, "APIKEY_FILE", str(key_file))

        util._migrate_legacy_api_key()

        assert key_file.read_bytes() == b"legacy-key"
        assert not legacy_file.exists()

    @pytest.mark.skipif(os.name == "nt", reason="POSIX file mode test")
    def test_migrates_with_owner_only_permissions(self, tmp_path, monkeypatch):
        from vastai.cli import util

        legacy_file = tmp_path / ".vast_api_key"
        key_file = tmp_path / "vast_api_key"
        legacy_file.write_bytes(b"legacy-key")
        legacy_file.chmod(0o644)
        monkeypatch.setattr(util, "APIKEY_FILE_HOME", str(legacy_file))
        monkeypatch.setattr(util, "APIKEY_FILE", str(key_file))

        old_umask = os.umask(0o022)
        try:
            util._migrate_legacy_api_key()
        finally:
            os.umask(old_umask)

        assert stat.S_IMODE(key_file.stat().st_mode) == 0o600

    def test_race_does_not_overwrite_new_api_key(self, tmp_path, monkeypatch):
        from vastai.cli import util

        legacy_file = tmp_path / ".vast_api_key"
        key_file = tmp_path / "vast_api_key"
        legacy_file.write_bytes(b"legacy-key")
        monkeypatch.setattr(util, "APIKEY_FILE_HOME", str(legacy_file))
        monkeypatch.setattr(util, "APIKEY_FILE", str(key_file))
        original_write_secret_file = util.write_secret_file

        def create_new_key_before_publish(path, secret, *, overwrite=True):
            key_file.write_bytes(b"new-key")
            return original_write_secret_file(path, secret, overwrite=overwrite)

        monkeypatch.setattr(util, "write_secret_file", create_new_key_before_publish)

        util._migrate_legacy_api_key()

        assert key_file.read_bytes() == b"new-key"
        assert legacy_file.read_bytes() == b"legacy-key"


class TestExistingCredentialPermissions:
    @pytest.mark.skipif(os.name == "nt", reason="POSIX file mode test")
    def test_secures_current_and_legacy_credentials(self, tmp_path, monkeypatch):
        from vastai.cli import util

        credential_files = [
            tmp_path / "vast_api_key",
            tmp_path / "vast_tfa_key",
            tmp_path / ".vast_api_key",
        ]
        for credential_file in credential_files:
            credential_file.write_bytes(b"secret")
            credential_file.chmod(0o644)

        monkeypatch.setattr(util, "APIKEY_FILE", str(credential_files[0]))
        monkeypatch.setattr(util, "TFAKEY_FILE", str(credential_files[1]))
        monkeypatch.setattr(util, "APIKEY_FILE_HOME", str(credential_files[2]))

        util._secure_existing_credentials()

        assert all(
            stat.S_IMODE(credential_file.stat().st_mode) == 0o600
            for credential_file in credential_files
        )

    @pytest.mark.skipif(os.name == "nt", reason="POSIX file mode test")
    def test_does_not_follow_symlinks(self, tmp_path):
        from vastai.cli.util import secure_existing_secret_file

        target = tmp_path / "target"
        link = tmp_path / "secret"
        target.write_bytes(b"not-a-credential")
        target.chmod(0o644)
        link.symlink_to(target)

        secure_existing_secret_file(link)

        assert stat.S_IMODE(target.stat().st_mode) == 0o644


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
