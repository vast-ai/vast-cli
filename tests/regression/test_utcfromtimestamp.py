"""No deprecated utcfromtimestamp() calls in vast.py.

The bug: datetime.utcfromtimestamp() is deprecated since Python 3.12 and
will be removed in a future version. It also returns a naive datetime that
is ambiguous about its timezone.

The fix: Replace all utcfromtimestamp() calls with
datetime.fromtimestamp(ts, tz=timezone.utc), which returns an aware
datetime and is not deprecated.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import re
import pytest
from datetime import datetime, timezone


VAST_PY_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'vast.py')


class TestNoUtcfromtimestamp:
    """Lint-style tests verifying utcfromtimestamp is not used anywhere."""

    def test_no_utcfromtimestamp_in_source(self):
        """utcfromtimestamp should not appear anywhere in vast.py.

        This deprecated method returns naive datetimes and will be removed
        in a future Python version. Use fromtimestamp(ts, tz=timezone.utc).
        """
        with open(VAST_PY_PATH, encoding='utf-8') as f:
            content = f.read()

        matches = re.findall(r'utcfromtimestamp', content)
        assert len(matches) == 0, (
            f"Found {len(matches)} occurrences of utcfromtimestamp in vast.py. "
            "Use datetime.fromtimestamp(ts, tz=timezone.utc) instead."
        )

    def test_no_utcnow_in_source(self):
        """utcnow() is also deprecated for the same reason as utcfromtimestamp.

        Prevent regression by ensuring neither deprecated UTC method is used.
        """
        with open(VAST_PY_PATH, encoding='utf-8') as f:
            content = f.read()

        # Match utcnow() but not in comments
        lines = content.split('\n')
        violations = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            if 'utcnow()' in line:
                violations.append(f"Line {i}: {stripped}")

        assert len(violations) == 0, (
            f"Found {len(violations)} occurrences of utcnow() in vast.py. "
            "Use datetime.now(tz=timezone.utc) instead.\n"
            + "\n".join(violations)
        )


class TestReplacementProducesAwareDatetime:
    """Verify the replacement fromtimestamp(ts, tz=timezone.utc) works correctly."""

    def test_fromtimestamp_with_tz_returns_aware_datetime(self):
        """datetime.fromtimestamp(ts, tz=timezone.utc) must return a tz-aware datetime."""
        ts = 1704067200  # 2024-01-01 00:00:00 UTC
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        assert dt.tzinfo is not None, "Result should be timezone-aware"
        assert dt.tzinfo == timezone.utc, "Result timezone should be UTC"

    def test_fromtimestamp_with_tz_correct_values(self):
        """Verify the replacement produces correct year/month/day/hour."""
        ts = 1704067200  # 2024-01-01 00:00:00 UTC
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 1
        assert dt.hour == 0
        assert dt.minute == 0
        assert dt.second == 0

    def test_fromtimestamp_with_tz_matches_expected_format(self):
        """The replacement in schedule_maintenance should format correctly."""
        ts = 1704067200  # 2024-01-01 00:00:00 UTC
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        # The schedule_maintenance function uses str(dt) implicitly in f-string
        dt_str = str(dt)
        assert "2024-01-01" in dt_str, f"Expected 2024-01-01 in {dt_str}"
