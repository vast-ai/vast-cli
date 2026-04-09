"""
Websocket session example - Client

Demonstrates using SDK sessions to keep a worker alive while connecting to it
via websockets directly. The proxy doesn't support websockets, so we:

1. Create a session (pins & keeps the worker alive via the autoscaler)
2. Extract the worker URL from the session
3. Connect to the websocket server on the worker directly
4. When done, close the websocket and the session
"""

import asyncio
from urllib.parse import urlparse
import websockets
from vastai import Serverless

ENDPOINT_NAME = "my-ws-endpoint"
NUM_CONNECTIONS = 2


class WebsocketSession:
    """Wraps an SDK session + a direct websocket connection to the worker."""

    def __init__(self, session, ws):
        self.session = session
        self.ws = ws

    @classmethod
    async def connect(cls, endpoint, cost=1000):
        session = await endpoint.session(cost=cost, lifetime=60)
        try:
            # Query the server for the external websocket port.
            # This goes through the worker SDK proxy as a normal HTTP request.
            port_resp = await session.request("/ws_port", {})
            ws_port = port_resp["response"]["port"]

            # Build the websocket URL using the worker's IP + external port
            parsed = urlparse(session.url)
            ws_url = f"ws://{parsed.hostname}:{ws_port}/ws"
            print(f"Connecting to {ws_url} (session {session.session_id})")
            ws = await websockets.connect(ws_url)
        except Exception:
            await session.close()
            raise
        return cls(session, ws)

    async def send(self, message):
        await self.ws.send(message)
        return await self.ws.recv()

    async def close(self):
        try:
            await self.ws.close()
        finally:
            await self.session.close()


async def run_connection(endpoint, conn_id):
    """Open a websocket session, send some pings, then close."""
    ws_session = await WebsocketSession.connect(endpoint)
    try:
        for i in range(5):
            response = await ws_session.send("ping")
            print(f"[conn {conn_id}] ping #{i} -> {response}")
            await asyncio.sleep(0.5)
    finally:
        await ws_session.close()
        print(f"[conn {conn_id}] closed")


async def main():
    async with Serverless() as client:
        endpoint = await client.get_endpoint(name=ENDPOINT_NAME)

        # Launch multiple websocket sessions concurrently
        await asyncio.gather(*(
            run_connection(endpoint, i) for i in range(NUM_CONNECTIONS)
        ))


if __name__ == "__main__":
    asyncio.run(main())
