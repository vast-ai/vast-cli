# Websocket Sessions Example

This example shows how to run a persistent websocket server on Vast serverless
workers, using SDK sessions to keep workers alive and cooperate with the
autoscaler.

## Architecture

```
Client                         Vast                          Worker
  |                              |                              |
  |-- session(cost=1000) ------->|-- pin worker --------------->|
  |<- session.url (worker IP) ---|                              |
  |                              |                              |
  |-- session.request("/ws_port") -------- proxy HTTP --------->| (returns external port)
  |<- {"port": 32464} --------- proxy HTTP --------------------|
  |                              |                              |
  |-- ws://worker_ip:32464/ws ------ direct connection -------->| (websocket)
  |<======= websocket traffic (bypasses proxy) ================>|
  |                              |                              |
  |-- session.close() ---------->|-- release worker ----------->|
```

The Vast proxy doesn't support websockets, so we bypass it:

1. **Sessions** keep workers alive. The client creates a session, which pins a
   worker and tells the autoscaler it's in use.
2. **Port discovery** happens through a normal HTTP request proxied by the
   worker SDK. The server reads its `VAST_TCP_PORT_9001` env var (Vast maps
   internal container ports to different external ports) and returns it.
3. **Websocket traffic** goes directly to the worker's IP and external port.
4. **Cleanup** — when the websocket closes, the client closes the session so
   the autoscaler can reclaim the worker.

## Files

| File | Runs on | Purpose |
|------|---------|---------|
| `server.py` | Worker | Your websocket backend. The included version is a minimal ping/pong placeholder -- replace the `/ws` handler with your own logic. The `/noop`, `/health`, and `/ws_port` routes are required for SDK integration. |
| `worker.py` | Worker | Vast worker SDK config. Points the SDK at server.py for benchmarking and healthchecks. |
| `client.py` | Your machine | Creates sessions and connects to workers via websocket. |
| `onstart.sh` | Worker | Bootstrap script that installs deps, starts server.py, then hands off to the Vast worker SDK. |
| `requirements.txt` | Worker | Python deps for server.py (just `aiohttp`). |

## Setup

### 1. Create an endpoint

Create a serverless endpoint on [console.vast.ai](https://console.vast.ai)
with the following settings:

- **Expose port 9001** (or whatever port your websocket server uses)
- **Onstart script**: paste the contents of `onstart.sh`, or host it and use a
  bootstrap URL

### 2. Run the client

```bash
pip install vastai websockets
export VAST_API_KEY=your_key_here
python3 client.py
```

## Adapting for your backend

Replace `server.py` with your own websocket server. You need to keep these
integration points:

1. **`POST /noop`** -- benchmark route. The worker SDK calls this to measure
   performance. Return 200. The sleep duration and workload value control the
   reported perf score (workload / time = perf).

2. **`GET /health`** -- healthcheck. Return 200 when your server is ready.

3. **`POST /ws_port`** -- port discovery. Return
   `{"port": int(os.environ["VAST_TCP_PORT_<your_port>"])}`. This is how the
   client finds the external port mapped to your internal websocket port.

4. **Log "Websocket server ready"** to the log file (`/workspace/ws_server.log`)
   when your server is up. The worker SDK watches for this line.

5. **Update `worker.py`** if you change the port or log file path.
