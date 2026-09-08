"""Benchmarks pagination: the flat-list helper pages, the v1 helper does not."""

from unittest.mock import patch

from vastai.api import offers
from vastai.sdk import VastAI


class _FakeResp:
    def __init__(self, rows, token=None):
        self._rows = rows
        self._token = token

    def raise_for_status(self):
        pass

    def json(self):
        return {"success": True, "benchmarks_found": len(self._rows),
                "benchmarks": self._rows, "next_token": self._token}


class _FakeClient:
    """Two pages: the first carries a token, the second does not."""

    def __init__(self):
        self.calls = []

    def get(self, subpath, query_args=None):
        # Copy: the pager reuses one params dict across pages.
        self.calls.append(dict(query_args or {}))
        if (query_args or {}).get("after_token"):
            return _FakeResp([{"id": 3}])
        return _FakeResp([{"id": 1}, {"id": 2}], token="TOK")


def sdk_with(client):
    with patch("vastai.sdk.VastClient"):
        v = VastAI(api_key="test-key")
    v.client = client
    return v


def test_v1_returns_one_page_with_token():
    client = _FakeClient()
    data = offers.search_benchmarks_v1(client, {"select_filters": {}})

    assert [r["id"] for r in data["benchmarks"]] == [1, 2]
    assert data["next_token"] == "TOK"
    assert len(client.calls) == 1


def test_search_benchmarks_follows_next_token():
    client = _FakeClient()
    rows = offers.search_benchmarks(client, query={"type": {"eq": "perf"}})

    # Every row across both pages, in order.
    assert [r["id"] for r in rows] == [1, 2, 3]
    # Two requests: the second echoes the token from the first page.
    assert len(client.calls) == 2
    assert "after_token" not in client.calls[0]
    assert client.calls[1]["after_token"] == "TOK"


def test_search_benchmarks_resumes_from_token():
    client = _FakeClient()
    rows = offers.search_benchmarks(client, after_token="TOK")
    assert [r["id"] for r in rows] == [3]


def test_omits_limit_when_unset():
    assert "limit" not in offers.benchmarks_query_args()


def test_forwards_limit():
    assert offers.benchmarks_query_args(limit=100)["limit"] == 100


def test_sdk_returns_a_single_page_by_default():
    """A broad query must not scan the whole table unless the caller asks."""
    client = _FakeClient()
    rows = sdk_with(client).search_benchmarks(query={"type": {"eq": "perf"}})

    assert [r["id"] for r in rows] == [1, 2]
    assert len(client.calls) == 1


def test_sdk_all_pages_fetches_everything():
    client = _FakeClient()
    rows = sdk_with(client).search_benchmarks(all_pages=True)

    assert [r["id"] for r in rows] == [1, 2, 3]
    assert len(client.calls) == 2


def test_sdk_resumes_from_token():
    client = _FakeClient()
    rows = sdk_with(client).search_benchmarks(after_token="TOK")

    assert [r["id"] for r in rows] == [3]
    assert client.calls[0]["after_token"] == "TOK"


def test_sdk_v1_exposes_next_token():
    client = _FakeClient()
    data = sdk_with(client).search_benchmarks_v1({"select_filters": {}})

    assert data["next_token"] == "TOK"
