"""Mutable default arguments in http_put, http_post, http_del.

The bug: Using json={} as a default argument means all calls share the same
dict object. If any caller mutates the dict, subsequent calls see the mutation.

The fix: Use json=None and initialize to {} at runtime.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from unittest.mock import MagicMock, patch
import argparse


def _make_args():
    return argparse.Namespace(retry=1, curl=False)


def _mock_http_request(verb, args, req_url, headers, json, **kwargs):
    """Capture the json arg and return a mock response."""
    r = MagicMock()
    r.status_code = 200
    # Store reference to the json dict that was passed
    r._captured_json = json
    return r


@patch('vast.http_request', side_effect=_mock_http_request)
def test_http_put_no_shared_default(mock_req):
    from vast import http_put
    args = _make_args()
    r1 = http_put(args, "http://test1", headers=None)
    r2 = http_put(args, "http://test2", headers=None)
    # Each call must get its own dict, not share the mutable default
    assert r1._captured_json is not r2._captured_json


@patch('vast.http_request', side_effect=_mock_http_request)
def test_http_post_no_shared_default(mock_req):
    from vast import http_post
    args = _make_args()
    r1 = http_post(args, "http://test1", headers=None)
    r2 = http_post(args, "http://test2", headers=None)
    assert r1._captured_json is not r2._captured_json


@patch('vast.http_request', side_effect=_mock_http_request)
def test_http_del_no_shared_default(mock_req):
    from vast import http_del
    args = _make_args()
    r1 = http_del(args, "http://test1", headers=None)
    r2 = http_del(args, "http://test2", headers=None)
    assert r1._captured_json is not r2._captured_json
