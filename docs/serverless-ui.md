# Serverless UI

`vastai run serverless-ui` serves a local web page for testing Vast serverless endpoints, and an
OpenAI-compatible proxy to them. It works with endpoints that run pyworker: its OpenAI-compatible
worker (vLLM, vLLM-Omni, SGLang, llama.cpp) and its ComfyUI worker.

```bash
vastai run serverless-ui                         # open the link it prints
vastai run serverless-ui --prefer my-endpoint    # when several endpoints serve a model
```

It uses your API key the way every `vastai` command does: `--api-key`, then `VAST_API_KEY`,
then the key saved by `vastai set api-key`. `SERVERLESS_UI_HOST` and `SERVERLESS_UI_PORT` set
the defaults for `--host` and `--port`.

## The access token

Whenever the server holds a key, or others can reach it, every caller sends an access token:
localhost is open to every user and process on the machine. (On localhost without a key there is
none: callers bring their own key, and nothing of the server's can be spent.)

Each run makes a token and prints a link that carries it, like `http://127.0.0.1:8765/#token=…`,
and an `export SERVERLESS_UI_TOKEN=…` line for programs. Open the link, and the page connects and
remembers the token. (It is in the link's fragment, which browsers never send to a server, so it
doesn't reach logs.)

For programs using the proxy, and to keep the same token across runs, set your own:

```bash
export SERVERLESS_UI_TOKEN=$(openssl rand -hex 16)   # or --access-token TOKEN
vastai run serverless-ui
```

## Sharing it

To use it from another computer, an SSH tunnel keeps it on localhost and encrypted:

```bash
ssh -L 8765:127.0.0.1:8765 user@host     # then open http://127.0.0.1:8765 locally
```

It serves plain HTTP. Bound beyond localhost, or named by a reverse proxy or tunnel with
`--allowed-host`, it warns that the token, any key a caller sends, and every prompt and reply
cross the network unencrypted. Put TLS in front of it (a reverse proxy) before sharing it on a
network you don't trust:

```bash
vastai run serverless-ui --host 0.0.0.0 --port 8080 --allowed-host ui.example.com
```

The page makes every request relative to its own address, so a reverse proxy can serve it
under a path (`https://example.com/tools/ui/`) as well as at the root. The proxy must pass the
original `Host`, port included (nginx: `proxy_set_header Host $http_host`), name it with
`--allowed-host`, and strip the path prefix before forwarding. Otherwise the page's requests
are refused: their `Origin` no longer matches the `Host`.

Give it a host name of its own. A browser treats every page on one host name as the same site,
so another app served from that host (`https://example.com/tools/other/` beside
`https://example.com/tools/ui/`) can script this page: read a key as it is typed or sent, and
read the access token it remembers. No setting on this server can prevent that.

### Without a key

To have each person use their own key (pasted into the page and held in that tab, or sent by
their programs as the API key), start it with `--api-key=`, which overrides `VAST_API_KEY` and the
saved key:

```bash
vastai run serverless-ui --api-key= --host 0.0.0.0 --allowed-host ui.example.com
```

Shared like this it still has an access token, which programs send in the `X-Serverless-UI-Token`
header beside their own key.

## The page

Pick an endpoint and the page reads what it serves from its template: backend, model and
routes. Every route has a form, and the form writes the JSON body, which you can edit before
sending.

- **Workers:** live in the sidebar, with status, jobs and load for each worker, so you can
  watch scaling and job handling while you send requests.
- **Every reply names the worker that served it**, by id, GPU and address.
- **Send ×N:** a burst of N requests at once, with latency percentiles.
- **Load…:** requests at a rate that changes over time, with charts of throughput,
  concurrency, latency and ready workers.
- **Smoke test…:** one small request to each route the endpoint serves, checked for the right
  kind of reply. Upload routes get small generated files.
- **Files:** transcriptions, translations, image edits and image-to-video take uploads, and
  chat takes images, audio and video as attachments. The editor shows a placeholder such as
  `"@file:1 speech.wav (120 KB)"`; the file is sent as a `data:` URI.
- **Code:** each request as Python, with the Vast SDK or with the `openai` package through the
  proxy.
- **Proxy traffic:** requests your own programs send through the proxy, live. Bound beyond
  localhost, traffic made with the server's key is shown only with `--share-traffic`, since it
  is other people's prompts and replies.

## ComfyUI endpoints

Endpoints running pyworker's ComfyUI worker (`vastai/comfy`) get a Workflow tab for
`/generate/sync`. Each request is a whole workflow in ComfyUI's API format.

- **Workflows:** each worker keeps the workflows its template provisions, already converted to
  the API format, in `/opt/comfyui-api-wrapper/workflows/` (the benchmark runs one of them). The
  tab names them and, once a worker is ready, gives the commands to copy them from it
  (`vastai copy C.<worker>:/opt/comfyui-api-wrapper/workflows/ local:comfy-workflows/`, or one over
  SSH). Drop one in, or a workflow exported from ComfyUI with Export (API); a GUI-format file is
  explained, not sent.
- **Fields:** prompts (positive and negative, by the sampler input they feed), seed (random each
  request by default), size, steps, CFG, length and input files. Input files are names already
  on the worker (the template's `PROVISIONING_DOWNLOADS`) or http(s) URLs.
- **Outputs** come back inline (`return_outputs_as_base64`), shown as images, video or audio,
  with ComfyUI's timings.
- **Through the proxy:** `POST /e/<endpoint>/generate/sync` with the same JSON.

## The proxy

Point any OpenAI client at it:

```python
import os
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8765/e/my-endpoint/v1",
                api_key=os.environ["SERVERLESS_UI_TOKEN"])  # the access token, not a Vast key
client.chat.completions.create(model="Qwen/Qwen3-4B-Instruct-2507", messages=[...], max_tokens=512)
```

Set `max_tokens` on chat and completions. pyworker counts a request's workload by it, and
currently counts a request without it as no work at all, so an endpoint fed only such requests
looks idle to the autoscaler and doesn't scale up.

- `/e/<endpoint>/v1` sends everything to one endpoint, by name or id. A missing `model` is
  filled in with the endpoint's.
- `/v1` picks the endpoint from `model`: the model its template serves, or an endpoint name,
  which is then sent on as that endpoint's model (the backends accept only the model they serve).
  `GET /v1/models` lists them. When several endpoints serve one model, `--prefer` ranks them.
- All of pyworker's routes pass through, streams as server-sent events. File uploads arrive
  as multipart, as OpenAI clients send them, and are passed on as pyworker expects.
- ComfyUI endpoints take `POST /e/<endpoint>/generate/sync` with a workflow in ComfyUI's API
  format: not an OpenAI route, so plain HTTP rather than an OpenAI client. See
  [ComfyUI endpoints](#comfyui-endpoints), and the page's "HTTP via proxy" view for an example.
- Every response carries `X-Vast-Endpoint`, `X-Vast-Worker` (address) and, once known,
  `X-Vast-Worker-Id`.
- The proxy uses the server's key; the client's is ignored unless the server has none. With an
  access token, the client sends the token as its API key:
  `OpenAI(base_url=..., api_key=os.environ["SERVERLESS_UI_TOKEN"])`.

## Slow requests and timeouts

A request waits until a worker can take it: while the endpoint starts one, or while every worker
is busy. A cold start can take minutes (the image, then the model). Nothing is sent back while a
request waits, not even for a stream.

- **The limit.** `--request-timeout` (default 600 seconds) covers waiting for a worker and the
  worker's answer starting, together. Past it the caller gets HTTP 504 with a message that says
  so, and the page shows that on the result. A stream, once its first chunk has arrived, runs to
  its end.
- **Giving up cancels the request.** When a client disconnects (it timed out or retried, or Stop
  was pressed on the page), its request is cancelled. A request still waiting stops waiting, and
  one already on a worker is cut off: the worker cancels its call to the backend and records the
  request as cancelled. The proxy traffic view shows it as cancelled. Bursts and load runs stop
  the same way when their page goes away.
- **Clients' own timeouts are often shorter.** Many clients give up after 30 to 120 seconds, and
  a reverse proxy in front may cut a silent connection sooner (nginx: `proxy_read_timeout`,
  60 seconds by default). Give clients and proxies a timeout longer than the endpoint's cold
  start, or keep a worker ready (`cold_workers`, `min_load`) so requests don't wait for one.
- **Retries make duplicates.** The `openai` package retries a timed-out request twice by default.
  Each try is a new request. Those it abandons are cancelled, but one that has already reached a
  worker has done some work by then. Where a duplicate is costly, set `max_retries=0` and a
  timeout longer than a cold start:

  ```python
  client = OpenAI(base_url=..., api_key=..., timeout=900, max_retries=0)
  ```

## Keys and safety

- The key is held in memory only. A key pasted into the page is used for that tab and kept in
  its memory, never stored.
- Keys are removed from logs, errors and responses. Model replies are otherwise passed on as
  written: code a model writes that sets `api_key=` comes back intact.
- It listens on 127.0.0.1 by default. Whenever it holds a key, or others can reach it (bound
  beyond localhost, or answering to another name with `--allowed-host`), every request but the
  page's own load carries the access token (`SERVERLESS_UI_TOKEN`, `--access-token`, at least
  16 characters, or one made for the run). The page sends it as `X-Serverless-UI-Token`, and
  proxy clients as their API key. The server holds it in memory and removes it from logs and
  responses. The page asks for the token alone, or takes it from the printed link, and once it
  works remembers it in the browser (`localStorage`) until you click Forget token; a token made
  for one run is useless after it. A Vast key is never stored.
- Share the token only with people who may spend the key, and use a key you can revoke. On a
  shared server, proxy traffic made with that key is hidden from the page unless you pass
  `--share-traffic`.
- Without a server key, each caller brings their own Vast key as the API key. Shared, it
  still has a token, which callers then send in the `X-Serverless-UI-Token` header, so strangers
  can't use it as a relay; and their keys cross plain HTTP unencrypted, so share it only behind
  TLS. On localhost without a key there is no token: nothing of the server's can be spent.
- Each key may run 2 load runs and keep 10 live worker views at once, within 20 and 200 for
  the whole server. A load run can send up to 20 requests a second for 30 minutes: give the
  token to a server with a key only to people you trust with it.
- Replies are scrubbed of the keys this server has seen, matched exactly, so a key echoed in
  pieces across stream chunks, or encoded, would get through. It is a safety net, not a
  boundary.
- Requests from other websites (by `Origin`) are refused, and so are requests naming a host
  the server doesn't answer to, which is what a website does after pointing its own name at
  this machine (DNS rebinding). On localhost it answers to localhost's names. Bound elsewhere
  it also answers to the machine's names and addresses, as printed at startup; add others,
  such as a DNS name on your network, with `--allowed-host`.
- Worker replies of any other kind than audio, video, images, JSON or plain text (HTML, say)
  are sent as downloads, never as a page on the server's address.
- The page runs only its own script: the Content-Security-Policy allows it by hash, and the page
  may fetch only from the server.

## Development

The server is `vastai/serverless/ui/` (`server.py`, `discovery.py`, `index.html`); the command is
`vastai/cli/commands/serverless_ui.py`.

```bash
cd tests && poetry run pytest cli/serverless_ui scripts/test_check_pyworker.py   # fake Vast API and worker
python tests/cli/serverless_ui/e2e_page.py [screenshot dir]   # the page in headless Chrome
python tests/cli/serverless_ui/live_check.py --prefix qs-     # real endpoints, through a running server
python scripts/check_pyworker.py path/to/pyworker             # the copied pyworker rules still match
```

- `e2e_page.py` drives the page against the fake Vast API in headless Chrome; it needs
  `playwright`, and uses an installed Chrome if there is one, else Playwright's own. It is not
  run by pytest. CI checks only that the page's script parses.
- `live_check.py` calls real endpoints, which need running workers and cost money. Point it at a
  running server with `--server` (default `http://127.0.0.1:8765`) and export the server's
  `SERVERLESS_UI_TOKEN` first. Its speech routes use pyworker's sample from a checkout:
  `$PYWORKER`, else `../pyworker`.

`discovery.py` and the page copy some of pyworker's rules (routes, model variables, backends,
workloads); `scripts/check_pyworker.py` reports where a pyworker checkout differs. Run it when
pyworker changes, or before a release: CI doesn't. It runs that checkout's `routes.py`, so point
it only at one you trust.
