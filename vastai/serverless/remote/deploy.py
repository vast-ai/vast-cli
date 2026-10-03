import functools
import inspect
import threading
import time
import json
import os
from typing import Optional, Any, Callable, Awaitable, ParamSpec, BinaryIO
from typing_extensions import Unpack
from dataclasses import asdict, dataclass
from vastai.data import query
from vastai import AsyncClient
from vastai._base import _APIKEY_SENTINEL
from vastai.data.deployment import DeploymentConfig
from vastai.serverless.client import ManagedDeployment
from vastai.serverless.client.worker import Worker
from . import serialization
from .base import (
    Autoscaling,
    Config,
    Deployment_,
    DockerLogin,
    Image,
    RemoteOptions,
    RemoteOptionsDict,
)
from .progress import StartupProgress, WorkerStartupTimeout
from .utils import create_deployment_tarball, compute_deployment_hash
from os.path import getsize
import tempfile
import asyncio
import logging

logger = logging.getLogger("vastai")

logger.debug("mode: deploy")
# TODO: implement heartbeat, sync ready.

"""
Design:

Deployment has a root module.

Single file vs package deployments:
single file:
- from vastai.serverless import deployments
- deployment = deployments.Deployment(Image) 
- @deployment.remote...
- deployment.ensure_ready()

multi file: # skip for now
- @deployments.post_configure(name = name, image = image)
  def post_configure(deployment):
    deployment.ensure_ready()
  with post_configure:
    import mod1 
    import mod2

Serve:
- pull tarball
- read env, onstart, installs, submodules, name from config. # non essential
- inserts envs, runs installs, runs onstart. # non essential
- from vastai.serverless import deployments # essential
- import deployment # for package deployments require __init__.py to explicitly import remote function modules 
- my_deployment = deployments.get(name) # name is None if not manually set here. 
- serve(my_deployment) -> # essential
    async loop
    async serve(fname, args) -> serialize(my_deployment.registry[fname](deserialize(args)))
- fname relative to root module


Deploy:
- make endpoint args and get a tarball upload link
- make tarball and post it
- when functions are called:
  - convert fname to be relative to root module. 


Client -> Serve depends:
- POST -> app.endpoint/api/f serialized args -> returns f(args). 
  - serialization: root module agrees (i.e., `deployment` in serve is the root_module of deployment)
Serve depends:
- handle_f -> app.get(f_name)(args,kwargs)
    - app  <- deployments.get_app(name)
      - import deployment -> registers app and app functions
        - deployment module in ./deployment/ or ./deployment.py, untarred in tarball
    - name from config.json
    - environment:
        - On Image defined by from_image
        - with machine requirements set by requires_
        - envs set to envs (from config.json)
        - pip installs installed ""
        - apt gets installed ""
        - runs ran ""
        - vastai sdk installed (by bootstrap script)
    - where config.json, deployments are in tarball
      - bootstrap script knows deployment_id to grab from tarball with from S3

Serve <-> Webserver:
    - deployment_id in env
    - bootstrap script in onstart
    - Image, search params from deployments

Serve <-> Deploy:
    - Tarball as promised
Deploy <-> webserver

"""

DEBUG_DEPLOYMENT_TAR = os.environ.get("DEBUG_DEPLOYMENT_TAR")


@dataclass
class _FullDeployment:
    root_module: str
    deployment: ManagedDeployment


_WARNED: set[tuple[str, Any]] = set()

_WARNING_TEXT = {
    "event_loop_blocked": (
        "Worker {worker} reported its event loop was blocked. A synchronous "
        "remote function body starves the worker's health reporting and the "
        "worker may be reclaimed mid-batch. Define the function with plain "
        "`def` (it will be threaded automatically) or wrap the work in "
        "`asyncio.to_thread(...)`."
    ),
}


def _warn_once(code: str, worker: Any) -> None:
    """Surface a worker-reported problem to the caller, once per worker."""
    key = (code, worker)
    if key in _WARNED:
        return
    _WARNED.add(key)
    template = _WARNING_TEXT.get(code)
    if template is None:
        logger.warning(f"Worker {worker} reported: {code}")
    else:
        logger.warning(template.format(worker=worker))


class RemoteCall:
    """An in-flight remote call that also reports where it ran.

    ``await f(x)`` stays the simple path. When you need to know which worker
    served a call — to verify a batch really spread across the pool, say — use
    ``f.submit(x)`` and read the attributes after awaiting::

        calls = [render.submit(i) for i in range(32)]
        results = await asyncio.gather(*calls)
        Counter(c.worker_id for c in calls)
    """

    __slots__ = (
        "_coro",
        "worker_id",
        "worker_url",
        "gpu",
        "latency",
        "duration_ms",
        "deployment_version_id",
    )

    def __init__(self) -> None:
        self._coro: Optional[Awaitable[Any]] = None
        self.worker_id: Optional[int] = None
        self.worker_url: Optional[str] = None
        self.gpu: Optional[str] = None
        self.latency: Optional[float] = None
        self.duration_ms: Optional[float] = None
        self.deployment_version_id: Optional[int] = None

    def __await__(self):
        if self._coro is None:
            raise RuntimeError("RemoteCall was not dispatched")
        return self._coro.__await__()

    def __repr__(self) -> str:
        return (
            f"<RemoteCall worker={self.worker_id} gpu={self.gpu} "
            f"latency={self.latency}>"
        )


P = ParamSpec("P")


class Deployment(Deployment_):  # TODO: Async Context Manager compatible with client
    def __init__(
        self,
        api_key: str | object = _APIKEY_SENTINEL,
        ttl: float | None = None,
        autoscaler_instance="prod",
        autoscaler_url: Optional[str] = None,
        webserver_url="https://console.vast.ai",
        progress: str = "auto",
        startup_timeout: float | None = 900.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.async_client = AsyncClient(api_key, vast_server=webserver_url)
        self.client = self.async_client.serverless(
            instance=autoscaler_instance, autoscaler_url=autoscaler_url
        )
        self.autoscaler_instance = autoscaler_instance
        self.autoscaler_url = self.client.autoscaler_url
        self.webserver_url = webserver_url
        self._image: Image | None = None
        self._autoscaling: Autoscaling | None = None
        self._ttl = ttl
        self._inner: _FullDeployment | None = None
        # "auto" | "live" | "plain" | "off"
        self._progress_mode = progress
        # Refuse to block forever waiting for a worker that may never arrive.
        self._startup_timeout = startup_timeout
        self._progress: Optional[StartupProgress] = None
        self._version_id: Optional[int] = None

    # -- worker introspection ------------------------------------------------

    async def workers(self) -> list[Worker]:
        """Current workers for this deployment's endpoint.

        Useful on its own, and the data source for startup progress and for
        ``ensure_ready(wait=...)``.
        """
        if not isinstance(self._inner, _FullDeployment):
            raise Exception("Deployment is not ready. Call .ensure_ready() first!")
        endpoint = await self._inner.deployment.endpoint._get_routing_endpoint()
        return await self.client.get_endpoint_workers(endpoint)

    def _get_progress(self) -> StartupProgress:
        if self._progress is None:
            self._progress = StartupProgress(
                name=self.name or "deployment",
                fetch_workers=self.workers,
                mode=self._progress_mode,
            )
        return self._progress

    def _compile_env(self, checked_image: Image) -> str:
        envs = [f"-p {port}:{port}/{type_}" for port, type_ in checked_image._ports]
        if self.autoscaler_url is not None:
            envs.append(f"-e REPORT_ADDR={self.autoscaler_url}")
        if self.webserver_url != "https://console.vast.ai":
            envs.append(f"-e VAST_API_URL={self.webserver_url}")
        if checked_image._venv == "":
            envs.append("-e USE_SYSTEM_PYTHON=true")
            envs.append("-e UV_SYSTEM_PYTHON=1")
            envs.append("-e UV_BREAK_SYSTEM_PACKAGES=1")
        elif checked_image._venv is not None:
            envs.append(f"-e ENV_PATH={checked_image._venv}")
        return " ".join(envs)

    def _into_deployment_config_and_tarball(self, tar_path: str) -> DeploymentConfig:
        # should error if _image, _autoscaling, file, or any other field needed to calculate DeploymentConfig is None
        if not isinstance(self._image, Image):
            raise Exception(
                "Trying to deploy a deployment without an image configured."
            )
        if not isinstance(self.name, str):
            raise Exception(
                "Trying to deploy an unbound deployment. Have any remote functions been registered?"
            )
        if not isinstance(self.root_module, str):
            raise Exception(
                "Trying to deploy an unbound deployment. Have any remote functions been registered?"
            )
        if not isinstance(self._autoscaling, dict):
            raise Exception(
                "Trying to deploy a deployment without autoscaling configured."
            )
        logger.debug(f"Building deployment tarball at {tar_path}")
        hash, size = self._compute_hash_and_filesize_and_make_tar(
            tar_path, self.name, self._image
        )
        logger.info(f"Deployment tarball built: hash={hash}, size={size} bytes")
        return DeploymentConfig(
            name=self.name
            if self.name
            else self.root_module,  # if "", is main deployment for module
            image=self._image._image,
            env=self._compile_env(self._image),
            file_hash=hash,
            file_size=size,
            tag=self.tag,
            search_params=self._image._requires.unparse_query(),
            storage=self._image._storage,
            ttl=self._ttl,
            version_label=self.version_label,
            **self._image._docker_login,
            **self._autoscaling,
        )

    def configure_autoscaling(self, **kwargs: Unpack[Autoscaling]):
        if self._autoscaling is None:
            self._autoscaling = kwargs
        else:
            self._autoscaling.update(kwargs)

    def image(
        self, from_image: str, storage: int, **docker_login: Unpack[DockerLogin]
    ) -> Image:
        self._image = Image(from_image, storage, **docker_login)
        return self._image

    def _collate_config(self, checked_name: str, checked_image: Image) -> Config:
        # should error if any required fields are still None
        return Config(
            checked_name,
            checked_image._pip_installs,
            checked_image._apt_gets,
            list(checked_image._envs.items()),
            checked_image._runs,
        )

    def _compute_hash_and_filesize_and_make_tar(
        self, tar_path: str, checked_name: str, checked_image: Image
    ) -> tuple[str, int]:
        if not isinstance(self.file, str):
            raise Exception(
                "Trying to deploy a deployment not yet bound to a Python module. Have any remote functions been registered?"
            )
        config = self._collate_config(checked_name, checked_image)
        hash = compute_deployment_hash(config, self.file, checked_image._copies)
        create_deployment_tarball(tar_path, config, self.file, checked_image._copies)
        size = getsize(tar_path)
        return (hash, size)

    def _heartbeat_thread(self, deployment: ManagedDeployment, ttl: float):
        interval = min(ttl / 2, 60)
        while True:
            deployment.sync_heartbeat()
            time.sleep(interval)

    async def async_ensure_ready(
        self,
        wait: bool | int = False,
        timeout: float | None = None,
        require_version: bool = True,
    ):
        """Register (and if needed upload) the deployment.

        Args:
            wait: ``False`` returns as soon as the deployment is registered —
                the historical behaviour. ``True`` waits for one worker to be
                serving this exact code version; an int waits for that many.
            timeout: Seconds to wait when ``wait`` is set. Defaults to the
                deployment's ``startup_timeout``.
            require_version: Reject workers still serving a superseded version,
                so a call made right after a rolling update cannot be answered
                by the previous code.
        """
        if not isinstance(self.root_module, str):
            raise Exception(
                "Trying to deploy a deployment not yet bound to a Python module. Have any remote functions been registered?"
            )

        logger.info(f"Preparing deployment '{self.name}' (module={self.root_module})")
        with tempfile.NamedTemporaryFile(
            delete_on_close=False
        ) as f:  # deletes at end of context manager instead of at f.close
            tar_path = f.name if not DEBUG_DEPLOYMENT_TAR else DEBUG_DEPLOYMENT_TAR
            f.close()  # _into_deployment_config_and_tarball will reopen it when it makes the tarball
            config = self._into_deployment_config_and_tarball(tar_path)
            logger.debug(f"Registering deployment with server")
            deployment = await self.client.put_deployment(config)
            if deployment.needs_upload:
                logger.info(f"Uploading deployment tarball")
                await deployment.upload(tar_path)
                logger.info(f"Upload complete")
            else:
                logger.info(f"Deployment tarball already up to date, skipping upload")
            if deployment.action == "soft_update":
                wg_id = deployment.workergroup_id
                if not wg_id:
                    wg_id = await self.client.find_workergroup_for_endpoint(
                        deployment.endpoint_id
                    )
                if wg_id:
                    logger.info(f"Triggering rolling update for workergroup {wg_id}")
                    await self.client.update_workers(wg_id)
                else:
                    logger.warning(
                        f"soft_update but no workergroup found for endpoint {deployment.endpoint_id}, skipping update_workers"
                    )
            self._inner = _FullDeployment(self.root_module, deployment)
            if require_version:
                try:
                    self._version_id = (await deployment.get()).current_version_id
                except Exception as ex:  # non-fatal: fall back to no pinning
                    logger.debug(f"Could not resolve deployment version: {ex}")
                    self._version_id = None
            if self._ttl is not None:
                threading.Thread(
                    target=self._heartbeat_thread,
                    args=(deployment, self._ttl),
                    daemon=True,
                ).start()
        logger.info(f"Deployment '{self.name}' is ready (id={deployment.id})")

        if wait:
            want = 1 if wait is True else int(wait)
            await self._wait_for_workers(
                want,
                timeout if timeout is not None else self._startup_timeout,
                require_version=require_version,
            )

    async def _wait_for_workers(
        self, want: int, timeout: float | None, require_version: bool = True
    ) -> list[Worker]:
        """Block until ``want`` workers can serve this deployment's version."""
        deadline = None if timeout is None else time.monotonic() + timeout
        progress = self._get_progress()
        progress.acquire()
        started = time.monotonic()
        delay = 2.0
        try:
            while True:
                try:
                    workers = await self.workers()
                except Exception as ex:
                    logger.debug(f"worker poll failed while waiting: {ex}")
                    workers = []

                ready = [w for w in workers if w.is_ready]
                if require_version and self._version_id is not None:
                    # Treat "unknown version" as acceptable so older workers
                    # that do not report the field are not excluded outright.
                    ready = [
                        w
                        for w in ready
                        if w.deployment_version_id in (None, self._version_id)
                    ]
                if len(ready) >= want:
                    logger.info(
                        f"Deployment '{self.name}': {len(ready)} worker(s) ready"
                    )
                    return ready

                if deadline is None:
                    await asyncio.sleep(delay)
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise WorkerStartupTimeout(
                            self.name or "deployment",
                            time.monotonic() - started,
                            workers,
                        )
                    # Never sleep past the deadline, or a short timeout would
                    # be rounded up to a whole backoff interval.
                    await asyncio.sleep(min(delay, remaining))
                delay = min(delay * 1.5, 10.0)
        finally:
            progress.release()

    def ensure_ready(
        self,
        wait: bool | int = False,
        timeout: float | None = None,
        require_version: bool = True,
    ):
        asyncio.run(
            self.async_ensure_ready(
                wait=wait, timeout=timeout, require_version=require_version
            )
        )

    def _unwrap_worker_response(self, response: dict[str, Any]) -> serialization.JSON:
        try:
            return response["response"]["result"]
        except KeyError:
            raise Exception(
                f"Remote function call failed with status code {response['status']}: {response['text']}"
            )

    def _record_call_meta(self, call: "RemoteCall | None", response: dict) -> None:
        """Populate a RemoteCall from the transport + worker metadata.

        The worker URL and latency were always available on the transport
        response; the worker id and GPU come from the ``meta`` block that serve
        mode attaches alongside ``result``.
        """
        if call is None:
            return
        call.worker_url = response.get("url")
        call.latency = response.get("latency")
        meta = {}
        inner = response.get("response")
        if isinstance(inner, dict):
            meta = inner.get("meta") or {}
        call.worker_id = meta.get("worker_id")
        call.gpu = meta.get("gpu")
        call.deployment_version_id = meta.get("deployment_version_id")
        call.duration_ms = meta.get("duration_ms")
        for warning in meta.get("warnings") or []:
            _warn_once(warning, call.worker_id)

    async def _dispatch(
        self, f_name, globals, sig, args, kwargs, call: "RemoteCall | None" = None
    ) -> Any:
        if not isinstance(self._inner, _FullDeployment):
            raise Exception("Deployment is not ready. Call .ensure_ready() first!")
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        route = "/remote/" + "/".join(f_name)
        logger.debug(f"Dispatching remote call to {route}")

        payload = {
            "kwargs": {
                k: serialization.serialize(v, self._inner.root_module)
                for k, v in bound_args.arguments.items()
            }
        }
        # Let the worker reject the call if it is serving superseded code, so a
        # rolling update cannot silently answer with the previous version.
        if self._version_id is not None:
            payload["expect_version_id"] = self._version_id

        response = await self._request_with_progress(route, payload)
        self._record_call_meta(call, response)

        return serialization.deserialize_unwrap_error(
            self._unwrap_worker_response(response),
            self._inner.root_module,
            globals,
        )

    async def _request_with_progress(self, route: str, payload: dict) -> dict:
        """Issue the request, reporting startup progress while it waits.

        The transport blocks internally polling for a routable worker. There is
        no callback out of it, so progress is reported by a shared poller and
        the overall wait is bounded by ``startup_timeout``.
        """
        assert isinstance(self._inner, _FullDeployment)
        progress = self._get_progress()
        progress.acquire()
        started = time.monotonic()
        try:
            coro = self._inner.deployment.endpoint.request(route, payload)
            if self._startup_timeout is None:
                return await coro
            try:
                return await asyncio.wait_for(coro, timeout=self._startup_timeout)
            except asyncio.TimeoutError:
                raise WorkerStartupTimeout(
                    self.name or "deployment",
                    time.monotonic() - started,
                    progress.last_workers,
                ) from None
        finally:
            progress.release()

    def _submit(self, f_name, globals, sig, args, kwargs) -> "RemoteCall":
        """Dispatch a call and return an awaitable handle carrying metadata."""
        call = RemoteCall()
        call._coro = self._dispatch(f_name, globals, sig, args, kwargs, call=call)
        return call

    def remote(
        self,
        f: Callable[P, Awaitable[Any]] | None = None,
        **opts: Unpack[RemoteOptionsDict],
    ) -> (
        Callable[P, Awaitable[Any]]
        | Callable[[Callable[P, Awaitable[Any]]], Callable[P, Awaitable[Any]]]
    ):
        # Validate here so a bad option fails at decoration time with a useful
        # message, even though only serve mode acts on most of them.
        RemoteOptions.from_kwargs(**opts)

        def decorator(
            f: Callable[P, Awaitable[Any]], **_
        ) -> Callable[P, Awaitable[Any]]:
            f_rel_name = self.relativize(f)
            logger.debug(f"Registered remote function: {f.__name__}")
            f_globals = f.__globals__
            sig = inspect.signature(f)

            def inner(*args: P.args, **kwargs: P.kwargs) -> Awaitable[Any]:
                return self._dispatch(f_rel_name, f_globals, sig, args, kwargs)

            functools.update_wrapper(inner, f)
            # Opt-in richer handle: `call = f.submit(...)` then `await call`
            # exposes which worker served it. See RemoteCall.
            inner.submit = (  # type: ignore[attr-defined]
                lambda *a, **kw: self._submit(f_rel_name, f_globals, sig, a, kw)
            )
            return inner

        if f is not None:
            return decorator(f)
        else:
            return decorator
