"""show__instances() loop rebinds local variable without updating list.

The bug: `for row in rows: row = {...}` rebinds the local `row` variable to a
new dict, but the original dict in `rows` is unchanged. The stripped strings
and computed duration are lost.

The fix: Build a new list and reassign rows.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import argparse
import time
from unittest.mock import MagicMock, patch


def test_rows_are_modified_after_loop():
    """After show__instances processes rows, the returned rows have modified data."""
    from vast import show__instances

    mock_instances = [
        {
            "id": 12345,
            "start_date": time.time() - 3600,  # started 1 hour ago
            "extra_env": [["KEY1", "val1"], ["KEY2", "val2"]],
            "status": "running",
            "name": "  test  ",  # has leading/trailing spaces
        }
    ]

    mock_response = MagicMock()
    mock_response.json.return_value = {"instances": mock_instances}
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    args = argparse.Namespace(
        api_key="test", url="https://console.vast.ai",
        retry=3, raw=True, explain=False, quiet=False,
        curl=False, full=False,
    )

    with patch('vast.apiurl', return_value="https://console.vast.ai/api/v0/instances"), \
         patch('vast.http_get', return_value=mock_response):
        result = show__instances(args, extra={})

    # In raw mode, show__instances returns rows
    assert result is not None, "show__instances returned None in raw mode"
    assert len(result) > 0, "show__instances returned empty list"
    row = result[0]
    # The row should have 'duration' field computed from the loop
    assert 'duration' in row, "Row missing 'duration' -- loop rebinding bug still present"
    assert row['duration'] > 0, f"Duration should be positive, got {row['duration']}"
    # extra_env should be converted from list-of-pairs to dict
    assert isinstance(row['extra_env'], dict), "extra_env not converted to dict"
    assert row['extra_env'].get('KEY1') == 'val1'


def test_rows_stripped_strings_preserved():
    """Verify strip_strings is applied and preserved in the returned rows."""
    from vast import show__instances

    mock_instances = [
        {
            "id": 99,
            "start_date": time.time() - 100,
            "extra_env": [],
            "status": "  running  ",
        }
    ]

    mock_response = MagicMock()
    mock_response.json.return_value = {"instances": mock_instances}
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    args = argparse.Namespace(
        api_key="test", url="https://console.vast.ai",
        retry=3, raw=True, explain=False, quiet=False,
        curl=False, full=False,
    )

    with patch('vast.apiurl', return_value="https://console.vast.ai/api/v0/instances"), \
         patch('vast.http_get', return_value=mock_response):
        result = show__instances(args, extra={})

    assert result is not None
    row = result[0]
    # strip_strings should have trimmed the status value
    assert row['status'] == 'running', f"Expected 'running', got '{row['status']}' -- strip not applied"
