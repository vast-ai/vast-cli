"""Unit tests for vastai.serverless.server.worker components.

Tests LogActionConfig, WorkerConfig, HandlerConfig, BenchmarkConfig,
EndpointHandlerFactory, and created handler/payload behavior.
Does not start the full Worker server.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vastai.serverless.server.lib.data_types import LogAction, JsonDataException
from vastai.serverless.server.worker import (
    LogActionConfig,
    WorkerConfig,
    HandlerConfig,
    BenchmarkConfig,
    EndpointHandlerFactory,
)


class TestLogActionConfig:
    """Verify LogActionConfig builds log_actions correctly."""

    def test_log_actions_empty_when_no_config(self) -> None:
        """
        Verifies that log_actions returns empty list when no actions configured.

        This test verifies by:
        1. Creating LogActionConfig with default (empty) lists
        2. Asserting log_actions is empty

        Assumptions:
        - Default LogActionConfig has empty on_load, on_error, on_info
        """
        config = LogActionConfig()
        assert config.log_actions == []

    def test_log_actions_includes_on_load_messages(self) -> None:
        """
        Verifies that on_load messages are mapped to LogAction.ModelLoaded.

        This test verifies by:
        1. Creating LogActionConfig with on_load messages
        2. Asserting log_actions contains (ModelLoaded, msg) for each

        Assumptions:
        - log_actions property builds list from on_load, on_error, on_info
        """
        config = LogActionConfig(on_load=["Model loaded", "Ready"])
        actions = config.log_actions
        assert (LogAction.ModelLoaded, "Model loaded") in actions
        assert (LogAction.ModelLoaded, "Ready") in actions
        assert len(actions) == 2

    def test_log_actions_includes_on_error_messages(self) -> None:
        """
        Verifies that on_error messages are mapped to LogAction.ModelError.

        This test verifies by:
        1. Creating LogActionConfig with on_error messages
        2. Asserting log_actions contains (ModelError, msg) for each

        Assumptions:
        - log_actions property builds list from on_load, on_error, on_info
        """
        config = LogActionConfig(on_error=["Error occurred"])
        actions = config.log_actions
        assert (LogAction.ModelError, "Error occurred") in actions

    def test_log_actions_includes_on_info_messages(self) -> None:
        """
        Verifies that on_info messages are mapped to LogAction.Info.

        This test verifies by:
        1. Creating LogActionConfig with on_info messages
        2. Asserting log_actions contains (Info, msg) for each

        Assumptions:
        - log_actions property builds list from on_load, on_error, on_info
        """
        config = LogActionConfig(on_info=["Info message"])
        actions = config.log_actions
        assert (LogAction.Info, "Info message") in actions

    def test_log_actions_combines_all_action_types(self) -> None:
        """
        Verifies that log_actions combines on_load, on_error, on_info in order.

        This test verifies by:
        1. Creating LogActionConfig with all three list types populated
        2. Asserting log_actions contains correct tuples in expected order

        Assumptions:
        - extend order: on_load first, then on_error, then on_info
        """
        config = LogActionConfig(
            on_load=["load1"],
            on_error=["err1"],
            on_info=["info1"],
        )
        actions = config.log_actions
        assert actions == [
            (LogAction.ModelLoaded, "load1"),
            (LogAction.ModelError, "err1"),
            (LogAction.Info, "info1"),
        ]


class TestEndpointHandlerFactory:
    """Verify EndpointHandlerFactory creates handlers from WorkerConfig."""

    def test_factory_with_empty_handlers_creates_default_route(
        self, server_worker_config
    ) -> None:
        """
        Verifies that empty handlers list creates a default handler at /.

        This test verifies by:
        1. Creating EndpointHandlerFactory with config that has no handlers
        2. Asserting get_handler("/") returns a handler
        3. Asserting handler.endpoint == "/"

        Assumptions:
        - minimal_worker_config fixture provides config with empty handlers
        """
        factory = EndpointHandlerFactory(server_worker_config("minimal"))
        handler = factory.get_handler("/")
        assert handler is not None
        assert handler.endpoint == "/"

    def test_get_handler_returns_none_for_unknown_route(
        self, server_worker_config
    ) -> None:
        """
        Verifies that get_handler returns None for unregistered route.

        This test verifies by:
        1. Creating factory with minimal config
        2. Calling get_handler with unknown route
        3. Asserting result is None

        Assumptions:
        - get_handler uses dict.get, returns None for missing key
        """
        factory = EndpointHandlerFactory(server_worker_config("minimal"))
        assert factory.get_handler("/unknown") is None

    def test_get_all_handlers_returns_copy(self, server_worker_config) -> None:
        """
        Verifies that get_all_handlers returns a copy of handlers dict.

        This test verifies by:
        1. Creating factory and getting handlers
        2. Mutating the returned dict
        3. Asserting factory's internal state is unchanged

        Assumptions:
        - get_all_handlers returns .copy()
        """
        factory = EndpointHandlerFactory(server_worker_config("minimal"))
        handlers = factory.get_all_handlers()
        handlers["/"] = None
        assert factory.get_handler("/") is not None

    def test_has_handlers_true_when_handlers_exist(self, server_worker_config) -> None:
        """
        Verifies that has_handlers returns True when handlers are registered.

        This test verifies by:
        1. Creating factory with default handler
        2. Asserting has_handlers() is True

        Assumptions:
        - minimal_worker_config creates default / handler
        """
        factory = EndpointHandlerFactory(server_worker_config("minimal"))
        assert factory.has_handlers() is True

    def test_model_server_base_url_formats_correctly(
        self, server_worker_config
    ) -> None:
        """
        Verifies that model_server_base_url returns url:port format.

        This test verifies by:
        1. Creating factory with url and port
        2. Asserting model_server_base_url == "http://localhost:8000"

        Assumptions:
        - minimal_worker_config has url and port set
        """
        factory = EndpointHandlerFactory(server_worker_config("minimal"))
        assert factory.model_server_base_url == "http://localhost:8000"

    def test_get_benchmark_handler_returns_none_when_no_handlers(
        self, server_worker_config
    ) -> None:
        """
        Verifies that get_benchmark_handler returns None when _handlers is empty.

        This test verifies by:
        1. Creating factory (which has default handler)
        2. Clearing _handlers to simulate empty state
        3. Calling get_benchmark_handler()
        4. Asserting result is None

        Assumptions:
        - get_benchmark_handler returns None when no handlers are registered
        """
        factory = EndpointHandlerFactory(server_worker_config("minimal"))
        factory._handlers.clear()
        assert factory.get_benchmark_handler() is None

    def test_has_handlers_false_when_no_handlers(self, server_worker_config) -> None:
        """
        Verifies that has_handlers returns False when _handlers is empty.

        This test verifies by:
        1. Creating factory and clearing _handlers
        2. Asserting has_handlers() is False

        Assumptions:
        - has_handlers returns len(self._handlers) > 0
        """
        factory = EndpointHandlerFactory(server_worker_config("minimal"))
        factory._handlers.clear()
        assert factory.has_handlers() is False

    def test_get_benchmark_handler_raises_when_none_has_benchmark(
        self, server_worker_config
    ) -> None:
        """
        Verifies that get_benchmark_handler raises when no handler has benchmark.

        This test verifies by:
        1. Creating factory with empty handlers (default handler has no BenchmarkConfig)
        2. Calling get_benchmark_handler
        3. Asserting Exception is raised with "Missing EndpointHandler"

        Assumptions:
        - minimal_worker_config creates default handler with no BenchmarkConfig
        """
        factory = EndpointHandlerFactory(server_worker_config("minimal"))
        with pytest.raises(
            Exception, match="Missing EndpointHandler with BenchmarkConfig"
        ):
            factory.get_benchmark_handler()

    def test_factory_with_handler_and_benchmark_config_creates_handler(
        self, server_worker_config
    ) -> None:
        """
        Verifies that HandlerConfig with BenchmarkConfig creates benchmark handler.

        This test verifies by:
        1. Using server_worker_config fixture to build config with /predict handler
        2. Creating EndpointHandlerFactory
        3. Asserting get_benchmark_handler returns the handler
        4. Asserting get_handler returns handler for the route

        Assumptions:
        - server_worker_config creates valid config with BenchmarkConfig
        """
        config = server_worker_config(
            "handler", route="/predict", dataset=[{"input": "test"}]
        )
        factory = EndpointHandlerFactory(config)
        benchmark_handler = factory.get_benchmark_handler()
        assert benchmark_handler is not None
        assert benchmark_handler.endpoint == "/predict"
        assert benchmark_handler.has_benchmark is True
        assert factory.get_handler("/predict") is benchmark_handler

    def test_get_benchmark_handler_raises_when_multiple_have_benchmark(
        self, server_worker_config
    ) -> None:
        """
        Verifies that get_benchmark_handler raises when multiple handlers have BenchmarkConfig.

        This test verifies by:
        1. Using server_worker_config with extra_handlers to add second benchmark
        2. Creating EndpointHandlerFactory
        3. Calling get_benchmark_handler
        4. Asserting Exception is raised with "Cannot define BenchmarkConfig"

        Assumptions:
        - Exactly one handler may have BenchmarkConfig
        """
        config = server_worker_config(
            "handler",
            route="/a",
            dataset=[{"x": 1}],
            extra_handlers=[
                HandlerConfig(
                    route="/b",
                    benchmark_config=BenchmarkConfig(dataset=[{"x": 2}]),
                ),
            ],
        )
        factory = EndpointHandlerFactory(config)
        with pytest.raises(
            Exception, match="Cannot define BenchmarkConfig for more than one"
        ):
            factory.get_benchmark_handler()

    def test_factory_with_explicit_handler_config_creates_handler(
        self, server_worker_config
    ) -> None:
        """
        Verifies that explicit HandlerConfig creates handler at specified route.

        This test verifies by:
        1. Using server_worker_config for /v1/chat route
        2. Creating EndpointHandlerFactory
        3. Asserting get_handler("/v1/chat") returns handler with that endpoint

        Assumptions:
        - server_worker_config creates config with handlers list
        """
        config = server_worker_config(
            "handler", route="/v1/chat", dataset=[{"messages": []}]
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/v1/chat")
        assert handler is not None
        assert handler.endpoint == "/v1/chat"


class TestWorkerConfigAndDataclasses:
    """Verify WorkerConfig, HandlerConfig, BenchmarkConfig construction."""

    def test_worker_config_defaults(self) -> None:
        """
        Verifies that WorkerConfig has expected default values.

        This test verifies by:
        1. Creating WorkerConfig with no args
        2. Asserting key defaults

        Assumptions:
        - Defaults match dataclass field defaults
        """
        config = WorkerConfig()
        assert config.model_server_url is None
        assert config.model_server_port is None
        assert config.handlers == []
        assert config.max_sessions == 10

    def test_handler_config_with_benchmark(self) -> None:
        """
        Verifies that HandlerConfig accepts benchmark_config.

        This test verifies by:
        1. Creating HandlerConfig with BenchmarkConfig
        2. Asserting benchmark_config is set

        Assumptions:
        - benchmark_config is optional
        """
        bc = BenchmarkConfig(dataset=[{"a": 1}], runs=4)
        hc = HandlerConfig(route="/", benchmark_config=bc)
        assert hc.benchmark_config is bc
        assert hc.benchmark_config.runs == 4

    def test_benchmark_config_with_generator(self) -> None:
        """
        Verifies that BenchmarkConfig accepts generator callable.

        This test verifies by:
        1. Creating BenchmarkConfig with generator
        2. Asserting generator is set

        Assumptions:
        - generator is optional, alternative to dataset
        """

        def gen() -> dict:
            return {"sample": 1}

        config = BenchmarkConfig(generator=gen)
        assert config.generator is gen
        assert config.generator() == {"sample": 1}


class TestEndpointHandlerFactoryCreatedPayload:
    """Verify payload class created by _create_handler (GenericApiPayload) behavior."""

    def test_payload_for_test_with_dataset_returns_sample(
        self, server_worker_config
    ) -> None:
        """
        Verifies that payload_cls().for_test() returns a payload with data from dataset.

        This test verifies by:
        1. Creating factory with HandlerConfig that has BenchmarkConfig(dataset=[...])
        2. Getting handler and calling payload_cls().for_test() multiple times
        3. Asserting returned payload has .input in the dataset and generate_payload_json matches

        Assumptions:
        - GenericApiPayload.for_test uses random.choice(benchmark_config.dataset)
        """
        dataset = [{"a": 1}, {"b": 2}]
        config = server_worker_config("handler", route="/predict", dataset=dataset)
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/predict")
        payload_cls = handler.payload_cls()

        for _ in range(10):
            payload = payload_cls.for_test()
            assert payload.input in dataset
            assert payload.generate_payload_json() == payload.input

    def test_payload_for_test_with_generator_uses_generator(
        self, server_worker_config
    ) -> None:
        """
        Verifies that payload_cls().for_test() uses benchmark_config.generator when set.

        This test verifies by:
        1. Creating HandlerConfig with BenchmarkConfig(generator=callable) and no dataset
        2. Building config with that single handler and creating factory
        3. Calling payload_cls().for_test() and asserting input matches generator return

        Assumptions:
        - generator is called once per for_test(); we use a deterministic generator
        """

        def gen():
            return {"from_generator": True}

        config = server_worker_config(
            "from_handlers",
            handlers=[
                HandlerConfig(
                    route="/gen",
                    benchmark_config=BenchmarkConfig(generator=gen),
                ),
            ],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/gen")
        payload = handler.payload_cls().for_test()
        assert payload.input == {"from_generator": True}
        assert payload.generate_payload_json() == {"from_generator": True}

    def test_payload_for_test_without_dataset_or_generator_raises(
        self, server_worker_config
    ) -> None:
        """
        Verifies that payload_cls().for_test() raises when BenchmarkConfig has no dataset or generator.

        This test verifies by:
        1. Creating HandlerConfig with BenchmarkConfig() (no dataset, no generator)
        2. Creating factory and getting handler
        3. Calling payload_cls().for_test()
        4. Asserting an Exception is raised (missing data path raises)

        Assumptions:
        - Exactly one handler must have BenchmarkConfig for get_benchmark_handler; this config has one
        - Implementation may raise Exception("Missing BenchmarkConfig!") or UnboundLocalError
        """
        config = server_worker_config(
            "from_handlers",
            handlers=[
                HandlerConfig(
                    route="/",
                    benchmark_config=BenchmarkConfig(),
                ),
            ],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/")
        with pytest.raises(Exception):
            handler.payload_cls().for_test()

    def test_payload_for_test_raises_when_benchmark_config_is_none(
        self, server_worker_config
    ) -> None:
        """
        Verifies that for_test() hits the ``Missing BenchmarkConfig!`` branch when
        ``HandlerConfig.benchmark_config`` is omitted (None).

        Generic ``for_test`` only enters that else-branch when ``benchmark_config`` is
        falsy; an empty ``BenchmarkConfig()`` is still truthy, so this case is distinct
        from ``test_payload_for_test_without_dataset_or_generator_raises``.
        """
        config = server_worker_config(
            "from_handlers",
            handlers=[
                HandlerConfig(route="/nobench", benchmark_config=None),
            ],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/nobench")
        with pytest.raises(Exception, match="Missing BenchmarkConfig"):
            handler.payload_cls().for_test()

    def test_payload_from_json_msg_wraps_json_data_exception_from_from_dict(
        self, server_worker_config
    ) -> None:
        """
        Verifies that ``from_json_msg`` converts ``JsonDataException`` from ``from_dict``
        into a new ``JsonDataException`` (the ``except`` block after ``from_dict``).
        """
        config = server_worker_config(
            "from_handlers",
            handlers=[
                HandlerConfig(
                    route="/jd",
                    benchmark_config=BenchmarkConfig(dataset=[{"a": 1}]),
                ),
            ],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/jd")
        payload_cls = handler.payload_cls()
        with patch.object(
            payload_cls,
            "from_dict",
            side_effect=JsonDataException({"field": "bad"}),
        ):
            with pytest.raises(
                JsonDataException, match="Error in user response handler"
            ):
                payload_cls.from_json_msg({"ok": True})

    def test_payload_from_dict_and_generate_payload_json(
        self, server_worker_config
    ) -> None:
        """
        Verifies that payload from_dict builds payload and generate_payload_json returns input.

        This test verifies by:
        1. Getting handler from factory with benchmark config
        2. Creating payload via payload_cls().from_dict(input)
        3. Asserting generate_payload_json() returns that input

        Assumptions:
        - GenericApiPayload.from_dict(input) creates payload with input=input
        """
        config = server_worker_config("handler", route="/", dataset=[{"x": 1}])
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/")
        payload_cls = handler.payload_cls()
        payload = payload_cls.from_dict({"key": "value"})
        assert payload.input == {"key": "value"}
        assert payload.generate_payload_json() == {"key": "value"}

    def test_payload_from_json_msg_without_parser(self, server_worker_config) -> None:
        """
        Verifies that from_json_msg parses dict into payload when no request_parser.

        This test verifies by:
        1. Getting handler (no request_parser)
        2. Calling payload_cls().from_json_msg({"key": "v"})
        3. Asserting payload.input == {"key": "v"}

        Assumptions:
        - from_json_msg without parser calls from_dict(json_msg) directly
        """
        config = server_worker_config("handler", route="/", dataset=[{"a": 1}])
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/")
        payload = handler.payload_cls().from_json_msg({"key": "v"})
        assert payload.input == {"key": "v"}

    def test_payload_from_json_msg_with_parser_applies_parser(
        self, server_worker_config
    ) -> None:
        """
        Verifies that from_json_msg applies request_parser when provided.

        This test verifies by:
        1. Creating HandlerConfig with request_parser that rewrites the dict
        2. Creating factory and getting handler
        3. Calling from_json_msg with raw dict
        4. Asserting payload reflects parsed (rewritten) dict

        Assumptions:
        - request_parser is called with json_msg and result passed to from_dict
        """

        def parser(raw):
            return {"parsed": raw.get("raw_key", "")}

        config = server_worker_config(
            "from_handlers",
            handlers=[
                HandlerConfig(
                    route="/p",
                    benchmark_config=BenchmarkConfig(dataset=[{"a": 1}]),
                    request_parser=parser,
                ),
            ],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/p")
        payload = handler.payload_cls().from_json_msg({"raw_key": "value"})
        assert payload.input == {"parsed": "value"}

    def test_payload_from_json_msg_non_dict_raises_json_data_exception(
        self, server_worker_config
    ) -> None:
        """
        Verifies that from_json_msg raises JsonDataException when message is not a dict.

        This test verifies by:
        1. Getting handler from factory
        2. Calling from_json_msg with a list (or non-dict)
        3. Asserting JsonDataException is raised

        Assumptions:
        - worker raises JsonDataException({"data": "payload must be a dictionary"}) for non-dict
        """
        config = server_worker_config("handler", route="/", dataset=[{"a": 1}])
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/")
        with pytest.raises(JsonDataException) as exc_info:
            handler.payload_cls().from_json_msg([1, 2, 3])
        assert exc_info.value.message.get("data") == "payload must be a dictionary"

    def test_payload_count_workload_default(self, server_worker_config) -> None:
        """
        Verifies that count_workload returns 100.0 when no workload_calculator.

        This test verifies by:
        1. Getting handler without workload_calculator
        2. Creating payload and calling count_workload()
        3. Asserting result == 100.0

        Assumptions:
        - Default workload in GenericApiPayload is 100.0
        """
        config = server_worker_config("handler", route="/", dataset=[{"a": 1}])
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/")
        payload = handler.payload_cls().from_dict({"x": 1})
        assert payload.count_workload() == 100.0

    def test_payload_count_workload_uses_calculator(self, server_worker_config) -> None:
        """
        Verifies that count_workload uses workload_calculator when provided.

        This test verifies by:
        1. Creating HandlerConfig with workload_calculator that returns 7.0 for input
        2. Creating payload and calling count_workload()
        3. Asserting result == 7.0

        Assumptions:
        - workload_calculator(input) is called and its return used
        """

        def calc(data):
            return float(data.get("tokens", 0))

        config = server_worker_config(
            "from_handlers",
            handlers=[
                HandlerConfig(
                    route="/w",
                    benchmark_config=BenchmarkConfig(dataset=[{"tokens": 7}]),
                    workload_calculator=calc,
                ),
            ],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/w")
        payload = handler.payload_cls().from_dict({"tokens": 7})
        assert payload.count_workload() == 7.0

    def test_payload_for_test_raises_when_generator_raises(
        self, server_worker_config
    ) -> None:
        """
        Verifies that payload_cls().for_test() raises with expected message when generator raises.

        This test verifies by:
        1. Creating HandlerConfig with BenchmarkConfig(generator=callable_that_raises)
        2. Creating factory and getting handler
        3. Calling payload_cls().for_test()
        4. Asserting Exception is raised with "Error generating benchmark data"

        Assumptions:
        - Generator exception is wrapped in Exception with route name
        """

        def bad_gen():
            raise ValueError("generator failed")

        config = server_worker_config(
            "from_handlers",
            handlers=[
                HandlerConfig(
                    route="/badgen",
                    benchmark_config=BenchmarkConfig(generator=bad_gen),
                ),
            ],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/badgen")
        with pytest.raises(Exception, match="Error generating benchmark data"):
            handler.payload_cls().for_test()

    def test_payload_from_json_msg_raises_when_request_parser_raises(
        self, server_worker_config
    ) -> None:
        """
        Verifies that from_json_msg raises Exception when request_parser raises.

        This test verifies by:
        1. Creating HandlerConfig with request_parser that raises
        2. Calling payload_cls().from_json_msg(...)
        3. Asserting Exception is raised with "Error in user response handler"

        Assumptions:
        - Parser exception is wrapped in Exception
        """

        def failing_parser(_):
            raise RuntimeError("parser error")

        config = server_worker_config(
            "from_handlers",
            handlers=[
                HandlerConfig(
                    route="/p",
                    benchmark_config=BenchmarkConfig(dataset=[{"a": 1}]),
                    request_parser=failing_parser,
                ),
            ],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/p")
        with pytest.raises(Exception, match="Error in user response handler"):
            handler.payload_cls().from_json_msg({"x": 1})

    def test_factory_with_payload_class_uses_user_payload_class(
        self, server_worker_config
    ) -> None:
        """
        Verifies that HandlerConfig with payload_class uses that class instead of GenericApiPayload.

        This test verifies by:
        1. Defining a custom ApiPayload subclass with distinct for_test/from_json_msg behavior
        2. Creating HandlerConfig with payload_class=ThatClass and BenchmarkConfig
        3. Creating factory and getting handler
        4. Asserting payload_cls() is the custom class and for_test/from_json_msg use its logic

        Assumptions:
        - When payload_class is set, _create_handler uses it and does not create GenericApiPayload
        """
        from vastai.serverless.server.lib.data_types import ApiPayload
        from dataclasses import dataclass

        @dataclass
        class CustomPayload(ApiPayload):
            value: int = 0

            @classmethod
            def for_test(cls):
                return cls(value=99)

            def generate_payload_json(self):
                return {"value": self.value}

            def count_workload(self) -> float:
                return float(self.value)

            @classmethod
            def from_dict(cls, input_dict):
                return cls(value=input_dict.get("value", 0))

            @classmethod
            def from_json_msg(cls, json_msg):
                if not isinstance(json_msg, dict):
                    raise JsonDataException({"data": "must be dict"})
                return cls.from_dict(json_msg)

        config = server_worker_config(
            "from_handlers",
            handlers=[
                HandlerConfig(
                    route="/custom",
                    benchmark_config=BenchmarkConfig(dataset=[{"ignored": 1}]),
                    payload_class=CustomPayload,
                ),
                HandlerConfig(
                    route="/bench",
                    benchmark_config=BenchmarkConfig(dataset=[{"a": 1}]),
                ),
            ],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/custom")
        assert handler.payload_cls() is CustomPayload
        payload = handler.payload_cls().for_test()
        assert payload.value == 99
        assert payload.count_workload() == 99.0
        payload2 = handler.payload_cls().from_json_msg({"value": 3})
        assert payload2.value == 3


class TestEndpointHandlerFactoryCreatedHandler:
    """Verify handler instance created by _create_handler (GenericEndpointHandler) behavior."""

    def test_generic_handler_healthcheck_endpoint_is_none(
        self, server_worker_config
    ) -> None:
        """GenericEndpointHandler does not expose a model health URL by default."""
        config = server_worker_config("handler", route="/h", dataset=[{"a": 1}])
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/h")
        assert handler.healthcheck_endpoint is None

    def test_make_benchmark_payload_calls_payload_for_test(
        self, server_worker_config
    ) -> None:
        """
        Verifies that make_benchmark_payload returns payload_cls().for_test().

        This test verifies by:
        1. Creating factory with known dataset
        2. Calling handler.make_benchmark_payload()
        3. Asserting result is payload with .input in dataset

        Assumptions:
        - make_benchmark_payload delegates to PayloadClass.for_test()
        """
        dataset = [{"bench": 1}]
        config = server_worker_config("handler", route="/predict", dataset=dataset)
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/predict")
        payload = handler.make_benchmark_payload()
        assert payload.input in dataset

    @pytest.mark.asyncio
    async def test_generate_client_response_uses_user_response_generator(
        self,
        server_worker_config,
        make_mock_web_request,
        make_mock_model_response,
    ) -> None:
        """
        Verifies that generate_client_response calls user_response_generator when provided.

        This test verifies by:
        1. Creating HandlerConfig with response_generator that returns a fixed web.Response
        2. Getting handler and calling generate_client_response with mock request/response
        3. Asserting returned response is the one from the generator

        Assumptions:
        - user_response_generator(client_request, model_response) is awaited and returned
        """
        from aiohttp import web

        async def my_generator(_req, _model_resp):
            return web.Response(text="custom", status=201)

        config = server_worker_config(
            "from_handlers",
            handlers=[
                HandlerConfig(
                    route="/r",
                    benchmark_config=BenchmarkConfig(dataset=[{"a": 1}]),
                    response_generator=my_generator,
                ),
            ],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/r")
        mock_req = make_mock_web_request(spec_request=True)
        mock_model_resp = make_mock_model_response()
        response = await handler.generate_client_response(mock_req, mock_model_resp)
        assert response.status == 201
        # aiohttp.web.Response body is in .body
        assert response.body == b"custom"

    @pytest.mark.asyncio
    async def test_generate_client_response_default_non_streaming(
        self,
        server_worker_config,
        make_mock_web_request,
        make_mock_model_response,
    ) -> None:
        """
        Verifies that default generate_client_response returns web.Response for non-streaming.

        This test verifies by:
        1. Getting handler without response_generator
        2. Mocking model_response with content_type application/json and read() returning body
        3. Calling generate_client_response
        4. Asserting result is web.Response with same body and status

        Assumptions:
        - When content_type is not streaming and no chunked, body is read and web.Response returned
        """
        from aiohttp import web

        config = server_worker_config("handler", route="/", dataset=[{"a": 1}])
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/")
        mock_req = make_mock_web_request(spec_request=True)
        mock_model_resp = make_mock_model_response(
            content_type="application/json",
            body=b'{"ok": true}',
            status=200,
        )

        response = await handler.generate_client_response(mock_req, mock_model_resp)
        assert isinstance(response, web.Response)
        assert response.status == 200
        assert response.body == b'{"ok": true}'

    @pytest.mark.asyncio
    async def test_call_remote_dispatch_function_raises_when_not_configured(
        self, server_worker_config
    ) -> None:
        """
        Verifies that call_remote_dispatch_function raises RuntimeError when remote_function is None.

        This test verifies by:
        1. Getting handler created without remote_function
        2. Calling call_remote_dispatch_function(params)
        3. Asserting RuntimeError with "remote_function is not configured"

        Assumptions:
        - remote_dispatch_function None triggers RuntimeError
        """
        config = server_worker_config("handler", route="/", dataset=[{"a": 1}])
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/")
        with pytest.raises(RuntimeError, match="remote_function is not configured"):
            await handler.call_remote_dispatch_function({})

    @pytest.mark.asyncio
    async def test_call_remote_dispatch_function_calls_remote(
        self, server_worker_config
    ) -> None:
        """
        Verifies that call_remote_dispatch_function calls remote_function and returns result.

        This test verifies by:
        1. Creating HandlerConfig with remote_function async that returns a value
        2. Getting handler and calling call_remote_dispatch_function
        3. Asserting return value matches

        Assumptions:
        - remote_function(**params) is awaited and result returned
        """

        async def remote(**kwargs):
            return kwargs.get("x", 0) + 1

        config = server_worker_config(
            "from_handlers",
            handlers=[
                HandlerConfig(
                    route="/remote",
                    benchmark_config=BenchmarkConfig(dataset=[{"a": 1}]),
                    remote_function=remote,
                ),
            ],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/remote")
        result = await handler.call_remote_dispatch_function({"x": 10})
        assert result == 11

    @pytest.mark.asyncio
    async def test_generate_client_response_raises_when_user_response_generator_raises(
        self,
        server_worker_config,
        make_mock_web_request,
        make_mock_model_response,
    ) -> None:
        """
        Verifies that generate_client_response raises when user_response_generator raises.

        This test verifies by:
        1. Creating HandlerConfig with response_generator that raises
        2. Calling generate_client_response
        3. Asserting Exception is raised with "Error in user response generator"

        Assumptions:
        - Exception from generator is wrapped and re-raised
        """
        from aiohttp import web

        async def bad_generator(_req, _resp):
            raise ValueError("generator failed")

        config = server_worker_config(
            "from_handlers",
            handlers=[
                HandlerConfig(
                    route="/r",
                    benchmark_config=BenchmarkConfig(dataset=[{"a": 1}]),
                    response_generator=bad_generator,
                ),
            ],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/r")
        mock_req = make_mock_web_request(spec_request=True)
        mock_resp = make_mock_model_response()
        with pytest.raises(Exception, match="Error in user response generator"):
            await handler.generate_client_response(mock_req, mock_resp)

    @pytest.mark.asyncio
    async def test_call_remote_dispatch_function_raises_when_remote_raises(
        self, server_worker_config
    ) -> None:
        """
        Verifies that call_remote_dispatch_function raises RuntimeError when remote_function raises.

        This test verifies by:
        1. Creating HandlerConfig with remote_function that raises
        2. Calling call_remote_dispatch_function
        3. Asserting RuntimeError with "Error calling remote dispatch function"

        Assumptions:
        - Exception from remote is wrapped in RuntimeError
        """

        async def remote_raises(**kwargs):
            raise ValueError("remote failed")

        config = server_worker_config(
            "from_handlers",
            handlers=[
                HandlerConfig(
                    route="/remote",
                    benchmark_config=BenchmarkConfig(dataset=[{"a": 1}]),
                    remote_function=remote_raises,
                ),
            ],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/remote")
        with pytest.raises(RuntimeError):
            await handler.call_remote_dispatch_function({})

    @pytest.mark.asyncio
    async def test_generate_client_response_default_streaming_passthrough(
        self,
        server_worker_config,
        make_mock_web_request,
        make_mock_model_response,
    ) -> None:
        """
        Verifies that default generate_client_response uses streaming path for stream content-type.

        This test verifies by:
        1. Getting handler without response_generator
        2. Mocking model_response with content_type text/event-stream and async iter_any
        3. Patching web.StreamResponse to capture construction and avoid real aiohttp prepare
        4. Calling generate_client_response and asserting StreamResponse was created with status/content_type

        Assumptions:
        - When content_type indicates streaming, code creates StreamResponse and iterates model_response.content.iter_any
        - We patch StreamResponse to avoid real I/O while still exercising the streaming branch
        """
        from aiohttp import web

        config = server_worker_config("handler", route="/", dataset=[{"a": 1}])
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/")
        mock_req = make_mock_web_request(spec_request=False)
        # Empty chunk triggers continue in handler
        mock_model_resp = make_mock_model_response(
            content_type="text/event-stream",
            status=200,
            stream_chunks=[b"chunk1", b"", b"chunk2"],
        )

        with patch(
            "vastai.serverless.server.worker.web.StreamResponse"
        ) as mock_stream_cls:
            mock_stream = MagicMock()
            mock_stream.prepare = AsyncMock()
            mock_stream.write = AsyncMock()
            mock_stream.write_eof = AsyncMock()
            mock_stream.status = 200
            mock_stream.content_type = "text/event-stream"
            mock_stream_cls.return_value = mock_stream

            response = await handler.generate_client_response(mock_req, mock_model_resp)

        mock_stream_cls.assert_called_once()
        assert mock_stream_cls.call_args[1]["status"] == 200
        mock_stream.prepare.assert_called_once_with(mock_req)
        # chunk1, empty (skipped), chunk2
        assert mock_stream.write.call_count == 2
        mock_stream.write_eof.assert_called_once()
        assert response is mock_stream


class TestEndpointHandlerFactoryCustomHandlerClass:
    """Verify EndpointHandlerFactory uses handler_class when provided."""

    def test_factory_uses_handler_class_instance(self, server_worker_config) -> None:
        """
        Verifies that HandlerConfig with handler_class registers an instance of that class.

        This test verifies by:
        1. Defining a minimal concrete EndpointHandler subclass
        2. Creating WorkerConfig with HandlerConfig(route="/custom", handler_class=ThatClass)
        3. Creating factory and get_handler("/custom")
        4. Asserting returned handler is instance of ThatClass (and not GenericEndpointHandler)

        Assumptions:
        - When handler_class is not None, factory creates handler_class() and stores it
        """
        from vastai.serverless.server.lib.data_types import (
            EndpointHandler,
            ApiPayload,
            ClientResponse,
        )
        from aiohttp import web
        from dataclasses import dataclass
        from typing import Type, Optional, Union

        @dataclass
        class DummyPayload(ApiPayload):
            value: str = ""

            @classmethod
            def for_test(cls):
                return cls(value="test")

            def generate_payload_json(self):
                return {"value": self.value}

            def count_workload(self) -> float:
                return 1.0

            @classmethod
            def from_json_msg(cls, json_msg: dict):
                return cls(value=json_msg.get("value", ""))

        class DummyHandler(EndpointHandler[DummyPayload]):
            has_benchmark = False  # so only /bench is the benchmark handler

            @property
            def endpoint(self) -> str:
                return "/custom"

            @property
            def healthcheck_endpoint(self) -> Optional[str]:
                return None

            @classmethod
            def payload_cls(cls) -> Type[DummyPayload]:
                return DummyPayload

            def make_benchmark_payload(self) -> DummyPayload:
                return DummyPayload.for_test()

            async def generate_client_response(
                self,
                client_request: web.Request,
                model_response: ClientResponse,
            ) -> Union[web.Response, web.StreamResponse]:
                return web.Response(text="ok")

            async def call_remote_dispatch_function(self, params: dict):
                raise RuntimeError("not configured")

        config = server_worker_config(
            "from_handlers",
            handlers=[
                HandlerConfig(route="/custom", handler_class=DummyHandler),
                HandlerConfig(
                    route="/bench",
                    benchmark_config=BenchmarkConfig(dataset=[{"a": 1}]),
                ),
            ],
        )
        factory = EndpointHandlerFactory(config)
        custom_handler = factory.get_handler("/custom")
        assert custom_handler is not None
        assert isinstance(custom_handler, DummyHandler)
        assert custom_handler.endpoint == "/custom"
        # Benchmark handler is the /bench route (exactly one with BenchmarkConfig)
        assert factory.get_handler("/bench") is not None
