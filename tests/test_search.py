"""Integration tests for search API. Read-only — no resources created."""

import pytest

from vastai.data.query import Query, Column


pytestmark = pytest.mark.integration


class TestSyncSearch:
    def test_search_returns_offers(self, sync_client):
        q = Query.search_defaults()
        q.extend(Column("num_gpus") >= 1)
        offers = sync_client.search(q, limit=5)
        assert isinstance(offers, list)
        assert len(offers) <= 5
        for o in offers:
            assert o.num_gpus >= 1
            assert o.id is not None
            assert o.gpu_name is not None

    def test_search_with_gpu_filter(self, sync_client):
        q = Query.search_defaults()
        q.extend(Column("gpu_ram") >= 20000)
        offers = sync_client.search(q, limit=3)
        for o in offers:
            assert o.gpu_ram >= 20000

    def test_search_order_by_price(self, sync_client):
        q = Query.search_defaults()
        offers = sync_client.search(q, order=[["dph_total", "asc"]], limit=10)
        prices = [o.dph_total for o in offers if o.dph_total is not None]
        assert prices == sorted(prices)

    def test_search_empty_result(self, sync_client):
        q = Query.search_defaults()
        q.extend(Column("gpu_ram") >= 999999999)
        offers = sync_client.search(q, limit=5)
        assert offers == []


class TestAsyncSearch:
    @pytest.mark.asyncio
    async def test_search_returns_offers(self, async_client):
        q = Query.search_defaults()
        q.extend(Column("num_gpus") >= 1)
        offers = await async_client.search(q, limit=5)
        assert isinstance(offers, list)
        assert len(offers) <= 5
        for o in offers:
            assert o.num_gpus >= 1

    @pytest.mark.asyncio
    async def test_search_with_gpu_filter(self, async_client):
        q = Query.search_defaults()
        q.extend(Column("gpu_ram") >= 20000)
        offers = await async_client.search(q, limit=3)
        for o in offers:
            assert o.gpu_ram >= 20000
