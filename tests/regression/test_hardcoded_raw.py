"""Hardcoded `if True:` instead of `if args.raw:` in three functions.

The bug: search__benchmarks, search__invoices, and search__templates have
`if True: # args.raw:` which means they always return raw data / print JSON
regardless of the --raw flag, bypassing display_table.

The fix: Replace `if True:` with `if args.raw:`.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import argparse
from unittest.mock import patch, MagicMock


def _make_args(raw=False):
    return argparse.Namespace(
        api_key="test", url="https://console.vast.ai",
        retry=3, raw=raw, explain=False, quiet=False,
        curl=False, query=[],
    )


@patch('vast.display_table')
@patch('vast.http_get')
def test_search_benchmarks_respects_raw_flag(mock_http_get, mock_display):
    """search__benchmarks calls display_table when raw=False."""
    from vast import search__benchmarks

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"id": 1, "score": 99}]
    mock_resp.raise_for_status = MagicMock()
    mock_http_get.return_value = mock_resp

    args = _make_args(raw=False)
    result = search__benchmarks(args)

    # When raw=False, function should call display_table (not return data)
    mock_display.assert_called_once()
    # Return value should be None (display_table handles output)
    assert result is None, f"Expected None when raw=False, got {result}"


@patch('vast.http_get')
def test_search_benchmarks_returns_data_when_raw(mock_http_get):
    """search__benchmarks returns data when raw=True."""
    from vast import search__benchmarks

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"id": 1, "score": 99}]
    mock_resp.raise_for_status = MagicMock()
    mock_http_get.return_value = mock_resp

    args = _make_args(raw=True)
    result = search__benchmarks(args)

    assert result is not None, "Expected data when raw=True"
    assert isinstance(result, list)
