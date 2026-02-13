"""22 functions return Response object instead of parsed JSON.

The bug: Functions using http_* directly return `r` (Response object) in raw
mode. Response objects are not JSON-serializable, causing json.dumps to fail.
The bare except: in main() masks this by calling res.json() as a fallback.

The fix: Change `return r` to `return r.json()` in all 22 functions.
Also: Remove bare except in main() since all returns are now serializable.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import re


def test_no_bare_return_r_in_functions():
    """No function (except http_request) returns bare `r` (Response object)."""
    vast_path = os.path.join(os.path.dirname(__file__), '..', '..', 'vast.py')
    with open(vast_path, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    # Find all 'return r' lines outside http_request
    in_http_request = False
    violations = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('def http_request('):
            in_http_request = True
        elif stripped.startswith('def ') and in_http_request:
            in_http_request = False

        if in_http_request:
            continue

        # Match 'return r' but not 'return rows', 'return r.json()', etc.
        if re.match(r'\s+return r\s*$', line):
            violations.append(f"Line {i}: {stripped}")

    assert not violations, (
        f"Found {len(violations)} function(s) still returning bare Response object:\n"
        + "\n".join(violations)
    )


def test_no_bare_except_in_main():
    """main() should not have a bare except: clause for raw output."""
    vast_path = os.path.join(os.path.dirname(__file__), '..', '..', 'vast.py')
    with open(vast_path, 'r', encoding='utf-8', errors='replace') as f:
        source = f.read()

    # Check that res.json() fallback is gone from main's raw handler
    # The old pattern was: try: json.dumps(res) except: json.dumps(res.json())
    # After fix: just json.dumps(res) with no try/except
    assert 'res.json()' not in source, (
        "Found res.json() fallback in main(). "
        "All returns are JSON-serializable and the fallback is dead code."
    )
