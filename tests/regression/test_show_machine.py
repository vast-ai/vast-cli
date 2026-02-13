"""show__machine() doesn't handle single dict response.

The bug: api_call returns a dict for single-machine queries. The code
iterates `for row in rows` which iterates over dict KEYS (strings like 'id',
'gpu_name') instead of dicts. display_table also expects a list of dicts.

The fix: Wrap single dict responses in a list.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import argparse
from unittest.mock import patch, MagicMock


def test_single_dict_response_handled():
    """show__machine wraps a single dict response in a list."""
    from vast import show__machine

    single_machine = {
        "id": 42,
        "gpu_name": "RTX 4090",
        "num_gpus": 1,
    }

    args = argparse.Namespace(
        api_key="test", url="https://console.vast.ai",
        retry=3, raw=True, explain=False, quiet=False,
        curl=False, id=42,
    )

    with patch('vast.api_call', return_value=single_machine):
        result = show__machine(args)

    # In raw mode, should return a list (wrapped dict)
    assert isinstance(result, list), f"Expected list, got {type(result)}"
    assert len(result) == 1
    assert result[0]['id'] == 42


def test_list_response_unchanged():
    """show__machine leaves list responses as-is."""
    from vast import show__machine

    machine_list = [{"id": 42, "gpu_name": "RTX 4090"}]

    args = argparse.Namespace(
        api_key="test", url="https://console.vast.ai",
        retry=3, raw=True, explain=False, quiet=False,
        curl=False, id=42,
    )

    with patch('vast.api_call', return_value=machine_list):
        result = show__machine(args)

    assert isinstance(result, list)
    assert len(result) == 1
