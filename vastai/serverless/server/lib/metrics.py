import os
import time
import logging
import json
from asyncio import sleep
from dataclasses import dataclass, asdict, field
from functools import cache
import asyncio
from aiohttp import ClientSession, ClientTimeout, TCPConnector, ClientResponseError

from .data_types import WorkerStatusData, SystemMetrics, ModelMetrics, RequestMetrics
from typing import Awaitable, NoReturn, List

METRICS_UPDATE_INTERVAL = 1
DELETE_REQUESTS_INTERVAL = 1

log = logging.getLogger(__file__)


@cache
def get_url() -> str:
    use_ssl = os.environ.get("USE_SSL", "false") == "true"
    worker_port = os.environ[f"VAST_TCP_PORT_{os.environ['WORKER_PORT']}"]
    public_ip = os.environ["PUBLIC_IPADDR"]
    return f"http{'s' if use_ssl else ''}://{public_ip}:{worker_port}"


@dataclass
class Metrics:
    version: str = "0"
    mtoken: str = ""
    last_metric_update: float = 0.0
    last_request_served: float = 0.0
    update_pending: bool = False
    id: int = field(default_factory=lambda: int(os.environ["CONTAINER_ID"]))
    report_addr: List[str] = field(
        default_factory=lambda: os.environ["REPORT_ADDR"].split(",")
    )
    url: str = field(default_factory=get_url)
    system_metrics: SystemMetrics = field(default_factory=SystemMetrics.empty)
    model_metrics: ModelMetrics = field(default_factory=ModelMetrics.empty)
    _session: ClientSession | None = field(default=None, init=False, repr=False)

    async def http(self) -> ClientSession:
        if self._session is None:
            self._session = ClientSession(
                timeout=ClientTimeout(total=10),
                connector=TCPConnector(limit=8, limit_per_host=4, force_close=True, enable_cleanup_closed=True)
            )
        return self._session
    
    async def aclose(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    def _request_start(self, request: RequestMetrics) -> None:
        """
        this function is called prior to forwarding a request to a model API.
        """
        log.debug(f"Starting request {request.reqnum}")
        request.status = "Started"
        self.model_metrics.workload_pending += request.workload
        self.model_metrics.workload_received += request.workload
        self.model_metrics.requests_recieved.add(request.reqnum)
        self.model_metrics.requests_working[request.reqnum] = request
        self.update_pending = True

    def _request_end(self, request: RequestMetrics) -> None:
        """
        this function is called after handling of a request ends, regardless of the outcome
        """
        log.debug(f"Ending request {request.reqnum}")
        self.model_metrics.workload_pending -= request.workload
        self.model_metrics.requests_working.pop(request.reqnum, None)
        self.model_metrics.requests_deleting.append(request)
        self.last_request_served = time.time()

    def _request_success(self, request: RequestMetrics) -> None:
        """
        this function is called after a response from model API is received and forwarded.
        """
        log.debug(f"Request {request.reqnum} succeeded")
        self.model_metrics.workload_served += request.workload
        request.status = "Success"
        request.success = True
        self.update_pending = True

    def _request_errored(self, request: RequestMetrics, message: str) -> None:
        """
        this function is called if model API returns an error
        """
        log.error(f"Request {request.reqnum} errored: {message}")
        self.model_metrics.workload_errored += request.workload
        request.status = "Error"
        request.success = False
        self.update_pending = True

    def _request_canceled(self, request: RequestMetrics) -> None:
        """
        this function is called if client drops connection before model API has responded
        """
        log.debug(f"Canceling request {request.reqnum}")
        self.model_metrics.workload_cancelled += request.workload
        request.success = True
        request.status = "Cancelled"
    
    def _request_reject(self, request: RequestMetrics):
        """
        this function is called if the current wait time for the model is above max_queue_time
        """
        self.model_metrics.requests_recieved.add(request.reqnum)
        self.model_metrics.requests_deleting.append(request)
        self.model_metrics.workload_rejected += request.workload
        request.success = False
        request.status = "Rejected"
        self.update_pending = True

    async def _send_delete_requests_loop(self) -> Awaitable[NoReturn]:
        while True:
            await sleep(DELETE_REQUESTS_INTERVAL)
            if len(self.model_metrics.requests_deleting) > 0:
                await self.__send_delete_requests_and_reset()

    async def _send_metrics_loop(self) -> Awaitable[NoReturn]:
        while True:
            await sleep(METRICS_UPDATE_INTERVAL)
            elapsed = time.time() - self.last_metric_update
            if self.system_metrics.model_is_loaded is False and elapsed >= 10:
                await self.__send_metrics_and_reset()
            elif self.update_pending or elapsed > 10:
                await self.__send_metrics_and_reset()

    def _model_loaded(self, max_throughput: float) -> None:
        self.system_metrics.model_loading_time = (
            time.time() - self.system_metrics.model_loading_start
        )
        self.system_metrics.model_is_loaded = True
        self.model_metrics.max_throughput = max_throughput

    def _model_errored(self, error_msg: str) -> None:
        self.model_metrics.set_errored(error_msg)
        self.system_metrics.model_is_loaded = True

    def _set_version(self, version: str) -> None:
        self.version = version

    def _set_mtoken(self, mtoken: str) -> None:
        self.mtoken = mtoken

    #######################################Private#######################################

    async def __send_delete_requests_and_reset(self):
        async def post(report_addr: str, idxs: list[int], success_flag: bool) -> bool:
            data = {
                "worker_id": self.id,
                "mtoken": self.mtoken,
                "request_idxs": idxs,
                "success": success_flag,
            }
            log.debug(
                f"Deleting requests that {'succeeded' if success_flag else 'failed'}: {data['request_idxs']}"
            )
            full_path = report_addr.rstrip("/") + "/delete_requests/"
            for attempt in range(1, 4):
                try:
                    session = await self.http()
                    async with session.post(full_path, json=data) as res:
                        log.debug(f"delete_requests response: {res.status}")
                        res.raise_for_status()
                    return True
                except asyncio.TimeoutError:
                    log.debug("delete_requests timed out")
                except (ClientResponseError, Exception) as e:
                    log.debug(f"delete_requests failed with error: {e}")
                await asyncio.sleep(2)
                log.debug(f"Retrying delete_request, attempt: {attempt}")
            return False

        # Take a snapshot of what we plan to send this tick.
        # New arrivals after this snapshot will remain in the queue for the next tick.
        snapshot = list(self.model_metrics.requests_deleting)
        success_idxs = [r.request_idx for r in snapshot if r.success is True]
        failed_idxs  = [r.request_idx for r in snapshot if r.success is False]

        if not success_idxs and not failed_idxs:
            return  # nothing to do

        for report_addr in self.report_addr:
            # TODO: Add a Redis subscriber queue for delete_requests
            if report_addr == "https://cloud.vast.ai/api/v0":
                # Patch: ignore the Redis API report_addr
                continue
            sent_success = True
            sent_failed  = True

            if success_idxs:
                sent_success = await post(report_addr, success_idxs, True)
            if failed_idxs:
                sent_failed = await post(report_addr, failed_idxs, False)

            if sent_success and sent_failed:
                # Remove only the items we actually sent from the live queue.
                sent_set = set(success_idxs) | set(failed_idxs)
                self.model_metrics.requests_deleting[:] = [
                    r for r in self.model_metrics.requests_deleting
                    if r.request_idx not in sent_set
                ]
                break


    async def __send_metrics_and_reset(self):

        loadtime_snapshot = self.system_metrics.model_loading_time

        def get_worker_status_data() -> WorkerStatusData:
            return WorkerStatusData(
                id=self.id,
                mtoken=self.mtoken,
                version=self.version,
                loadtime=(loadtime_snapshot or 0.0), 
                new_load=self.model_metrics.workload_processing,
                cur_load=self.model_metrics.cur_load,
                rej_load=self.model_metrics.workload_rejected,
                max_perf=self.model_metrics.max_throughput,
                cur_perf=self.model_metrics.workload_served,
                error_msg=self.model_metrics.error_msg or "",
                num_requests_working=len(self.model_metrics.requests_working),
                num_requests_recieved=len(self.model_metrics.requests_recieved),
                additional_disk_usage=self.system_metrics.additional_disk_usage,
                working_request_idxs=self.model_metrics.working_request_idxs,
                cur_capacity=0,
                max_capacity=0,
                url=self.url,
            )

        async def send_data(report_addr: str) -> bool:
            data = get_worker_status_data()
            log_data = asdict(data)
            def obfuscate(secret: str) -> str:
                if secret is None:
                    return ""
                return secret[:7] + "..." if len(secret) > 12 else ("*" * len(secret))
            
            log_data["mtoken"] = obfuscate(log_data.get("mtoken"))
            log.debug(
                "\n".join(
                    [
                        "\n" + "#" * 20 + " Worker Status " + "#" * 20,
                        f"{json.dumps(log_data, indent=2)}",
                        "#" * 55,
                    ]
                )
            )

            full_path = report_addr.rstrip("/") + "/worker_status/"
            for attempt in range(1, 4):
                try:
                    session = await self.http()
                    async with session.post(full_path, json=asdict(data)) as res:
                        res.raise_for_status()
                    return True
                except asyncio.TimeoutError:
                    log.debug(f"Request to /worker_status/ timed out")
                except (ClientResponseError, Exception)  as e:
                    log.debug(f"Request to /worker_status/ failed with error: {e}")
                await asyncio.sleep(2)
                log.debug(f"Retrying /worker_status/ request, attempt: {attempt}")
            log.debug(f"Failed to send worker status through {report_addr}")
            return False

        ###########

        self.system_metrics.update_disk_usage()

        sent = False
        for report_addr in self.report_addr:
            if await send_data(report_addr):
                sent = True
                break

        if sent:
            # clear the one-shot loadtime only if we actually sent *this* value
            self.system_metrics.reset(expected=loadtime_snapshot)
            self.update_pending = False
            self.model_metrics.reset()
            self.last_metric_update = time.time()
