from vastai import Worker, WorkerConfig, HandlerConfig, LogActionConfig, BenchmarkConfig

# vLLM model configuration
MODEL_SERVER_URL           = 'http://127.0.0.1'
MODEL_SERVER_PORT          = 8080
MODEL_LOG_FILE             = '/var/log/model.log'
MODEL_HEALTHCHECK_ENDPOINT = "/health"

# vLLM-specific log messages
MODEL_LOAD_LOG_MSG = [
    "Model Server Running",
]

MODEL_ERROR_LOG_MSGS = [
    "Traceback (most recent call last):"
]

benchmark_dataset = [
    {
        "max_train_batches_per_epoch" : 10
    }
]

worker_config = WorkerConfig(
    model_server_url=MODEL_SERVER_URL,
    model_server_port=MODEL_SERVER_PORT,
    model_log_file=MODEL_LOG_FILE,
    model_healthcheck_url=MODEL_HEALTHCHECK_ENDPOINT,
    handlers=[
        HandlerConfig(
            route="/start_task",
            benchmark_config=BenchmarkConfig(
                dataset=benchmark_dataset, runs=1
            )
        ),
        HandlerConfig(route="/status"),
        HandlerConfig(route="/cancel_task"),
    ],
    log_action_config=LogActionConfig(
        on_load=MODEL_LOAD_LOG_MSG,
        on_error=MODEL_ERROR_LOG_MSGS
    )
)

Worker(worker_config).run()