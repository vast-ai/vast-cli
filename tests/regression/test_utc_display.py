"""UTC-labeled timestamps must actually display UTC.

The bug: datetime.fromtimestamp(ts) without tz= returns LOCAL time, but
the columns are labeled "UTC" or the output is treated as UTC. Users in
non-UTC timezones see wrong times.

The fix: All fromtimestamp() calls that produce UTC-labeled output now
pass tz=timezone.utc explicitly.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import re
import pytest
from datetime import datetime, timezone


VAST_PY_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'vast.py')


class TestUnixToReadableUTC:
    """Verify unix_to_readable() produces UTC output."""

    def test_known_epoch_returns_utc_midnight(self):
        """1704067200 is 2024-01-01 00:00:00 UTC. Output must show 00:00:00."""
        from vast import unix_to_readable
        result = unix_to_readable(1704067200)
        assert "00:00:00" in result, (
            f"unix_to_readable(1704067200) should show 00:00:00 UTC, got: {result}"
        )

    def test_known_epoch_returns_correct_date(self):
        """1704067200 is 2024-01-01 UTC. Output must contain Jan-01-2024."""
        from vast import unix_to_readable
        result = unix_to_readable(1704067200)
        assert "Jan-01-2024" in result, (
            f"unix_to_readable(1704067200) should contain Jan-01-2024, got: {result}"
        )

    def test_midday_epoch_shows_utc_time(self):
        """1704110400 is 2024-01-01 12:00:00 UTC. Output must show 12:00:00."""
        from vast import unix_to_readable
        result = unix_to_readable(1704110400)
        assert "12:00:00" in result, (
            f"unix_to_readable(1704110400) should show 12:00:00 UTC, got: {result}"
        )


class TestFromtimestampCallsUseUTC:
    """Lint-style test: every fromtimestamp() call must use tz=timezone.utc."""

    def test_all_fromtimestamp_calls_have_tz_utc(self):
        """Every fromtimestamp( call in vast.py should include tz=timezone.utc.

        This prevents regressions where a new fromtimestamp() call is added
        without the timezone parameter, silently producing local time.
        """
        with open(VAST_PY_PATH, encoding='utf-8') as f:
            lines = f.readlines()

        violations = []
        for i, line in enumerate(lines, 1):
            # Skip comments
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            # Find fromtimestamp( calls
            if 'fromtimestamp(' in line and 'utcfromtimestamp' not in line:
                if 'tz=timezone.utc' not in line:
                    violations.append(f"Line {i}: {stripped}")

        assert len(violations) == 0, (
            f"Found {len(violations)} fromtimestamp() calls without tz=timezone.utc:\n"
            + "\n".join(violations)
        )


class TestCacheAgeUsesAwareDatetimes:
    """Verify cache age calculation uses timezone-aware datetimes on both sides."""

    def test_cache_age_uses_tz_aware_now(self):
        """datetime.now() in cache age must use tz=timezone.utc."""
        with open(VAST_PY_PATH, encoding='utf-8') as f:
            content = f.read()

        # Find the cache_age line
        match = re.search(r'cache_age\s*=\s*(.+)', content)
        assert match is not None, "cache_age assignment not found in vast.py"

        cache_age_line = match.group(1)
        assert 'datetime.now(tz=timezone.utc)' in cache_age_line, (
            f"cache_age should use datetime.now(tz=timezone.utc), got: {cache_age_line}"
        )
        assert 'fromtimestamp(' in cache_age_line and 'tz=timezone.utc' in cache_age_line, (
            f"cache_age should use fromtimestamp with tz=timezone.utc, got: {cache_age_line}"
        )
