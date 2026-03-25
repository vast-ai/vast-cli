import nltk
import random

from vastai import Worker, WorkerConfig, HandlerConfig, LogActionConfig, BenchmarkConfig

# TGI model configuration
MODEL_SERVER_URL           = 'http://0.0.0.0'
MODEL_SERVER_PORT          = 5001
MODEL_LOG_FILE             = "/workspace/infer.log"
MODEL_HEALTHCHECK_ENDPOINT = "/health"

# TGI-specific log messages
MODEL_LOAD_LOG_MSG = [
    '"message":"Connected","target":"text_generation_router"',
    '"message":"Connected","target":"text_generation_router::server"',
]

MODEL_ERROR_LOG_MSGS = [
    "Error: WebserverFailed",
    "Error: DownloadError",
    "Error: ShardCannotStart",
]

MODEL_INFO_LOG_MSGS = [
    '"message":"Download'
]

nltk.download("words")
WORD_LIST = nltk.corpus.words.words()


def benchmark_generator() -> dict:
    prompt = " ".join(random.choices(WORD_LIST, k=int(250)))

    benchmark_data = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 128,
            "temperature": 0.7,
            "return_full_text": False
        }
    }

    return benchmark_data

worker_config = WorkerConfig(
    model_server_url=MODEL_SERVER_URL,
    model_server_port=MODEL_SERVER_PORT,
    model_log_file=MODEL_LOG_FILE,
    model_healthcheck_url=MODEL_HEALTHCHECK_ENDPOINT,
    handlers=[
        HandlerConfig(
            route="/generate",
            allow_parallel_requests=True,
            max_queue_time=60.0,
            benchmark_config=BenchmarkConfig(
                generator=benchmark_generator,
                concurrency=50
            ),
            workload_calculator= lambda x: x["parameters"]["max_new_tokens"]
        ),
        HandlerConfig(
            route="/generate_stream",
            allow_parallel_requests=True,
            max_queue_time=60.0,
            workload_calculator= lambda x: x["parameters"]["max_new_tokens"]
        )
    ],
    log_action_config=LogActionConfig(
        on_load=MODEL_LOAD_LOG_MSG,
        on_error=MODEL_ERROR_LOG_MSGS,
        on_info=MODEL_INFO_LOG_MSGS
    )
)

Worker(worker_config).run()