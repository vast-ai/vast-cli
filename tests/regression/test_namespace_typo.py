"""Typo 'debbuging' in Namespace construction.

The bug: destroy_args = argparse.Namespace(..., debbuging=args.debugging, ...)
creates an attribute 'debbuging' instead of 'debugging'. Any code accessing
destroy_args.debugging gets AttributeError.

The fix: Change 'debbuging' to 'debugging'.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def test_no_debbuging_typo_in_source():
    """Verify the typo 'debbuging' does not appear in vast.py source."""
    vast_path = os.path.join(os.path.dirname(__file__), '..', '..', 'vast.py')
    with open(vast_path, 'r', encoding='utf-8', errors='replace') as f:
        source = f.read()

    assert 'debbuging' not in source, (
        "Found 'debbuging' typo in vast.py. "
        "Should be 'debugging' in the Namespace construction."
    )
