"""Unit tests for data objects. No API calls."""

from vastai.data.query import Query, Column
from vastai.data.endpoint import EndpointConfig, EndpointData
from vastai.data.deployment import DeploymentConfig, DeploymentData, DeploymentPutResponse
from vastai.data.workergroup import WorkergroupConfig
from vastai.data.offer import Offer


# ── Query / Column ──────────────────────────────────────────────────────────

class TestColumn:
    def test_eq(self):
        q = Column("gpu_name") == "A100"
        assert q.query == {"gpu_name": {"eq": "A100"}}

    def test_ne(self):
        q = Column("gpu_name") != "A100"
        assert q.query == {"gpu_name": {"neq": "A100"}}

    def test_gt(self):
        q = Column("gpu_ram") > 24000
        assert q.query == {"gpu_ram": {"gt": 24000}}

    def test_ge(self):
        q = Column("gpu_ram") >= 24000
        assert q.query == {"gpu_ram": {"gte": 24000}}

    def test_lt(self):
        q = Column("dph_total") < 1.0
        assert q.query == {"dph_total": {"lt": 1.0}}

    def test_le(self):
        q = Column("dph_total") <= 1.0
        assert q.query == {"dph_total": {"lte": 1.0}}

    def test_in(self):
        q = Column("gpu_name").in_(["A100", "H100"])
        assert q.query == {"gpu_name": {"in": ["A100", "H100"]}}

    def test_notin(self):
        q = Column("gpu_name").notin_(["A100"])
        assert q.query == {"gpu_name": {"notin": ["A100"]}}


class TestQuery:
    def test_empty(self):
        q = Query({})
        assert q.query == {}

    def test_search_defaults(self):
        q = Query.search_defaults()
        assert q.query == {
            "verified": {"eq": True},
            "rentable": {"eq": True},
            "rented": {"eq": False},
        }

    def test_search_defaults_override(self):
        q = Query.search_defaults(rented=None)
        assert "rented" not in q.query
        assert q.query["verified"] == {"eq": True}

    def test_extend(self):
        q = Query.search_defaults()
        q.extend(Column("gpu_ram") >= 24000)
        assert q.query["gpu_ram"] == {"gte": 24000}
        assert q.query["verified"] == {"eq": True}

    def test_extend_multiple_ops(self):
        q = Query({})
        q.extend(Column("gpu_ram") >= 16000)
        q.extend(Column("gpu_ram") <= 48000)
        assert q.query["gpu_ram"] == {"gte": 16000, "lte": 48000}

    def test_extend_conflict_raises(self):
        q = Query({})
        q.extend(Column("gpu_ram") >= 16000)
        try:
            q.extend(Column("gpu_ram") >= 24000)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "gpu_ram" in str(e)

    def test_extend_returns_self(self):
        q = Query({})
        result = q.extend(Column("gpu_ram") >= 16000)
        assert result is q


# ── EndpointConfig ──────────────────────────────────────────────────────────

class TestEndpointConfig:
    def test_required_only(self):
        cfg = EndpointConfig(endpoint_name="test")
        d = cfg.to_dict()
        assert d == {"endpoint_name": "test"}

    def test_with_optional(self):
        cfg = EndpointConfig(endpoint_name="test", cold_workers=5, max_workers=10)
        d = cfg.to_dict()
        assert d["cold_workers"] == 5
        assert d["max_workers"] == 10

    def test_none_excluded(self):
        cfg = EndpointConfig(endpoint_name="test")
        d = cfg.to_dict()
        assert "cold_workers" not in d
        assert "autoscaler_instance" not in d


# ── WorkergroupConfig ───────────────────────────────────────────────────────

class TestWorkergroupConfig:
    def test_defaults(self):
        cfg = WorkergroupConfig(endpoint_id=1, template_hash="abc")
        d = cfg.to_dict()
        assert d["endpoint_id"] == 1
        assert d["template_hash"] == "abc"
        assert "search_params" in d  # always included

    def test_search_params_default(self):
        cfg = WorkergroupConfig()
        d = cfg.to_dict()
        assert d["search_params"] == ""

    def test_search_params_explicit(self):
        cfg = WorkergroupConfig(search_params="gpu_ram>=8")
        d = cfg.to_dict()
        assert d["search_params"] == "gpu_ram>=8"

    def test_search_params_dict(self):
        cfg = WorkergroupConfig(search_params={"gpu_ram": {"gte": 8}})
        d = cfg.to_dict()
        assert d["search_params"] == {"gpu_ram": {"gte": 8}}


# ── DeploymentConfig ────────────────────────────────────────────────────────

class TestDeploymentConfig:
    def test_required_fields(self):
        cfg = DeploymentConfig(name="dep", image="pytorch/pytorch", file_hash="abc", file_size=1024)
        d = cfg.to_dict()
        assert d["name"] == "dep"
        assert d["image"] == "pytorch/pytorch"
        assert d["file_hash"] == "abc"
        assert d["file_size"] == 1024

    def test_none_excluded(self):
        cfg = DeploymentConfig(name="dep", image="img", file_hash="h", file_size=1)
        d = cfg.to_dict()
        assert "tag" not in d
        assert "ttl" not in d
        assert "cold_workers" not in d

    def test_with_scaling_params(self):
        cfg = DeploymentConfig(
            name="dep", image="img", file_hash="h", file_size=1,
            cold_workers=3, max_workers=10
        )
        d = cfg.to_dict()
        assert d["cold_workers"] == 3
        assert d["max_workers"] == 10


# ── EndpointData ────────────────────────────────────────────────────────────

class TestEndpointData:
    def test_from_dict(self):
        raw = {
            "id": 42,
            "endpoint_name": "my-ep",
            "api_key": "abc123",
            "user_id": 1,
            "created_at": 1000.0,
            "cold_workers": 3,
            "max_workers": 20,
            "min_load": 0.0,
            "min_cold_load": 0.0,
            "target_util": 0.9,
            "cold_mult": 3.0,
            "max_queue_time": 30.0,
            "target_queue_time": 10.0,
            "endpoint_state": "active",
            "inactivity_timeout": None,
            "auto_delete_in_seconds": 100.0,
            "auto_delete_due_24h": False,
        }
        data = EndpointData.from_dict(raw)
        assert data.id == 42
        assert data.api_key == "abc123"
        assert data.config.endpoint_name == "my-ep"
        assert data.config.cold_workers == 3
        assert data.config.endpoint_state == "active"
        assert data.auto_delete_in_seconds == 100.0

    def test_from_dict_missing_optional(self):
        raw = {
            "id": 1,
            "endpoint_name": "ep",
            "api_key": "k",
            "user_id": 1,
            "created_at": 0.0,
        }
        data = EndpointData.from_dict(raw)
        assert data.config.cold_workers is None
        assert data.auto_delete_in_seconds is None
        assert data.auto_delete_due_24h is False


# ── DeploymentData ──────────────────────────────────────────────────────────

class TestDeploymentData:
    def test_from_dict(self):
        raw = {
            "id": 10,
            "name": "my-dep",
            "tag": "v1",
            "endpoint_id": 42,
            "endpoint_state": "active",
            "worker_count": 3,
            "s3_key": "some/key",
            "env": "FOO=bar",
            "image": "pytorch/pytorch",
            "storage": 50.0,
            "search_params": "gpu_ram>=8",
            "file_hash": "abc",
            "current_version_id": 1,
            "last_healthy_version_id": 1,
            "ttl": None,
            "last_client_heartbeat": None,
            "created_at": 1000.0,
            "updated_at": 2000.0,
        }
        data = DeploymentData.from_dict(raw)
        assert data.id == 10
        assert data.name == "my-dep"
        assert data.endpoint_id == 42
        assert data.image == "pytorch/pytorch"


# ── DeploymentPutResponse ──────────────────────────────────────────────────

class TestDeploymentPutResponse:
    def test_from_dict(self):
        raw = {
            "success": True,
            "action": "created",
            "deployment_id": 5,
            "endpoint_id": 10,
            "upload_url": "https://s3.example.com/upload",
            "upload_fields": {"key": "value"},
        }
        resp = DeploymentPutResponse.from_dict(raw)
        assert resp.action == "created"
        assert resp.deployment_id == 5
        assert resp.upload_url == "https://s3.example.com/upload"

    def test_from_dict_minimal(self):
        raw = {
            "success": True,
            "action": "exists",
            "deployment_id": 5,
            "endpoint_id": 10,
        }
        resp = DeploymentPutResponse.from_dict(raw)
        assert resp.upload_url is None
        assert resp.evicted_versions is None


# ── Offer ───────────────────────────────────────────────────────────────────

class TestOffer:
    def test_from_dict_ignores_unknown(self):
        """Offer.from_dict should accept a full API response dict and ignore extra keys."""
        import dataclasses
        # Build a dict with all known fields set to None, then override a few
        base = {f.name: None for f in dataclasses.fields(Offer)}
        base.update({"id": 1, "gpu_name": "A100", "gpu_ram": 80000, "machine_id": 42,
                     "host_id": 1, "num_gpus": 8, "unknown_field": "ignored"})
        offer = Offer.from_dict(base)
        assert offer.id == 1
        assert offer.gpu_name == "A100"
        assert offer.num_gpus == 8
        assert not hasattr(offer, "unknown_field")
