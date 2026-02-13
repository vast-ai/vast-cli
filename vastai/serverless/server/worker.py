from vastai.serverless.server.lib import backend, server
from vastai.serverless.server.lib.data_types import ApiPayload, EndpointHandler, LogAction, JsonDataException
from dataclasses import dataclass, field
from aiohttp import web, ClientResponse
import logging
import json
import random
import logging
from typing import Optional, Dict, Callable, Awaitable, Union, Any, Type

# Callable types
RequestPayloadParser = Callable[[Dict[str, Any]], Dict[str, Any]]
ClientResponseGenerator = Callable[[web.Request, ClientResponse], Awaitable[Union[web.Response, web.StreamResponse]]]
WorkloadCalculator = Callable[[Dict[str, Any]], float]

@dataclass
class LogActionConfig:
    """Configuration for defining log actions"""
    on_load: list[str] = field(default_factory=list)
    on_error: list[str] = field(default_factory=list)
    on_info: list[str] = field(default_factory=list)

    @property
    def log_actions(self) -> list[LogAction]:
        log_actions_ = []
        log_actions_.extend([(LogAction.ModelLoaded, log) for log in self.on_load])
        log_actions_.extend([(LogAction.ModelError,  log) for log in self.on_error])
        log_actions_.extend([(LogAction.Info,        log) for log in self.on_info])
        return log_actions_
    
@dataclass
class BenchmarkConfig:
    """Configuration for defining a benchmark"""
    dataset: list[dict] | None = None
    generator: Callable[[], dict] | None = None  # optional sample factory
    runs: int = 8
    concurrency: int | None = 10

@dataclass
class HandlerConfig:
    """Configuration for defining handlers"""
    route: str
    allow_parallel_requests: bool = False
    max_queue_time: Optional[float] = 30.0
    benchmark_config: Optional[BenchmarkConfig] = None
    handler_class: Optional[Type[EndpointHandler]] = None
    payload_class: Optional[Type[ApiPayload]] = None
    request_parser: Optional[RequestPayloadParser] = None
    response_generator: Optional[ClientResponseGenerator] = None
    workload_calculator: Optional[WorkloadCalculator] = None


@dataclass
class WorkerConfig:
    model_server_url: str = None
    model_server_port: int = None
    model_log_file: str = None
    model_healthcheck_url: str = None
    handlers: list[HandlerConfig] = field(default_factory=list)
    log_action_config: LogActionConfig = field(default_factory=LogActionConfig)


class EndpointHandlerFactory:
    """Factory for creating endpoint handlers from WorkerConfig"""
    
    def __init__(self, config: WorkerConfig):
        self.config = config
        self._handlers: Dict[str, EndpointHandler] = {}
        self._build_handlers()
    
    def _build_handlers(self) -> None:
        """Build endpoint handlers from config"""
        # If no handlers, create a default handler at /
        if not self.config.handlers:
            default_handler_config = HandlerConfig(
                route="/",
            )
            handler = self._create_handler(default_handler_config)
            self._handlers["/"] = handler
        else:
            # Build handlers from config
            for handler_config in self.config.handlers:
                # TODO: Override values from handler class with HandlerConfig values
                if handler_config.handler_class is not None:
                    # Use custom handler class
                    handler = handler_config.handler_class()
                    self._handlers[handler_config.route] = handler
                    continue
                handler = self._create_handler(handler_config)
                self._handlers[handler_config.route] = handler
    
    def _create_handler(self, handler_config: HandlerConfig) -> EndpointHandler:
        """Create a generic endpoint handler from HandlerConfig"""
        
        # Extract config values with defaults
        route_path = handler_config.route
        benchmark_config = handler_config.benchmark_config
        user_payload_class = handler_config.payload_class
        user_request_parser = handler_config.request_parser
        user_response_generator = handler_config.response_generator
        user_workload_calculator = handler_config.workload_calculator
        
        # If user provided a custom payload class, use it
        if user_payload_class:
            PayloadClass = user_payload_class
        else:
            # Create a generic ApiPayload class
            @dataclass
            class GenericApiPayload(ApiPayload):
                input: Dict[str, Any] = field(default_factory=dict)
                
                @classmethod
                def for_test(cls) -> "GenericApiPayload":
                    # Use random.choice from benchmark_data if available
                    if benchmark_config:
                        if benchmark_config.dataset:
                            test_data = random.choice(benchmark_config.dataset)
                        elif benchmark_config.generator:
                            try:
                                test_data = benchmark_config.generator()
                            except Exception as ex:
                                raise(Exception(f"Error generating benchmark data for \"{handler_config.route}\" handler: {ex}"))
                    else:
                        raise(Exception(f"Error generating benchmark data for \"{handler_config.route}\" handler: Missing BenchmarkConfig!"))
                    return cls(input=test_data.copy())
                
                def generate_payload_json(self) -> Dict[str, Any]:
                    return self.input
                

                @classmethod
                def from_dict(cls, input: Dict[str, Any]) -> "GenericApiPayload":
                    return cls(input=input)

                def count_workload(self) -> float:
                    # Use custom workload calculator if provided
                    if user_workload_calculator:
                        return user_workload_calculator(self.input)
                    # Default to 100 unless overridden
                    return 100.0
                
                @classmethod
                def from_json_msg(cls, json_msg: Dict[str, Any]) -> "GenericApiPayload":
                    if not isinstance(json_msg, dict):
                        raise JsonDataException({"data": "payload must be a dictionary"})
                    
                    # Apply user's request parser if provided
                    if user_request_parser:
                        try:
                            json_msg = user_request_parser(json_msg)
                        except Exception as e:
                            raise Exception(f"Error in user response handler: {e}")
                        
                    try:
                        return cls.from_dict(json_msg)
                    except (json.JSONDecodeError, JsonDataException) as e:
                        raise JsonDataException(f"Error in user response handler: {e}")

            
            PayloadClass = GenericApiPayload
        
        # Create a generic EndpointHandler class
        @dataclass
        class GenericEndpointHandler(EndpointHandler[PayloadClass]):
            _route: str = field(default=route_path)
            has_benchmark: bool = field(
                default=(
                    True if handler_config.benchmark_config
                    else False
                )
            )
            allow_parallel_requests: bool = field(
                default=handler_config.allow_parallel_requests
            )
            max_queue_time: float = field(
                default=handler_config.max_queue_time
            )
            benchmark_runs: int = field(
                default=(
                    handler_config.benchmark_config.runs
                    if handler_config.benchmark_config
                    else 8
                )
            )
            concurrency: int = field(
                default=(
                    handler_config.benchmark_config.concurrency
                    if handler_config.benchmark_config and handler_config.benchmark_config.concurrency
                    else 10
                )
            )
            @property
            def endpoint(self) -> str:
                """The endpoint is the same as the route"""
                return self._route

            @property
            def healthcheck_endpoint(self) -> Optional[str]:
                return None
            
            @classmethod
            def payload_cls(cls) -> Type[PayloadClass]:
                return PayloadClass
            
            def make_benchmark_payload(self) -> PayloadClass:
                """Just call the payload class's for_test() method"""
                return PayloadClass.for_test()
            
            async def generate_client_response(
                self,
                client_request: web.Request,
                model_response: ClientResponse,
            ) -> Union[web.Response, web.StreamResponse]:
                # User implemented override
                if user_response_generator:
                    try:
                        return await user_response_generator(client_request, model_response)
                    except Exception as e:
                        raise Exception(f"Error in user response generator: {e}")

                # Reasonable default: return response, handle streaming if present
                # Detect streaming
                content_type = model_response.content_type or ""
                is_stream = (
                    content_type.startswith("text/event-stream") or
                    content_type in ("application/x-ndjson", "application/jsonl") or
                    "stream" in content_type.lower()
                ) or (model_response.headers.get("Transfer-Encoding") == "chunked")

                if is_stream:
                    # Streaming passthrough
                    res = web.StreamResponse(
                        status=model_response.status,
                    )
                    if content_type:
                        res.content_type = content_type

                    await res.prepare(client_request)

                    async for chunk in model_response.content.iter_any():
                        if not chunk:
                            continue
                        await res.write(chunk)

                    await res.write_eof()
                    return res
                else:
                    # Non-streaming
                    body = await model_response.read()

                    headers = model_response.headers.copy()
                    headers.pop("Content-Type", None)

                    return web.Response(
                        body=body,
                        status=model_response.status,
                        content_type=content_type or None,
                        headers=headers,
                    )
        
        return GenericEndpointHandler()
    
    def get_handler(self, route: str) -> Optional[EndpointHandler]:
        """Get handler for a specific route"""
        return self._handlers.get(route)
    
    def get_all_handlers(self) -> Dict[str, EndpointHandler]:
        """Get all registered handlers"""
        return self._handlers.copy()
    
    def get_benchmark_handler(self) -> Optional[EndpointHandler]:
        """
        Get the benchmark handler. 
        Raises errors if there are too many / too little BenchmarkConfigs
        Should be exactly one EndpointHandler with a BenchmarkConfig
        """
        if not self._handlers:
            return None

        benchmark_handler: EndpointHandler = None
        for handler in self._handlers.values():
            if handler.has_benchmark:
                if benchmark_handler is not None:
                    raise Exception("Cannot define BenchmarkConfig for more than one EndpointHandler!")
                else:
                    benchmark_handler = handler
        if not benchmark_handler:
            raise Exception("Missing EndpointHandler with BenchmarkConfig")
        return benchmark_handler
    
    def has_handlers(self) -> bool:
        """Check if any handlers are registered"""
        return len(self._handlers) > 0
    
    @property
    def model_server_base_url(self) -> str:
        """Get the full model server base URL"""
        return f"{self.config.model_server_url}:{self.config.model_server_port}"
    
class Worker:
    """
    This class provides a simple to use abstraction over the pyworker backend.
    All custom implementations of pyworker can be created by configuring a Worker object.
    The pyworker starts by calling Worker.run()
    """

    def __init__(self, config: WorkerConfig):
        
        # Configure logging for the pyworker internals
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s[%(levelname)-5s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        
        handler_factory = EndpointHandlerFactory(config)
        
        # Get all endpoint handlers
        handlers = handler_factory.get_all_handlers()
        benchmark_handler = handler_factory.get_benchmark_handler()
        
        # Create backend
        self.backend = backend.Backend(
            model_server_url=f"{config.model_server_url}:{config.model_server_port}",
            model_log_file=config.model_log_file,
            benchmark_handler=benchmark_handler,
            log_actions=config.log_action_config.log_actions,
            healthcheck_url=config.model_healthcheck_url
        )
        
        # Attach endpoint handlers to HTTP routes
        self.routes = []
        for route_path, handler in handlers.items():
            self.routes.append(
                web.post(route_path, self.backend.create_handler(handler))
            )
        
    async def run_async(self, **kwargs):
        await server.start_server_async(self.backend, self.routes, **kwargs)

    def run(self, **kwargs):
        server.start_server(self.backend, self.routes, **kwargs)

