#!/usr/bin/env python3
import os
import inspect
import functools
import asyncio
import requests
import aiofiles
import sys
import time
import logging
import hashlib
import io
import shlex
import tarfile

from vastai.serverless.remote.serialization import serialize, deserialize

from typing import Optional
from anyio import Path


API_URL = os.getenv("VAST_API_BASE", "https://console.vast.ai")

mode = os.getenv("VAST_DEPLOYMENT_MODE", "client")
debug = os.getenv("VAST_DEBUG", "") == "1"


def _setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    if debug:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('[%(asctime)s] %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
    else:
        logger.propagate = True
    return logger


REMOTE_FUNCTIONS_BY_ENDPOINT_NAME = {}
BENCHMARK_CONFIG_BY_ENDPOINT_NAME = {}


def get_mode():
    return mode


def _add_file_to_tar(tar, filepath, arcname):
    """Add a file to a tar archive with deterministic metadata."""
    info = tar.gettarinfo(filepath, arcname=arcname)
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    with open(filepath, 'rb') as f:
        tar.addfile(info, f)


def _add_string_to_tar(tar, content, arcname):
    """Add a string as a file to a tar archive with deterministic metadata."""
    data = content.encode('utf-8')
    info = tarfile.TarInfo(name=arcname)
    info.size = len(data)
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    tar.addfile(info, io.BytesIO(data))


def remote(endpoint_name: str):
    """
    Decorator that converts a function into a remote call to a Vast.ai endpoint.

    Args:
        endpoint_name: The name of the endpoint to call

    Example:
        @remote(endpoint_name="my-endpoint")
        def my_function(a: int, b: str) -> dict:
            return {"result": f"{a} {b}"}

        # When called, it will make a request to the endpoint
        result = await my_function(a=1, b="hello")
    """
    def decorator(func):
        func_name = func.__name__
        func_mod = func.__globals__['__name__']
        func_globals = func.__globals__
        sig = inspect.signature(func)
        if get_mode() == "client":
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                from vastai import Serverless

                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()

                payload = {
                    "input": {
                        k: serialize(v, func_mod) for k, v in bound_args.arguments.items()
                    }
                }

                print("Payload: ", payload)

                async with Serverless() as client:
                    snapshot_time = time.time()
                    endpoint = await client.get_endpoint(name=endpoint_name)
                    response = await endpoint.request(f"/remote/{func_name}", payload)
                    time_elapsed = time.time() - snapshot_time
                    print(f"Time elapsed: {time_elapsed} seconds")
                    if response["response"]["result"] is not None:
                        return deserialize(response["response"]["result"], func_mod, func_globals)
                    else:
                        return deserialize(response["response"], func_mod, func_globals)

            return async_wrapper
        elif get_mode() == "serve":
            funcs_for_endpoint = REMOTE_FUNCTIONS_BY_ENDPOINT_NAME.setdefault(
                endpoint_name, {}
            )

            async def inner(*args, **kwargs):
                args_ = [deserialize(a, func_mod, func_globals) for a in args]
                kwargs_ = {k: deserialize(v, func_mod, func_globals) for k, v in kwargs.items()}
                return serialize(await func(*args_, **kwargs_), func_mod)
            funcs_for_endpoint[func_name] = inner
            return func

        return func

    return decorator


def benchmark(
    endpoint_name: str,
    *,
    dataset: list[dict] | None = None,
    generator=None,
):
    """
    Decorator to mark a remote function as the benchmark function for an endpoint.

    Exactly one of `dataset` or `generator` should be provided.
    """
    if dataset is not None and generator is not None:
        raise ValueError("Specify either dataset or generator, not both")
    if dataset is None and generator is None:
        raise ValueError("Must specify either dataset or generator")
    if dataset is not None and not isinstance(dataset, list):
        raise TypeError("dataset must be a list of dicts")

    def decorator(func):
        func_mod = func.__globals__['__name__']
        nonlocal dataset
        nonlocal generator
        if dataset is not None:
            dataset = [{k: serialize(v, func_mod) for k, v in datum.items()} for datum in dataset]
        if generator is not None:
            generator = (lambda: {k: serialize(v, func_mod) for k, v in generator().items()})
        func_name = func.__name__

        BENCHMARK_CONFIG_BY_ENDPOINT_NAME[endpoint_name] = {
            "function_name": func_name,
            "dataset": dataset or [],
            "generator": generator,
        }

        return func

    return decorator


class Deployment:
    def __init__(
        self,
        name: str,
        tag: str = "default",
        image_name: str = "vastai/base-image:@vastai-automatic-tag",
        env_vars: dict = {},
        search_params: str = "",
        disk_space: int = 32,
        cold_workers: int = 5,
        max_workers: int = 16,
        min_load: int = 1,
        min_cold_load: int = 0,
        target_util: float = 0.9,
        cold_mult: int = 3,
        max_queue_time: Optional[float] = None,
        target_queue_time: Optional[float] = None,
        inactivity_timeout: Optional[float] = None,
        autoscaler_instance: str = "",
        ttl: Optional[float] = None,
        version_label: Optional[str] = None,
        # Worker configuration
        model_log_file: str = "/var/log/remote/debug.log",
        model_backend_load_logs: list = ["Deployment ready"],
        model_backend_error_logs: list = ["Deployment error"],
        model_healthcheck_endpoint: str = "health",
        secrets: list[str] = [],
    ):
        self.logger = _setup_logger("Deployment")

        # --- Deployment identity ---
        self.name = name
        self.tag = tag

        # --- Scaling configuration ---
        self.cold_workers = cold_workers
        self.max_workers = max_workers
        self.min_load = min_load
        self.min_cold_load = min_cold_load
        self.target_util = target_util
        self.cold_mult = cold_mult
        self.max_queue_time = max_queue_time
        self.target_queue_time = target_queue_time
        self.inactivity_timeout = inactivity_timeout
        self.autoscaler_instance = autoscaler_instance
        self.ttl = ttl
        self.version_label = version_label

        # --- Template configuration ---
        self.image_name = image_name
        self.env_vars = env_vars
        self.search_params = search_params
        self.disk_space = disk_space

        # --- Setup commands (become on_start.sh in tar) ---
        self.__onstart_cmd = ""
        self.__pip_packages_requested = False

        # --- Secrets (list of env var names, resolved from os.environ at deploy time) ---
        self.secrets = list(secrets)

        # --- Worker configuration ---
        self.remote_functions = REMOTE_FUNCTIONS_BY_ENDPOINT_NAME.get(name, {})
        benchmark_cfg = BENCHMARK_CONFIG_BY_ENDPOINT_NAME.get(name)
        self.benchmark_function_name = None
        self.benchmark_dataset = []
        self.benchmark_generator = None
        if benchmark_cfg:
            self.benchmark_function_name = benchmark_cfg["function_name"]
            self.benchmark_dataset = benchmark_cfg["dataset"]
            self.benchmark_generator = benchmark_cfg["generator"]
        self.model_log_file = model_log_file
        self.model_healthcheck_endpoint = model_healthcheck_endpoint
        self.on_init_function = None
        self.background_task = None
        self.model_backend_load_logs = model_backend_load_logs
        self.model_backend_error_logs = model_backend_error_logs

        # --- Deployment result state ---
        self.deployment_id = None
        self.endpoint_id = None

        # Capture the file path of the script that created this Deployment
        # (the caller's module, i.e. deployment.py)
        caller_frame = inspect.stack()[1]
        self._deployment_script_path = os.path.abspath(caller_frame.filename)

    # --- Setup methods (build on_start.sh content) ---

    def apt_get(self, packages: list[str]):
        packages_str = " ".join(packages)
        self.__onstart_cmd += f"apt-get install -y {packages_str}\n"

    def uv_pip_install(self, packages: list[str]):
        if not self.__pip_packages_requested:
            self.__onstart_cmd += "curl -LsSf https://astral.sh/uv/install.sh | sh && uv venv && source .venv/bin/activate\n"
            self.__pip_packages_requested = True
        packages_str = " ".join(packages)
        self.__onstart_cmd += f"uv pip install {packages_str}\n"

    def on_start(self, cmd: str):
        self.__onstart_cmd += f"{cmd}\n"

    def set_env_vars(self, vars: dict[str, str]):
        self.env_vars.update(vars)

    def set_secrets(self, keys: list[str]):
        """Set secret env var names. Values are resolved from os.environ at deploy time
        and bundled in the tar.gz only (not stored in DB)."""
        self.secrets.extend(keys)

    # --- Deploy ---

    def _build_env_string(self):
        """Convert env_vars dict to Docker -e format string."""
        parts = ["-p 3000:3000"]
        for k, v in self.env_vars.items():
            parts.append(f"-e {k}={v}")
        return " ".join(parts)

    def _build_tar_payload(self):
        """Build tar.gz containing deployment.py, on_start.sh, and .secrets."""
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w:gz') as tar:
            # 1. deployment.py
            _add_file_to_tar(tar, self._deployment_script_path, arcname="deployment.py")

            # 2. on_start.sh (if any setup commands were specified)
            if self.__onstart_cmd.strip():
                onstart_content = f"#!/bin/bash\nset -e\n{self.__onstart_cmd}"
                _add_string_to_tar(tar, onstart_content, arcname="on_start.sh")

            # 3. .secrets (resolve key names from current os.environ)
            if self.secrets:
                secrets_lines = []
                for key in self.secrets:
                    val = os.environ.get(key)
                    if val is None:
                        self.logger.warning(f"Secret '{key}' not found in environment, skipping")
                        continue
                    secrets_lines.append(f"export {key}={shlex.quote(val)}")
                if secrets_lines:
                    secrets_content = "\n".join(secrets_lines) + "\n"
                    _add_string_to_tar(tar, secrets_content, arcname=".secrets")

        payload = buf.getvalue()
        file_hash = hashlib.sha256(payload).hexdigest()
        file_size = len(payload)
        return payload, file_hash, file_size

    def deploy(self):
        """Package code and deploy via PUT /api/v0/deployments/. Upload to S3 if needed."""
        api_key = os.environ.get("VAST_API_KEY")
        if not api_key:
            raise ValueError("VAST_API_KEY environment variable is not set")

        self.logger.info(f"Deploying '{self.name}' (tag={self.tag})")

        # Build tar.gz payload
        payload, file_hash, file_size = self._build_tar_payload()
        self.logger.debug(f"Payload: {file_size} bytes, hash={file_hash}")

        # PUT /api/v0/deployments/
        body = {
            "name": self.name,
            "tag": self.tag,
            "image": self.image_name,
            "file_hash": file_hash,
            "file_size": file_size,
            "storage": self.disk_space,
            "cold_workers": self.cold_workers,
            "max_workers": self.max_workers,
        }

        # Optional fields
        if self.search_params:
            body["search_params"] = self.search_params
        if self.env_vars:
            body["env"] = self._build_env_string()
        if self.ttl is not None:
            body["ttl"] = self.ttl
        if self.version_label:
            body["version_label"] = self.version_label
        if self.min_load is not None:
            body["min_load"] = self.min_load
        if self.min_cold_load is not None:
            body["min_cold_load"] = self.min_cold_load
        if self.target_util is not None:
            body["target_util"] = self.target_util
        if self.cold_mult is not None:
            body["cold_mult"] = self.cold_mult
        if self.max_queue_time is not None:
            body["max_queue_time"] = self.max_queue_time
        if self.target_queue_time is not None:
            body["target_queue_time"] = self.target_queue_time
        if self.inactivity_timeout is not None:
            body["inactivity_timeout"] = self.inactivity_timeout
        if self.autoscaler_instance:
            body["autoscaler_instance"] = self.autoscaler_instance

        self.logger.debug(f"PUT {API_URL}/api/v0/deployments/ body={body}")
        resp = requests.put(
            f"{API_URL}/api/v0/deployments/",
            json=body,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()
        result = resp.json()

        if not result.get("success"):
            raise RuntimeError(f"Deployment failed: {result}")

        self.deployment_id = result["deployment_id"]
        self.endpoint_id = result["endpoint_id"]
        action = result.get("action", "unknown")
        self.logger.info(f"Deployment {action}: id={self.deployment_id}, endpoint={self.endpoint_id}")

        # Upload to S3 if the API returned a presigned upload URL (new version)
        if "upload_url" in result:
            self.logger.debug("Uploading deployment tar.gz to S3...")
            upload_resp = requests.post(
                result["upload_url"],
                data=result["upload_fields"],
                files={"file": ("deployment.tar.gz", payload)},
            )
            upload_resp.raise_for_status()
            self.logger.info("Upload complete.")

        if result.get("evicted_versions"):
            self.logger.info(f"Evicted old versions: {result['evicted_versions']}")

        print(f"Deployed '{self.name}' (action={action}, id={self.deployment_id})")
        return result

    # --- Serve (worker side) ---

    def ready(self):
        """In serve mode, start the Worker server. In client mode, deploy automatically."""
        current_mode = get_mode()

        if current_mode == "client":
            self.deploy()
            return

        if current_mode == "serve":
            from vastai import Worker, WorkerConfig, HandlerConfig, BenchmarkConfig, LogActionConfig

            remote_function_handlers: list[HandlerConfig] = []

            for remote_func_name, remote_func in self.remote_functions.items():
                benchmark_config: BenchmarkConfig = None
                if remote_func_name == self.benchmark_function_name:
                    if len(self.benchmark_dataset) > 0:
                        benchmark_config = BenchmarkConfig(
                            dataset=self.benchmark_dataset,
                            runs=10
                        )
                    elif self.benchmark_generator is not None:
                        benchmark_config = BenchmarkConfig(
                            generator=self.benchmark_generator,
                            runs=10
                        )
                    else:
                        raise ValueError("Must specify either a benchmark dataset or benchmark generator for benchmark function")

                remote_func_handler = HandlerConfig(
                    route=f"/remote/{remote_func_name}",
                    remote_function=remote_func,
                    allow_parallel_requests=False,
                    benchmark_config=benchmark_config,
                    max_queue_time=30.0
                )
                remote_function_handlers.append(remote_func_handler)

            remote_worker_config = WorkerConfig(
                model_log_file=self.model_log_file,
                handlers=remote_function_handlers,
                log_action_config=LogActionConfig(
                    on_load=self.model_backend_load_logs,
                    on_error=self.model_backend_error_logs,
                )
            )

            remote_worker = Worker(remote_worker_config)

            async def main():
                if self.on_init_function is not None:
                    try:
                        self.on_init_function()
                    except Exception as ex:
                        raise Exception(f"Error in on_init function: {ex}")

                model_log = Path(self.model_log_file)
                await model_log.parent.mkdir(parents=True, exist_ok=True)

                async with aiofiles.open(model_log, "a") as f:
                    await f.write("Deployment ready\n")

                if self.background_task:
                    await asyncio.gather(
                        remote_worker.run_async(),
                        self.background_task(),
                    )
                else:
                    await remote_worker.run_async()

            asyncio.run(main())
