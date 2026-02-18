from vastai import Worker, WorkerConfig, HandlerConfig, BenchmarkConfig, LogActionConfig

# We define a WorkerConfig object to configure our PyWorker
# Here, we can implement handlers for different routes our
# endpoint may serve
worker_config = WorkerConfig(
    # --- Model Config ---
    # The local URL of your model
    model_server_url="http://127.0.0.1",
    # The port your model is running on
    model_server_port=18000,
    # The file your model writes logs to
    model_log_file="/var/model/out.log",
    # If your model responds to a healthcheck, you can specify it here
    model_healthcheck_url="/health",

    # --- Handler Config ---
    # Here, we define potentially multiple endpoint handlers for our endpoint,
    # each of which services a different route on our endpoint
    handlers=[
        HandlerConfig(
            # The route on our endpoint that we are handling
            route="/my/route",
            # Enable this if the model backend supports handling multiple requests at once
            # If 'False', the worker will enforce one request at a time on the
            # model backend with strict FIFO ordering.
            allow_parallel_requests=False,
            # --- Benchmark config ---
            # One endpoint handler must implement a BenchmarkConfig
            # The BenchmarkConfig defines sample payloads we use for
            # measuring the performance of any given machine.
            # This is essential for correct optimal autoscaling behavior.
            benchmark_config=BenchmarkConfig(
                # A list of possible request payloads to benchmark on
                dataset=[
                    { "prompt" : "some" },
                    { "prompt" : "sample" },
                    { "prompt" : "data" }
                ],
                # You may also implement a `generator` function, which
                # returns a benchmark payload dictionary
                # generator= lambda: { "prompt" : "a" * random.randint(60) }

                # How many times you should run the benchmark
                runs= 5,

                # If `allow_parallel_requests` == True, how many concurrent payloads per run
                concurrency=10 
            ),
            # A function that calculates the workload per request
            # Example: the length of the input data
            workload_calculator= lambda request: len(request["prompt"])
        )
    ],

    # --- Log Config ---
    # Here, we define various LogActions, which inform our worker
    # of model start, model error, or useful model information.
    # It's important that your model outputs logs to the file
    # specified in `model_log_file`, so the worker knows the state
    # of the model and can react accordingly.
    log_action_config=LogActionConfig(
        # A log line from our model that indicates
        # the model has completed loading and is ready
        # to recieve requests
        on_load=[
            "Application startup complete.",
        ],
        # The log lines from our model that indicate
        # the model has suffered an irrecoverable error
        # and our worker must be restarted
        on_error=[
            "INFO exited: vllm",
            "RuntimeError: Engine",
            "Traceback (most recent call last):"
        ],
        # A log line the model may emit
        # containing relevant information
        on_info=[
            '"message":"Download'
        ]
    )
)

# --- Running the Worker ---
# Run the worker synchronously
Worker(worker_config).run()

# Or, if you wish to continue executing Python from this entrypoint,
# you can run your PyWorker in an asyncio background task
# pyworker_task = asyncio.run(Worker(worker_config).run_async())
# ... more python here ...