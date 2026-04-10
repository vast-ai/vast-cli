"""
Websocket session example - Client

Demonstrates using Vast serverless sessions to maintain websocket connections
to workers. We use sessions to keep workers alive while connecting to them directly:

  1. Create a session on the endpoint (pins a worker, keeps it alive)
  2. Query /ws_port through the session to discover the external port
  3. Connect to the websocket server on the worker directly
  4. When done, close the websocket and then the session
"""

import asyncio
import random
from urllib.parse import urlparse
import websockets
from vastai import Serverless

ENDPOINT_NAME = "my-ws-endpoint"
NUM_CONNECTIONS = 3
SESSION_DURATION = 120  # average session duration in seconds
SESSION_JITTER = 60     # +/- random range


class WebsocketSession:
    """Wraps an SDK session + a direct websocket connection to the worker."""

    def __init__(self, session, ws):
        self.session = session
        self.ws = ws

    @classmethod
    async def connect(cls, endpoint, cost=1000):
        session = await endpoint.session(cost=cost, lifetime=30)
        try:
            # Query the server for the external websocket port.
            # This goes through the worker SDK proxy as a normal HTTP request.
            port_resp = await session.request("/ws_port", {})
            ws_port = port_resp["response"]["result"]["port"]

            # Build the websocket URL using the worker's IP + external port
            parsed = urlparse(session.url)
            ws_url = f"ws://{parsed.hostname}:{ws_port}/ws"
            print(f"Connecting to {ws_url} (session {session.session_id})")
            ws = await websockets.connect(ws_url)
        except Exception:
            await session.close()
            raise
        inst = cls(session, ws)
        inst._keepalive_task = asyncio.create_task(inst._keepalive())
        return inst

    async def _keepalive(self):
        """Send a request every 10s to extend the session lifetime."""
        while self.session.open:
            await asyncio.sleep(10)
            try:
                resp = await self.session.request("/benchmark", {})
                print(f"[keepalive {self.session.session_id}] ok")
            except Exception as e:
                print(f"[keepalive {self.session.session_id}] failed: {e}")
                break

    async def send(self, message):
        await self.ws.send(message)
        return await self.ws.recv()

    async def close(self):
        self._keepalive_task.cancel()
        try:
            await self._keepalive_task
        except asyncio.CancelledError:
            pass
        try:
            await self.ws.close()
        finally:
            await self.session.close()


async def run_connection(endpoint, conn_id):
    """Open a websocket session, send pings for a random duration, then close."""
    duration = SESSION_DURATION + random.uniform(-SESSION_JITTER, SESSION_JITTER)
    ws_session = await WebsocketSession.connect(endpoint)
    try:
        elapsed = 0
        ping_num = 0
        while elapsed < duration:
            response = await ws_session.send("ping")
            print(f"[conn {conn_id}] ping #{ping_num} -> {response}")
            ping_num += 1
            await asyncio.sleep(1)
            elapsed += 1
    finally:
        await ws_session.close()
        print(f"[conn {conn_id}] closed after {elapsed:.0f}s")


async def run_slot(endpoint, slot_id):
    """Run sessions back-to-back in this slot, replacing each as it finishes."""
    conn_id = 0
    while True:
        try:
            await run_connection(endpoint, f"{slot_id}.{conn_id}")
        except Exception as e:
            print(f"[slot {slot_id}] connection failed: {e}")
            await asyncio.sleep(5)
        conn_id += 1


async def main():
    async with Serverless() as client:
        endpoint = await client.get_endpoint(name=ENDPOINT_NAME)

        # Maintain NUM_CONNECTIONS concurrent sessions.
        # Each slot runs sessions back-to-back with random durations,
        # so sessions come and go while the average count stays steady.
        await asyncio.gather(*(
            run_slot(endpoint, i) for i in range(NUM_CONNECTIONS)
        ))


if __name__ == "__main__":
    asyncio.run(main())
