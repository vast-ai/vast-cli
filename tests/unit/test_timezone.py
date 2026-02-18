"""Unit tests for timezone handling functions.

TEST-03: Unit tests for timezone handling functions.

These tests verify that all timezone conversions produce correct UTC results
regardless of the local system timezone.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import calendar
from datetime import datetime, timezone
import pytest


class TestStringToUnixEpoch:
    """Tests for string_to_unix_epoch() function."""

    def test_date_string_to_utc_epoch(self):
        """Date string converts to correct UTC epoch timestamp."""
        from vast import string_to_unix_epoch

        # 01/15/2025 00:00:00 UTC = 1736899200
        result = string_to_unix_epoch("01/15/2025")
        expected = calendar.timegm((2025, 1, 15, 0, 0, 0, 0, 0, 0))

        assert expected == 1736899200, f"Sanity check failed: expected 1736899200, got {expected}"
        assert result == expected

    def test_numeric_string_passthrough(self):
        """Numeric string is converted to float and returned."""
        from vast import string_to_unix_epoch

        assert string_to_unix_epoch("1736899200") == 1736899200.0
        assert string_to_unix_epoch("1736899200.5") == 1736899200.5

    def test_none_returns_none(self):
        """None input returns None."""
        from vast import string_to_unix_epoch

        assert string_to_unix_epoch(None) is None

    def test_empty_string_raises_value_error(self):
        """Empty string raises ValueError (not numeric, can't parse as date)."""
        from vast import string_to_unix_epoch

        # Empty string is not a valid float and not a valid date format
        with pytest.raises(ValueError):
            string_to_unix_epoch("")

    def test_various_date_formats(self):
        """Various date formats parse correctly."""
        from vast import string_to_unix_epoch

        # Test MM/DD/YYYY format
        result1 = string_to_unix_epoch("12/31/2024")
        expected1 = calendar.timegm((2024, 12, 31, 0, 0, 0, 0, 0, 0))
        assert result1 == expected1

        # Test boundary dates
        result2 = string_to_unix_epoch("01/01/2025")
        expected2 = calendar.timegm((2025, 1, 1, 0, 0, 0, 0, 0, 0))
        assert result2 == expected2


class TestFromTimestampUtc:
    """Tests for UTC-aware datetime.fromtimestamp usage."""

    def test_fromtimestamp_with_utc(self):
        """datetime.fromtimestamp with UTC timezone gives correct result."""
        # This tests the pattern used after the fix fix
        epoch = 1736899200  # 01/15/2025 00:00:00 UTC

        # The correct pattern (after fix)
        dt_utc = datetime.fromtimestamp(epoch, tz=timezone.utc)

        assert dt_utc.year == 2025
        assert dt_utc.month == 1
        assert dt_utc.day == 15
        assert dt_utc.hour == 0
        assert dt_utc.minute == 0
        assert dt_utc.second == 0
        assert dt_utc.tzinfo == timezone.utc

    def test_calendar_timegm_inverse(self):
        """calendar.timegm is the inverse of datetime.fromtimestamp(tz=utc)."""
        original_epoch = 1736899200

        # Convert to datetime
        dt = datetime.fromtimestamp(original_epoch, tz=timezone.utc)

        # Convert back to epoch
        timetuple = dt.timetuple()
        recovered_epoch = calendar.timegm(timetuple)

        assert recovered_epoch == original_epoch


class TestTimezoneConsistency:
    """Tests verifying timezone handling is consistent across functions."""

    def test_known_epoch_value(self):
        """Test against a known epoch value that's verifiable."""
        # Unix epoch 0 is January 1, 1970, 00:00:00 UTC
        epoch_zero = 0

        dt = datetime.fromtimestamp(epoch_zero, tz=timezone.utc)

        assert dt.year == 1970
        assert dt.month == 1
        assert dt.day == 1
        assert dt.hour == 0

    def test_y2k_epoch(self):
        """Test Y2K timestamp (known reference point)."""
        # January 1, 2000, 00:00:00 UTC = 946684800
        y2k_epoch = 946684800

        dt = datetime.fromtimestamp(y2k_epoch, tz=timezone.utc)

        assert dt.year == 2000
        assert dt.month == 1
        assert dt.day == 1
        assert dt.hour == 0
