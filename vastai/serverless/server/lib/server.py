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

        # Hardcoded session routes
        app.router.add_post("/session/create", backend.session_create_handler)
        app.router.add_post("/session/end", backend.session_end_handler)
        app.router.add_post("/session/get", backend.session_get_handler)
        app.router.add_post("/session/health", backend.session_health_handler)

        runner = web.AppRunner(app, handler_cancellation=True)
        await runner.setup()
        site = web.TCPSite(
            runner,
            ssl_context=ssl_context,
            port=int(os.environ["WORKER_PORT"]),
            **kwargs
        )

        # Create HTTP-only app for internal webhooks to /session/end
        http_app = web.Application()
        http_app.router.add_post("/session/end", backend.session_end_handler)

        http_runner = web.AppRunner(http_app)
        await http_runner.setup()
        http_port = int(os.environ.get("WORKER_HTTP_PORT", int(os.environ["WORKER_PORT"]) + 1))
        http_site = web.TCPSite(
            http_runner,
            ssl_context=None,  # No SSL for internal webhooks
            port=http_port,
            **kwargs
        )

        log.debug(f"Starting HTTP-only server for /session/end on port {http_port}")
        await gather(site.start(), http_site.start(), backend._start_tracking())

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

