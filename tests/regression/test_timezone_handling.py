"""Timezone handling uses time.mktime() which interprets as local time.

The bug: time.mktime() converts a time tuple to epoch using the LOCAL timezone.
For a user in PST (UTC-8), a date "01/15/2025" would produce an epoch value
that's 8 hours later than UTC midnight, giving wrong results.

The fix: Use calendar.timegm() which always interprets the time tuple as UTC.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import calendar


def test_string_to_unix_epoch_utc():
    """string_to_unix_epoch returns UTC timestamps regardless of local timezone."""
    from vast import string_to_unix_epoch

    # 01/15/2025 00:00:00 UTC = 1736899200
    result = string_to_unix_epoch("01/15/2025")
    expected = calendar.timegm((2025, 1, 15, 0, 0, 0, 0, 0, 0))
    assert expected == 1736899200, f"Sanity check: expected 1736899200, got {expected}"
    assert result == expected, (
        f"string_to_unix_epoch('01/15/2025') returned {result}, expected {expected}. "
        f"This likely means time.mktime() is still being used instead of calendar.timegm()."
    )


def test_string_to_unix_epoch_returns_float_passthrough():
    """string_to_unix_epoch returns float values as-is."""
    from vast import string_to_unix_epoch

    assert string_to_unix_epoch("1736899200") == 1736899200.0


def test_string_to_unix_epoch_none():
    """string_to_unix_epoch returns None for None input."""
    from vast import string_to_unix_epoch

    assert string_to_unix_epoch(None) is None
