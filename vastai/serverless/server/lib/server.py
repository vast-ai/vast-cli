import os
import logging
from typing import List
import ssl
from asyncio import run, gather
import asyncio

from .backend import Backend
from .metrics import Metrics
from aiohttp import web

log = logging.getLogger(__file__)

async def start_server_async(backend: Backend, routes: List[web.RouteDef], **kwargs):
    try:
        use_ssl = os.environ.get("USE_SSL", "false") == "true"
        if use_ssl is True:
            log.debug("Getting SSL Certificate from /etc/instance.crt")
            try:
                ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                ssl_context.load_cert_chain(
                    certfile="/etc/instance.crt",
                    keyfile="/etc/instance.key",
                )
            except Exception as ex:
                raise Exception(f"Failed to get SSL Certificate: {ex}")
        else:
            ssl_context = None

        log.debug("Starting Worker Server...")
        app = web.Application()
        app.add_routes(routes)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(
            runner,
            ssl_context=ssl_context,
            port=int(os.environ["WORKER_PORT"]),
            **kwargs
        )
        await gather(site.start(), backend._start_tracking())

    except Exception as e:
        err_msg = f"Worker Server failed to launch: {e}"
        log.error(err_msg)

        async def beacon():
            metrics = Metrics()
            metrics._set_version(getattr(backend, "version", "0"))
            metrics._set_mtoken(getattr(backend, "mtoken", ""))
            try:
                while True:
                    metrics._model_errored(err_msg)
                    await metrics._Metrics__send_metrics_and_reset()
                    await asyncio.sleep(10)
            finally:
                await metrics.aclose()

        await beacon()



def start_server(backend: Backend, routes: List[web.RouteDef], **kwargs):
    run(start_server_async(backend, routes, **kwargs))

