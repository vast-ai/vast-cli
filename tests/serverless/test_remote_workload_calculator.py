"""Tests for the per-remote-function ``workload_calculator`` argument."""

from vastai.serverless.remote.serve import Deployment
from vastai.serverless.remote.serialization import serialize
from vastai.serverless.server.worker import (
    WorkerConfig,
    HandlerConfig,
    EndpointHandlerFactory,
)


def _client_payload(deployment: Deployment, **kwargs) -> dict:
    """The request body a client sends for a remote call (see Deployment._dispatch)."""
    return {
        "kwargs": {
            k: serialize(v, deployment.root_module) for k, v in kwargs.items()
        }
    }


def _handler_for(deployment: Deployment, route: str, calc):
    """Build the handler into_worker would create for a remote function."""
    entry = deployment.remote_funcs[next(iter(deployment.remote_funcs))]
    wrapped = (
        deployment._wrap_workload_calculator(
            deployment.root_module, calc, entry.globals
        )
        if calc is not None
        else None
    )
    config = WorkerConfig(
        handlers=[HandlerConfig(route=route, workload_calculator=wrapped)]
    )
    return EndpointHandlerFactory(config).get_handler(route)


def test_remote_stores_workload_calculator() -> None:
    d = Deployment(name="wl-store")

    def calc(a, b):
        return float(len(a) * len(b))

    @d.remote(workload_calculator=calc)
    async def mul(a, b):
        return a

    entry = d.remote_funcs[next(iter(d.remote_funcs))]
    assert entry.workload_calculator is calc


def test_workload_calculator_receives_deserialized_kwargs() -> None:
    d = Deployment(name="wl-args")

    @d.remote(workload_calculator=lambda a, b: float(len(a) * len(b)))
    async def mul(a, b):
        return a

    handler = _handler_for(d, "/remote/mul", lambda a, b: float(len(a) * len(b)))
    payload = handler.payload_cls().from_json_msg(
        _client_payload(d, a=[1, 2, 3], b=[4, 5])
    )
    assert payload.count_workload() == 6.0


def test_workload_calculator_default_without_calculator() -> None:
    d = Deployment(name="wl-default")

    @d.remote()
    async def mul(a, b):
        return a

    handler = _handler_for(d, "/remote/mul", None)
    payload = handler.payload_cls().from_json_msg(
        _client_payload(d, a=[1, 2, 3], b=[4, 5])
    )
    assert payload.count_workload() == 100.0


def test_workload_calculator_falls_back_when_it_raises() -> None:
    d = Deployment(name="wl-raises")

    def boom(a, b):
        raise ValueError("bad input")

    @d.remote(workload_calculator=boom)
    async def mul(a, b):
        return a

    handler = _handler_for(d, "/remote/mul", boom)
    payload = handler.payload_cls().from_json_msg(
        _client_payload(d, a=[1, 2, 3], b=[4, 5])
    )
    assert payload.count_workload() == 100.0


def test_workload_calculator_falls_back_on_negative_or_nan() -> None:
    d = Deployment(name="wl-bad-value")

    @d.remote()
    async def mul(a, b):
        return a

    for bad in (-1.0, float("nan"), float("inf")):
        calc = (lambda v: lambda a, b: v)(bad)
        handler = _handler_for(d, "/remote/mul", calc)
        payload = handler.payload_cls().from_json_msg(
            _client_payload(d, a=[1, 2, 3], b=[4, 5])
        )
        assert payload.count_workload() == 100.0


def test_into_worker_wires_workload_calculator(monkeypatch) -> None:
    d = Deployment(name="wl-into-worker")

    @d.remote(
        benchmark_dataset=[{"a": [1, 2, 3], "b": [4, 5]}],
        workload_calculator=lambda a, b: float(len(a) * len(b)),
    )
    async def mul(a, b):
        return a

    captured = {}

    class StubWorker:
        def __init__(self, config):
            captured["config"] = config

    monkeypatch.setattr("vastai.serverless.remote.serve.Worker", StubWorker)

    d.into_worker()

    handler_config = next(
        hc for hc in captured["config"].handlers if hc.route == "/remote/mul"
    )
    assert handler_config.workload_calculator is not None
    assert handler_config.workload_calculator(
        _client_payload(d, a=[1, 2, 3], b=[4, 5])
    ) == 6.0
