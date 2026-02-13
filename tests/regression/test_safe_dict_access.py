"""Safe dict access on API response dicts.

The bug: 60+ locations accessed API response dicts with rj["key"],
r.json()["key"], or result["key"] which raises KeyError if the API
response format changes or an endpoint returns unexpected data.

The fix: Convert all API response dict accesses to .get() with
appropriate defaults:
  - Boolean checks: rj.get("success") -- None is falsy
  - Messages: rj.get("msg", "Unknown error") -- fallback text
  - Iterable data: rj.get("offers", []) -- empty list for iteration
  - Required fields: rj.get("result_url") with explicit error check
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import re
import argparse
import pytest
from unittest.mock import MagicMock, patch

VAST_PY_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'vast.py')


# --------------------------------------------------------------------------- #
# Lint-style tests #
# --------------------------------------------------------------------------- #

class TestMinimalRawDictAccess:
    """Ensure almost no raw rj['key'] access patterns remain on API data."""

    def test_minimal_rj_bracket_access(self):
        """Count rj["..."] patterns -- should be zero after the fix."""
        with open(VAST_PY_PATH, encoding='utf-8') as f:
            content = f.read()
        raw_accesses = re.findall(r'rj\["[^"]+"\]', content)
        assert len(raw_accesses) == 0, (
            f"Found {len(raw_accesses)} raw rj[\"key\"] accesses; "
            f"expected 0. Convert to rj.get('key', default). "
            f"Matches: {raw_accesses[:5]}"
        )

    def test_minimal_rj_single_quote_access(self):
        """Count rj['...'] patterns -- should be zero after the fix."""
        with open(VAST_PY_PATH, encoding='utf-8') as f:
            content = f.read()
        raw_accesses = re.findall(r"rj\['[^']+'\]", content)
        assert len(raw_accesses) == 0, (
            f"Found {len(raw_accesses)} raw rj['key'] accesses; "
            f"expected 0. Convert to rj.get('key', default). "
            f"Matches: {raw_accesses[:5]}"
        )

    def test_minimal_r_json_bracket_access(self):
        """Count r.json()["..."] patterns (excluding comments)."""
        with open(VAST_PY_PATH, encoding='utf-8') as f:
            lines = f.readlines()
        raw_accesses = []
        for i, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if stripped.startswith('#'):
                continue
            matches = re.findall(r'\.json\(\)\["[^"]+"\]', line)
            for m in matches:
                raw_accesses.append(f"line {i}: {m}")
        assert len(raw_accesses) == 0, (
            f"Found {len(raw_accesses)} raw .json()[\"key\"] accesses in "
            f"non-comment lines; expected 0. Matches: {raw_accesses[:5]}"
        )

    def test_high_safe_access_count(self):
        """Verify a high number of .get() patterns exist."""
        with open(VAST_PY_PATH, encoding='utf-8') as f:
            content = f.read()
        rj_gets = len(re.findall(r'rj\.get\(', content))
        json_gets = len(re.findall(r'\.json\(\)\.get\(', content))
        result_gets = len(re.findall(r'result\.get\(', content))
        total = rj_gets + json_gets + result_gets
        assert total >= 60, (
            f"Found only {total} safe .get() accesses on API response dicts "
            f"(rj.get: {rj_gets}, .json().get: {json_gets}, result.get: {result_gets}); "
            f"expected >= 60 after safe dict access conversion."
        )


# --------------------------------------------------------------------------- #
# Functional tests: missing "success" key #
# --------------------------------------------------------------------------- #

class TestMissingSuccessKey:
    """Verify functions handle missing 'success' key without KeyError."""

    @patch('vast.http_put')
    def test_prepay_instance_no_success_key(self, mock_put, capsys):
        """prepay__instance should not crash if 'success' key is missing."""
        import vast

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        # API returns dict WITHOUT 'success' key
        mock_response.json.return_value = {"some_other_field": 123}
        mock_put.return_value = mock_response

        args = argparse.Namespace(
            api_key="test-key", url="https://console.vast.ai",
            retry=3, raw=False, explain=False,
            id=12345, amount=10.0
        )

        # Should not raise KeyError
        vast.prepay__instance(args)

        captured = capsys.readouterr()
        # Since success is missing (falsy), it should print the error branch
        assert "Unknown error" in captured.out

    @patch('vast.api_call')
    def test_label_instance_no_success_key(self, mock_api_call, capsys):
        """label__instance should not crash if 'success' key is missing."""
        import vast

        # api_call returns a dict without 'success' key
        mock_api_call.return_value = {"some_other_field": 123}

        args = argparse.Namespace(
            api_key="test-key", url="https://console.vast.ai",
            retry=3, raw=False, explain=False,
            id=12345, label="test-label"
        )

        # Should not raise KeyError
        vast.label__instance(args)

        captured = capsys.readouterr()
        # Since success is missing (falsy), it should print the error branch
        assert "Unknown error" in captured.out


# --------------------------------------------------------------------------- #
# Functional tests: missing "msg" key #
# --------------------------------------------------------------------------- #

class TestMissingMsgKey:
    """Verify functions handle missing 'msg' key by printing fallback."""

    @patch('vast.http_put')
    def test_prepay_failure_no_msg(self, mock_put, capsys):
        """When API returns success=False without msg, print 'Unknown error'."""
        import vast

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"success": False}
        mock_put.return_value = mock_response

        args = argparse.Namespace(
            api_key="test-key", url="https://console.vast.ai",
            retry=3, raw=False, explain=False,
            id=999, amount=5.0
        )

        vast.prepay__instance(args)

        captured = capsys.readouterr()
        assert "Unknown error" in captured.out

    @patch('vast.http_post')
    def test_create_overlay_no_msg(self, mock_post, capsys):
        """create__overlay should print 'Unknown error' when msg key missing."""
        import vast

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": "ok"}  # no "msg" key
        mock_post.return_value = mock_response

        args = argparse.Namespace(
            api_key="test-key", url="https://console.vast.ai",
            retry=3, raw=False, explain=False,
            name="test-overlay", cluster_id=123
        )

        vast.create__overlay(args)

        captured = capsys.readouterr()
        assert "Unknown error" in captured.out


# --------------------------------------------------------------------------- #
# Functional tests: missing data extraction keys #
# --------------------------------------------------------------------------- #

class TestMissingDataKeys:
    """Verify functions handle missing data keys gracefully."""

    @patch('vast.http_get')
    def test_show_instances_missing_instances_key(self, mock_get, capsys):
        """show__instances should handle missing 'instances' key without crash."""
        import vast

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"success": True}  # no "instances"
        mock_get.return_value = mock_response

        args = argparse.Namespace(
            api_key="test-key", url="https://console.vast.ai",
            retry=3, raw=True, explain=False,
            quiet=False
        )

        # Should return empty list, not KeyError
        result = vast.show__instances(args)
        assert result == []

    @patch('vast.api_call')
    def test_show_volumes_missing_volumes_key(self, mock_api_call, capsys):
        """show__volumes should handle missing 'volumes' key without crash."""
        import vast

        # api_call returns a dict without 'volumes' key
        mock_api_call.return_value = {"success": True}

        args = argparse.Namespace(
            api_key="test-key", url="https://console.vast.ai",
            retry=3, raw=True, explain=False,
            quiet=False, type="all"
        )

        # Should return empty list, not KeyError
        result = vast.show__volumes(args)
        assert result == [] or result is None
