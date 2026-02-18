"""
Unit tests for vastai/serverless/server/worker.py

Tests the configuration dataclasses and EndpointHandlerFactory without network calls.
"""
import pytest
from unittest.mock import MagicMock
import sys
from pathlib import Path

# Add vast-cli to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vastai.serverless.server.worker import (
    LogActionConfig,
    BenchmarkConfig,
    HandlerConfig,
    WorkerConfig,
    EndpointHandlerFactory,
)
from vastai.serverless.server.lib.data_types import LogAction


class TestLogActionConfig:
    """Tests for LogActionConfig dataclass."""

    def test_default_empty_lists(self):
        """Default factory should create empty lists for all action types."""
        config = LogActionConfig()
        assert config.on_load == []
        assert config.on_error == []
        assert config.on_info == []

    def test_log_actions_on_load_converts_to_tuples(self):
        """on_load strings should convert to (LogAction.ModelLoaded, str) tuples."""
        config = LogActionConfig(on_load=["Server started"])
        actions = config.log_actions
        assert (LogAction.ModelLoaded, "Server started") in actions

    def test_log_actions_on_error_converts_to_tuples(self):
        """on_error strings should convert to (LogAction.ModelError, str) tuples."""
        config = LogActionConfig(on_error=["Critical failure"])
        actions = config.log_actions
        assert (LogAction.ModelError, "Critical failure") in actions

    def test_log_actions_on_info_converts_to_tuples(self):
        """on_info strings should convert to (LogAction.Info, str) tuples."""
        config = LogActionConfig(on_info=["Download progress"])
        actions = config.log_actions
        assert (LogAction.Info, "Download progress") in actions

    def test_log_actions_combined_all_types(self):
        """log_actions should combine all three action types."""
        config = LogActionConfig(
            on_load=["Model loaded", "Ready to serve"],
            on_error=["Load failed"],
            on_info=["Starting download"]
        )
        actions = config.log_actions
        assert len(actions) == 4
        assert (LogAction.ModelLoaded, "Model loaded") in actions
        assert (LogAction.ModelLoaded, "Ready to serve") in actions
        assert (LogAction.ModelError, "Load failed") in actions
        assert (LogAction.Info, "Starting download") in actions

    def test_log_actions_empty_returns_empty_list(self):
        """Empty config should return empty log_actions list."""
        config = LogActionConfig()
        assert config.log_actions == []


class TestBenchmarkConfig:
    """Tests for BenchmarkConfig dataclass."""

    def test_default_values(self):
        """Default values should be set correctly."""
        config = BenchmarkConfig()
        assert config.dataset is None
        assert config.generator is None
        assert config.runs == 8
        assert config.concurrency == 10

    def test_custom_dataset_stored(self):
        """Custom dataset should be stored."""
        test_data = [{"input": "test1"}, {"input": "test2"}]
        config = BenchmarkConfig(dataset=test_data)
        assert config.dataset == test_data

    def test_custom_generator_stored(self):
        """Custom generator function should be stored."""
        def my_generator():
            return {"input": "generated"}
        config = BenchmarkConfig(generator=my_generator)
        assert config.generator == my_generator

    def test_custom_runs_stored(self):
        """Custom runs value should be stored."""
        config = BenchmarkConfig(runs=16)
        assert config.runs == 16

    def test_custom_concurrency_stored(self):
        """Custom concurrency value should be stored."""
        config = BenchmarkConfig(concurrency=5)
        assert config.concurrency == 5


class TestHandlerConfig:
    """Tests for HandlerConfig dataclass."""

    def test_route_required_and_stored(self):
        """Route should be stored correctly."""
        config = HandlerConfig(route="/inference")
        assert config.route == "/inference"

    def test_default_allow_parallel_requests(self):
        """Default allow_parallel_requests should be False."""
        config = HandlerConfig(route="/")
        assert config.allow_parallel_requests is False

    def test_default_max_queue_time(self):
        """Default max_queue_time should be 30.0."""
        config = HandlerConfig(route="/")
        assert config.max_queue_time == 30.0

    def test_default_benchmark_config_none(self):
        """Default benchmark_config should be None."""
        config = HandlerConfig(route="/")
        assert config.benchmark_config is None

    def test_default_handler_class_none(self):
        """Default handler_class should be None."""
        config = HandlerConfig(route="/")
        assert config.handler_class is None

    def test_default_payload_class_none(self):
        """Default payload_class should be None."""
        config = HandlerConfig(route="/")
        assert config.payload_class is None

    def test_default_request_parser_none(self):
        """Default request_parser should be None."""
        config = HandlerConfig(route="/")
        assert config.request_parser is None

    def test_default_response_generator_none(self):
        """Default response_generator should be None."""
        config = HandlerConfig(route="/")
        assert config.response_generator is None

    def test_default_workload_calculator_none(self):
        """Default workload_calculator should be None."""
        config = HandlerConfig(route="/")
        assert config.workload_calculator is None

    def test_custom_values_stored(self):
        """Custom values should be stored correctly."""
        benchmark = BenchmarkConfig(runs=5)
        config = HandlerConfig(
            route="/custom",
            allow_parallel_requests=True,
            max_queue_time=60.0,
            benchmark_config=benchmark
        )
        assert config.route == "/custom"
        assert config.allow_parallel_requests is True
        assert config.max_queue_time == 60.0
        assert config.benchmark_config == benchmark


class TestWorkerConfig:
    """Tests for WorkerConfig dataclass."""

    def test_default_handlers_empty_list(self):
        """Default handlers should be empty list."""
        config = WorkerConfig()
        assert config.handlers == []

    def test_default_log_action_config(self):
        """Default log_action_config should be LogActionConfig instance."""
        config = WorkerConfig()
        assert isinstance(config.log_action_config, LogActionConfig)

    def test_default_model_server_url_none(self):
        """Default model_server_url should be None."""
        config = WorkerConfig()
        assert config.model_server_url is None

    def test_default_model_server_port_none(self):
        """Default model_server_port should be None."""
        config = WorkerConfig()
        assert config.model_server_port is None

    def test_default_model_log_file_none(self):
        """Default model_log_file should be None."""
        config = WorkerConfig()
        assert config.model_log_file is None

    def test_default_model_healthcheck_url_none(self):
        """Default model_healthcheck_url should be None."""
        config = WorkerConfig()
        assert config.model_healthcheck_url is None

    def test_custom_values_stored(self):
        """Custom values should be stored correctly."""
        handler = HandlerConfig(route="/inference")
        log_config = LogActionConfig(on_load=["Ready"])
        config = WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
            model_log_file="/var/log/model.log",
            model_healthcheck_url="http://localhost:8000/health",
            handlers=[handler],
            log_action_config=log_config
        )
        assert config.model_server_url == "http://localhost"
        assert config.model_server_port == 8000
        assert config.model_log_file == "/var/log/model.log"
        assert config.model_healthcheck_url == "http://localhost:8000/health"
        assert config.handlers == [handler]
        assert config.log_action_config == log_config


class TestEndpointHandlerFactory:
    """Tests for EndpointHandlerFactory class."""

    def test_default_handler_created_when_no_handlers(self):
        """Factory should create a default handler at '/' when no handlers configured."""
        config = WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
        )
        factory = EndpointHandlerFactory(config)
        assert factory.has_handlers() is True
        assert "/" in factory.get_all_handlers()

    def test_get_handler_returns_handler_for_route(self):
        """get_handler should return handler for registered route."""
        config = WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/")
        assert handler is not None

    def test_get_handler_returns_none_for_unknown_route(self):
        """get_handler should return None for unregistered route."""
        config = WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
        )
        factory = EndpointHandlerFactory(config)
        assert factory.get_handler("/unknown") is None

    def test_get_all_handlers_returns_copy(self):
        """get_all_handlers should return a copy of handlers dict."""
        config = WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
        )
        factory = EndpointHandlerFactory(config)
        handlers = factory.get_all_handlers()
        # Modifying returned dict shouldn't affect internal state
        handlers["/test"] = "fake_handler"
        assert "/test" not in factory.get_all_handlers()

    def test_has_handlers_returns_true_when_handlers_exist(self):
        """has_handlers should return True when handlers are registered."""
        config = WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
        )
        factory = EndpointHandlerFactory(config)
        assert factory.has_handlers() is True

    def test_model_server_base_url_property(self):
        """model_server_base_url should return formatted URL with port."""
        config = WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
        )
        factory = EndpointHandlerFactory(config)
        assert factory.model_server_base_url == "http://localhost:8000"

    def test_builds_handlers_from_config_list(self):
        """Factory should build handlers from config handlers list."""
        handler_configs = [
            HandlerConfig(route="/inference"),
            HandlerConfig(route="/health"),
        ]
        config = WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
            handlers=handler_configs,
        )
        factory = EndpointHandlerFactory(config)
        handlers = factory.get_all_handlers()
        assert "/inference" in handlers
        assert "/health" in handlers

    def test_handler_uses_config_allow_parallel_requests(self):
        """Created handler should use allow_parallel_requests from config."""
        handler_config = HandlerConfig(
            route="/test",
            allow_parallel_requests=True,
        )
        config = WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
            handlers=[handler_config],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/test")
        assert handler.allow_parallel_requests is True

    def test_handler_uses_config_max_queue_time(self):
        """Created handler should use max_queue_time from config."""
        handler_config = HandlerConfig(
            route="/test",
            max_queue_time=60.0,
        )
        config = WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
            handlers=[handler_config],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/test")
        assert handler.max_queue_time == 60.0

    def test_handler_endpoint_property_returns_route(self):
        """Handler's endpoint property should return the route."""
        handler_config = HandlerConfig(route="/inference")
        config = WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
            handlers=[handler_config],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/inference")
        assert handler.endpoint == "/inference"

    def test_get_benchmark_handler_returns_handler_with_benchmark(self):
        """get_benchmark_handler should return handler with BenchmarkConfig."""
        benchmark = BenchmarkConfig(
            dataset=[{"input": "test"}],
            runs=4,
            concurrency=2,
        )
        handler_config = HandlerConfig(
            route="/inference",
            benchmark_config=benchmark,
        )
        config = WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
            handlers=[handler_config],
        )
        factory = EndpointHandlerFactory(config)
        benchmark_handler = factory.get_benchmark_handler()
        assert benchmark_handler is not None
        assert benchmark_handler.has_benchmark is True

    def test_get_benchmark_handler_raises_when_missing(self):
        """get_benchmark_handler should raise when no BenchmarkConfig exists."""
        handler_config = HandlerConfig(route="/test")
        config = WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
            handlers=[handler_config],
        )
        factory = EndpointHandlerFactory(config)
        with pytest.raises(Exception, match="Missing EndpointHandler with BenchmarkConfig"):
            factory.get_benchmark_handler()

    def test_get_benchmark_handler_raises_when_multiple(self):
        """get_benchmark_handler should raise when multiple BenchmarkConfigs exist."""
        benchmark1 = BenchmarkConfig(dataset=[{"input": "test1"}])
        benchmark2 = BenchmarkConfig(dataset=[{"input": "test2"}])
        handler_configs = [
            HandlerConfig(route="/inference1", benchmark_config=benchmark1),
            HandlerConfig(route="/inference2", benchmark_config=benchmark2),
        ]
        config = WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
            handlers=handler_configs,
        )
        factory = EndpointHandlerFactory(config)
        with pytest.raises(Exception, match="Cannot define BenchmarkConfig for more than one"):
            factory.get_benchmark_handler()


class TestHandlerBenchmarkProperties:
    """Tests for handler benchmark-related properties."""

    def test_handler_has_benchmark_false_without_config(self):
        """Handler should have has_benchmark=False without BenchmarkConfig."""
        handler_config = HandlerConfig(route="/test")
        config = WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
            handlers=[handler_config],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/test")
        assert handler.has_benchmark is False

    def test_handler_has_benchmark_true_with_config(self):
        """Handler should have has_benchmark=True with BenchmarkConfig."""
        benchmark = BenchmarkConfig(dataset=[{"input": "test"}])
        handler_config = HandlerConfig(
            route="/test",
            benchmark_config=benchmark,
        )
        config = WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
            handlers=[handler_config],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/test")
        assert handler.has_benchmark is True

    def test_handler_benchmark_runs_from_config(self):
        """Handler should use runs value from BenchmarkConfig."""
        benchmark = BenchmarkConfig(dataset=[{"input": "test"}], runs=16)
        handler_config = HandlerConfig(
            route="/test",
            benchmark_config=benchmark,
        )
        config = WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
            handlers=[handler_config],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/test")
        assert handler.benchmark_runs == 16

    def test_handler_concurrency_from_config(self):
        """Handler should use concurrency value from BenchmarkConfig."""
        benchmark = BenchmarkConfig(dataset=[{"input": "test"}], concurrency=5)
        handler_config = HandlerConfig(
            route="/test",
            benchmark_config=benchmark,
        )
        config = WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
            handlers=[handler_config],
        )
        factory = EndpointHandlerFactory(config)
        handler = factory.get_handler("/test")
        assert handler.concurrency == 5
