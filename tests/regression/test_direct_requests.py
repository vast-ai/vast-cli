"""No direct requests.get/post calls outside http_* helpers.

The bug: Several functions used requests.get() or requests.post() directly,
bypassing the centralized http_* helpers that provide timeout, retry, and
error handling.

The fix: Convert all direct requests.get/post calls in CLI command functions
to use http_get/http_post. Only allowed exceptions are:
  - get_project_data(): module-level PyPI check, no args available
  - fetch_url_content(): utility function, no args available (dead code)
  - _get_gpu_names(): module-level GPU cache, no args available
  - http_request(): the low-level implementation that uses requests.Session
  - import statements and commented-out code
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import ast
import re


# Allowed locations for direct requests.get/post calls
ALLOWED_FUNCTIONS = {
    'get_project_data',   # Module-level PyPI check, no args
    'fetch_url_content',  # Utility function, no args (dead code)
    '_get_gpu_names',     # Module-level GPU cache, no args
    'http_request',       # Low-level implementation
}


def _get_vast_source():
    """Read the vast.py source file."""
    vast_path = os.path.join(os.path.dirname(__file__), '..', '..', 'vast.py')
    with open(vast_path, encoding='utf-8') as f:
        return f.read()


def test_no_direct_requests_get_in_command_functions():
    """No requests.get() calls exist in CLI command functions (outside allowed exceptions)."""
    source = _get_vast_source()
    tree = ast.parse(source)

    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func_name = node.name
            if func_name in ALLOWED_FUNCTIONS:
                continue

            # Walk the function body looking for requests.get( or requests.post(
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    func = child.func
                    # Match: requests.get(...) or requests.post(...)
                    if (isinstance(func, ast.Attribute) and
                            isinstance(func.value, ast.Name) and
                            func.value.id == 'requests' and
                            func.attr in ('get', 'post')):
                        violations.append(
                            f"  {func_name}() at line {child.lineno}: "
                            f"requests.{func.attr}()"
                        )

    assert not violations, (
        "Found direct requests.get/post calls in command functions "
        "(should use http_get/http_post):\n" + "\n".join(violations)
    )


def test_no_direct_requests_get_via_grep():
    """Grep-style check: no unprotected requests.get/post patterns in vast.py."""
    source = _get_vast_source()
    lines = source.split('\n')

    violations = []
    pattern = re.compile(r'(?<!#)\s*\w*\s*=?\s*requests\.(get|post)\(')

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith('#'):
            continue
        # Skip import lines
        if 'import requests' in stripped:
            continue

        match = pattern.search(line)
        if match:
            # Check if this is in an allowed context
            # We do a simple heuristic: look for function context
            # by scanning backwards for the nearest 'def ' line
            func_name = _find_enclosing_function(lines, i - 1)
            if func_name in ALLOWED_FUNCTIONS:
                continue
            if func_name is None:
                # Module level - check if it's in allowed module-level contexts
                continue

            violations.append(f"  Line {i} (in {func_name}): {stripped}")

    assert not violations, (
        "Found direct requests.get/post calls outside allowed functions:\n"
        + "\n".join(violations)
    )


def _find_enclosing_function(lines, line_idx):
    """Find the name of the outermost function containing the given line index.

    Handles nested functions by tracking indentation: returns the function
    definition with the smallest indentation (outermost enclosing function).
    """
    best_name = None
    best_indent = float('inf')
    for i in range(line_idx, -1, -1):
        stripped = lines[i].lstrip()
        if stripped.startswith('def '):
            indent = len(lines[i]) - len(stripped)
            match = re.match(r'def\s+(\w+)\s*\(', stripped)
            if match and indent < best_indent:
                best_name = match.group(1)
                best_indent = indent
                if indent == 0:
                    break  # Top-level function, can't go higher
    return best_name


def test_allowed_exceptions_have_timeout():
    """Allowed direct requests calls (get_project_data, _get_gpu_names) have timeout."""
    source = _get_vast_source()
    lines = source.split('\n')

    # Find direct requests.get calls and verify they have timeout
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        if 'requests.get(' in stripped and 'import' not in stripped:
            func_name = _find_enclosing_function(lines, i - 1)
            if func_name in ALLOWED_FUNCTIONS or func_name is None:
                assert 'timeout' in stripped, (
                    f"Line {i} (in {func_name or 'module-level'}): "
                    f"direct requests.get() missing timeout parameter: {stripped}"
                )
