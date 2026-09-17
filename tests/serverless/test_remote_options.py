"""Tests for the shared @remote option set.

Deploy mode and serve mode each have their own ``remote()`` implementation. They
used to declare their keyword options independently, which let them drift:
``allow_parallel_requests`` and ``max_queue_time`` existed only in serve mode, so
``@app.remote(allow_parallel_requests=True)`` raised TypeError at deploy time and
the option was unreachable in practice. These tests pin the options to a single
declaration so the two cannot diverge again.
"""

import inspect

import pytest

from vastai.serverless.remote import deploy as deploy_mode
from vastai.serverless.remote import serve as serve_mode
from vastai.serverless.remote.base import RemoteOptions, RemoteOptionsDict


class TestRemoteOptionsDeclaration:
    def test_dataclass_and_typeddict_declare_the_same_keys(self) -> None:
        """The typing surface and the runtime surface must agree."""
        assert RemoteOptions.field_names() == frozenset(
            RemoteOptionsDict.__annotations__
        )

    def test_from_kwargs_applies_defaults(self) -> None:
        opts = RemoteOptions.from_kwargs()
        assert opts.benchmark_runs == 10
        assert opts.allow_parallel_requests is False
        assert opts.max_queue_time == 30.0
        assert opts.benchmark_dataset is None

    def test_from_kwargs_rejects_unknown_option_with_helpful_message(self) -> None:
        with pytest.raises(TypeError) as exc:
            RemoteOptions.from_kwargs(benchmark_datset=[{"x": 1}])
        message = str(exc.value)
        # names the offending key and lists the valid ones
        assert "benchmark_datset" in message
        assert "benchmark_dataset" in message

    def test_from_kwargs_passes_through_known_options(self) -> None:
        opts = RemoteOptions.from_kwargs(
            allow_parallel_requests=True, max_queue_time=None, benchmark_runs=3
        )
        assert opts.allow_parallel_requests is True
        assert opts.max_queue_time is None
        assert opts.benchmark_runs == 3


class TestRemoteSignatureParity:
    def test_deploy_and_serve_accept_the_same_parameters(self) -> None:
        """Regression guard: the two remote() signatures must not drift."""
        deploy_params = set(inspect.signature(deploy_mode.Deployment.remote).parameters)
        serve_params = set(inspect.signature(serve_mode.Deployment.remote).parameters)
        assert deploy_params == serve_params

    @pytest.mark.parametrize("mode", [deploy_mode, serve_mode])
    def test_remote_accepts_every_declared_option(self, mode, monkeypatch) -> None:
        """Every option in RemoteOptions is accepted by both implementations."""
        monkeypatch.setenv("VAST_API_KEY", "test-key")
        app = mode.Deployment(name="opts-test")

        # A dummy value per option that is type-plausible.
        kwargs = {
            "benchmark_dataset": [{"x": 1}],
            "benchmark_generator": None,
            "benchmark_runs": 2,
            "workload_calculator": lambda x=1: 1.0,
            "allow_parallel_requests": True,
            "max_queue_time": 12.5,
        }
        assert set(kwargs) == RemoteOptions.field_names()

        # Must not raise. Previously allow_parallel_requests/max_queue_time
        # raised TypeError in deploy mode.
        decorator = app.remote(**kwargs)
        assert callable(decorator)

    def test_allow_parallel_requests_is_reachable_from_deploy_mode(
        self, monkeypatch
    ) -> None:
        """The specific option that was unreachable before."""
        monkeypatch.setenv("VAST_API_KEY", "test-key")
        app = deploy_mode.Deployment(name="apr-test")
        decorator = app.remote(
            benchmark_dataset=[{"x": 1}], allow_parallel_requests=True
        )
        assert callable(decorator)

    def test_serve_mode_records_the_resolved_options(self, monkeypatch) -> None:
        """Serve mode is the side that acts on these; check they land."""
        monkeypatch.setenv("VAST_API_KEY", "test-key")
        app = serve_mode.Deployment(name="serve-opts")

        @app.remote(
            benchmark_dataset=[{"x": 1}],
            allow_parallel_requests=True,
            max_queue_time=7.0,
            benchmark_runs=4,
        )
        async def f(x):
            return x

        (entry,) = app.remote_funcs.values()
        assert entry.allow_parallel_requests is True
        assert entry.max_queue_time == 7.0
        assert entry.benchmark_runs == 4
