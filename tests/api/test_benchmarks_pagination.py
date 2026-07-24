"""search_benchmarks pages through next_token only when asked to."""

from vastai.api import offers


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
        self.calls.append(query_args or {})
        if (query_args or {}).get("after_token"):
            return _FakeResp([{"id": 3}])
        return _FakeResp([{"id": 1}, {"id": 2}], token="TOK")


def test_single_page_by_default():
    client = _FakeClient()
    rows, token = offers.search_benchmarks(client, query={"type": {"eq": "perf"}})

    assert [r["id"] for r in rows] == [1, 2]
    assert token == "TOK"
    assert len(client.calls) == 1
    assert "after_token" not in client.calls[0]


def test_all_pages_follows_next_token():
    client = _FakeClient()
    rows, token = offers.search_benchmarks(client, all_pages=True)
    assert token is None

    # Every row across both pages, in order.
    assert [r["id"] for r in rows] == [1, 2, 3]
    # Two requests: the second echoes the token from the first page.
    assert len(client.calls) == 2
    assert client.calls[1]["after_token"] == "TOK"


def test_omits_limit_when_unset():
    client = _FakeClient()
    offers.search_benchmarks(client)
    assert "limit" not in client.calls[0]


def test_forwards_limit():
    client = _FakeClient()
    offers.search_benchmarks(client, limit=100)
    assert client.calls[0]["limit"] == 100


def test_resumes_from_token():
    client = _FakeClient()
    rows, token = offers.search_benchmarks(client, after_token="TOK")
    assert [r["id"] for r in rows] == [3]
    assert token is None
