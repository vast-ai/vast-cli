"""Smoke tests for package imports and exports."""
import pytest


class TestPackageImports:
    """Verify the vastai package imports and exports correctly."""

    def test_import_vastai(self) -> None:
        """VastAI can be imported from vastai."""
        from vastai import VastAI
        assert VastAI is not None

    def test_import_serverless(self) -> None:
        """Serverless can be imported from vastai."""
        from vastai import Serverless, ServerlessRequest
        assert Serverless is not None
        assert ServerlessRequest is not None

    def test_import_endpoint(self) -> None:
        """Endpoint can be imported from vastai."""
        from vastai import Endpoint
        assert Endpoint is not None

    def test_import_worker_config(self) -> None:
        """Worker config dataclasses can be imported from vastai."""
        from vastai import Worker, WorkerConfig, HandlerConfig, LogActionConfig, BenchmarkConfig
        assert Worker is not None
        assert WorkerConfig is not None
        assert HandlerConfig is not None
        assert LogActionConfig is not None
        assert BenchmarkConfig is not None
