from .base import Config, Deployment_
from ..server.worker import Worker, WorkerConfig, HandlerConfig, BenchmarkConfig
from .serialization import serialize, deserialize, serialize_ok, serialize_err
from typing import (
    ParamSpec,
    Type,
    Any,
    Callable,
    Awaitable,
    TypeVar,
    AsyncContextManager,
    Optional,
)
from dataclasses import dataclass
import asyncio
import logging

logger = logging.getLogger("vastai")

logger.debug("mode: serve")


@dataclass
class RemoteFunc:
    func: Callable[..., Awaitable[Any]]
    globals: dict[str, Any]
    allow_parallel_requests: bool
    max_queue_time: float
    benchmark_dataset: Optional[list[dict[str, Any]]]
    benchmark_generator: Optional[Callable[[], dict[str, Any]]]
    benchmark_runs: int


T = TypeVar("T")
P = ParamSpec("P")


class Deployment(Deployment_, AsyncContextManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.contexts: dict[Type, Any] = {}
        self.context_managers: dict[Type, AsyncContextManager] = {}
        self.remote_funcs: dict[tuple[str], RemoteFunc] = {}

    def context(
        self, *args, **kwargs
    ) -> Callable[
        [Type[AsyncContextManager[T]]], Type[AsyncContextManager[T]]
    ]:  # registers context_class as deployment context
        def decorator(
            context_class: Type[AsyncContextManager[T]],
        ) -> Type[AsyncContextManager[T]]:
            self.context_managers[context_class] = context_class(*args, **kwargs)
            return context_class

        return decorator

    def get_context(self, context_class: Type[AsyncContextManager[T]]) -> T:
        if context_class not in self.contexts:
            raise KeyError(f"Context {context_class} not registered or not yet entered")
        return self.contexts[context_class]

    async def __aenter__(self):
        self.contexts = dict(
            zip(
                self.context_managers.keys(),
                await asyncio.gather(
                    *(
                        manager.__aenter__()
                        for manager in self.context_managers.values()
                    )
                ),
            )
        )

    async def __aexit__(self, exc_type, exc, tb):
        await asyncio.gather(
            *(
                self.context_managers[cls_].__aexit__(exc_type, exc, tb)
                for cls_ in self.contexts.keys()  # only run aexits for contexts we've aentered
            )
        )
        self.contexts = {}  # invalidate contexts

    def _wrap_remote_func(
        self, root_module: str, func: Callable[..., Awaitable[Any]], func_globals: dict
    ) -> Callable[..., Awaitable[Any]]:
        """Wrap a remote function with serialization/deserialization.

        Expects payload: {"args": [serialized_args], "kwargs": {serialized_kwargs}}
        Returns: {"ok": serialized_result} on success, {"err": serialized_exception} on failure.
        """

        async def wrapper(*, args: list = [], kwargs: dict = {}) -> dict:
            deserialized_args = [
                deserialize(a, root_module, func_globals) for a in args
            ]
            deserialized_kwargs = {
                k: deserialize(v, root_module, func_globals) for k, v in kwargs.items()
            }
            try:
                result = await func(*deserialized_args, **deserialized_kwargs)
                return serialize_ok(result, root_module)
            except Exception as e:
                return serialize_err(e, root_module)

        return wrapper

    def into_worker(self) -> Worker:
        handlers: list[HandlerConfig] = []
        if isinstance(self.root_module, str):
            for key, entry in self.remote_funcs.items():
                route = "/remote/" + "/".join(key)

                benchmark_config = None
                if (
                    entry.benchmark_dataset is not None
                    or entry.benchmark_generator is not None
                ):
                    # Serialize benchmark dataset values so they match the
                    # format a real client sends (the wrapper deserializes them).
                    dataset = entry.benchmark_dataset
                    if dataset is not None:
                        dataset = [
                            {
                                "kwargs": {
                                    k: serialize(v, self.root_module)
                                    for k, v in item.items()
                                }
                                for item in dataset
                            }
                        ]
                    benchmark_generator = None
                    if entry.benchmark_generator is not None:
                        root_module = self.root_module  # in case self.root_module changes, bind to current root_module
                        original_benchmark_generator = (
                            entry.benchmark_generator
                        )  # see above
                        benchmark_generator = lambda: {
                            "kwargs": {
                                k: serialize(v, root_module)
                                for k, v in original_benchmark_generator().items()
                            }
                        }

                    benchmark_config = BenchmarkConfig(
                        dataset=dataset,
                        generator=benchmark_generator,
                        runs=entry.benchmark_runs,
                    )

                wrapped = self._wrap_remote_func(
                    self.root_module, entry.func, entry.globals
                )

                handlers.append(
                    HandlerConfig(
                        route=route,
                        remote_function=wrapped,
                        allow_parallel_requests=entry.allow_parallel_requests,
                        benchmark_config=benchmark_config,
                        max_queue_time=entry.max_queue_time,
                    )
                )

            config = WorkerConfig(
                handlers=handlers,
                lifecycle=self,
            )
            return Worker(config)
        raise TypeError("Refusing to create empty Worker!")

    def remote(
        self,
        f: Callable[P, Awaitable[Any]] | None = None,
        *,
        allow_parallel_requests: bool = False,
        max_queue_time: float = 30.0,
        benchmark_dataset: list[dict] | None = None,
        benchmark_generator: Callable[[], dict] | None = None,
        benchmark_runs: int = 10,
    ) -> (
        Callable[P, Awaitable[Any]]
        | Callable[[Callable[P, Awaitable[Any]]], Callable[P, Awaitable[Any]]]
    ):
        def decorator(f: Callable[P, Awaitable[Any]]) -> Callable[P, Awaitable[Any]]:
            key = self.relativize(f)
            self.remote_funcs[key] = RemoteFunc(
                func=f,
                globals=f.__globals__,
                allow_parallel_requests=allow_parallel_requests,
                max_queue_time=max_queue_time,
                benchmark_dataset=benchmark_dataset,
                benchmark_generator=benchmark_generator,
                benchmark_runs=benchmark_runs,
            )
            return f

        if f is not None:
            return decorator(f)
        return decorator
