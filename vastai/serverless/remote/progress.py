"""Startup progress reporting for deployments.

A deployment's first call blocks while the serverless engine rents an instance,
pulls the image, installs packages, loads contexts and runs the startup
benchmark. That can take anywhere from under a minute to several minutes, and
without any output the caller cannot tell a slow start from a hang.

:class:`StartupProgress` polls worker state on a single shared task per
deployment and renders it, so one ``asyncio.gather`` of a hundred calls does not
produce a hundred pollers (the endpoint-workers API is rate limited).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from typing import Awaitable, Callable, List, Optional, Sequence

from vastai.serverless.client.worker import Worker

logger = logging.getLogger("vastai")

# The endpoint-workers API is rate limited; never poll faster than this.
MIN_POLL_INTERVAL = 5.0
# How often to redraw / re-log when nothing has changed.
LOG_INTERVAL = 15.0


class WorkerStartupTimeout(TimeoutError):
    """Raised when no worker becomes ready within the allotted time.

    Carries the last observed worker states so the message explains *what* the
    deployment was waiting on rather than just that it gave up.
    """

    def __init__(self, name: str, waited: float, workers: Sequence[Worker]):
        self.name = name
        self.waited = waited
        self.workers = list(workers)
        super().__init__(self._render())

    def _render(self) -> str:
        head = (
            f"Deployment {self.name!r}: no worker became ready after "
            f"{self.waited:.0f}s."
        )
        if not self.workers:
            return (
                head + " No workers were recruited at all — check that your"
                " image.require(...) filters match available offers, and that"
                " the endpoint's max_workers is above zero."
            )
        lines = [head, "Last observed worker states:"]
        for w in self.workers:
            lines.append(f"  {w.id}  {w.phase}")
        lines.append(
            "If workers are stuck in 'loading', the image or packages may be"
            " large; raise timeout=. If they cycle to 'stopped', check the"
            " worker logs for a failing startup or benchmark."
        )
        return "\n".join(lines)


def _supports_live_output() -> bool:
    if os.environ.get("VAST_PROGRESS") == "plain":
        return False
    if os.environ.get("VAST_PROGRESS") == "live":
        return True
    if os.environ.get("CI"):
        return False
    try:
        return sys.stderr.isatty()
    except Exception:
        return False


class StartupProgress:
    """Renders what a deployment is waiting on while it has no ready worker.

    Started lazily by the first blocked call and stopped as soon as any call
    gets routed. ``mode`` is "auto" (live line on a TTY, throttled log lines
    otherwise), "plain", "live" or "off".
    """

    def __init__(
        self,
        name: str,
        fetch_workers: Callable[[], Awaitable[List[Worker]]],
        mode: str = "auto",
        poll_interval: float = MIN_POLL_INTERVAL,
    ):
        self.name = name
        self._fetch = fetch_workers
        self._mode = mode
        self._poll_interval = max(poll_interval, MIN_POLL_INTERVAL)
        self._task: Optional[asyncio.Task] = None
        self._waiters = 0
        # Set again on first acquire(); initialised here so a reporter that is
        # rendered before being acquired does not report a nonsense elapsed.
        self._started_at = time.monotonic()
        self._last_render = 0.0
        self._last_line_len = 0
        self._workers: List[Worker] = []

    # -- lifecycle ---------------------------------------------------------

    def acquire(self) -> None:
        """Register one blocked caller; starts the poller on the first."""
        self._waiters += 1
        if self._task is None or self._task.done():
            self._started_at = time.monotonic()
            self._task = asyncio.create_task(self._run())

    def release(self) -> None:
        """Deregister a caller; stops the poller when the last one leaves."""
        self._waiters = max(0, self._waiters - 1)
        if self._waiters == 0:
            self._stop()

    def _stop(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None
        self._clear_line()

    @property
    def last_workers(self) -> List[Worker]:
        return list(self._workers)

    @property
    def enabled(self) -> bool:
        return self._mode != "off"

    # -- internals ---------------------------------------------------------

    async def _run(self) -> None:
        try:
            while True:
                try:
                    self._workers = await self._fetch()
                except Exception as ex:  # never let reporting break a request
                    logger.debug(f"progress: worker poll failed: {ex}")
                self._render()
                await asyncio.sleep(self._poll_interval)
        except asyncio.CancelledError:
            raise

    def _elapsed(self) -> float:
        return time.monotonic() - self._started_at

    def _summary(self) -> str:
        if not self._workers:
            return "no workers recruited yet"
        counts: dict[str, int] = {}
        for w in self._workers:
            counts[w.phase] = counts.get(w.phase, 0) + 1
        return ", ".join(f"{n} {phase}" for phase, n in sorted(counts.items()))

    def _render(self) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        live = self._mode in ("live",) or (
            self._mode == "auto" and _supports_live_output()
        )
        if live:
            self._render_live()
        elif now - self._last_render >= LOG_INTERVAL:
            self._last_render = now
            logger.info(
                f"{self.name}: waiting for a worker "
                f"({self._waiters} call(s) queued, {self._elapsed():.0f}s) — "
                f"{self._summary()}"
            )

    def _render_live(self) -> None:
        line = (
            f"{self.name}: waiting for a worker "
            f"({self._waiters} queued, {self._elapsed():.0f}s) — {self._summary()}"
        )
        try:
            pad = " " * max(0, self._last_line_len - len(line))
            sys.stderr.write("\r" + line + pad)
            sys.stderr.flush()
            self._last_line_len = len(line)
        except Exception:
            pass

    def _clear_line(self) -> None:
        if self._last_line_len:
            try:
                sys.stderr.write("\r" + " " * self._last_line_len + "\r")
                sys.stderr.flush()
            except Exception:
                pass
            self._last_line_len = 0
