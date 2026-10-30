"""
A CLI command that serves a local web page for testing serverless endpoints, and an
OpenAI-compatible proxy to them. The server lives in vastai/serverless/ui.

vastai run serverless-ui
"""

import argparse
import os
import sys

from vastai.cli.parser import argument
from vastai.cli.display import deindent
from vastai.cli.util import APIKEY_FILE, TFAKEY_FILE
from vastai.cli.utils import get_parser as _get_parser

parser = _get_parser()

TOKEN_VAR = "SERVERLESS_UI_TOKEN"


def key_source(api_key) -> str:
    """Where the CLI found the key, by name, for the startup line; never the key."""
    if not api_key:
        return "none"
    if api_key == os.environ.get("VAST_API_KEY"):
        return "VAST_API_KEY"
    for path in (TFAKEY_FILE, APIKEY_FILE):
        try:
            with open(path, encoding="utf-8") as f:
                if f.read().strip() == api_key:
                    return path
        except OSError:
            pass
    return "--api-key"


def port_number(value) -> int:
    """--port, or SERVERLESS_UI_PORT; the error names both."""
    try:
        port = int(value)
    except ValueError:
        port = 0
    if not 0 < port < 65536:
        raise argparse.ArgumentTypeError(f"{value!r} is not a port (from --port or SERVERLESS_UI_PORT)")
    return port


def seconds(value) -> float:
    """--request-timeout: a positive number of seconds."""
    try:
        n = float(value)
    except ValueError:
        n = 0.0
    if not n > 0:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number of seconds")
    return n


@parser.command(
    argument("--host", default=None,
             help="address to listen on (default SERVERLESS_UI_HOST, else 127.0.0.1: this machine only)"),
    argument("--port", type=port_number, default=None,
             help="port to listen on (default SERVERLESS_UI_PORT, else 8765)"),
    argument("--allowed-host", action="append", default=[], metavar="NAME",
             help="a name or address browsers reach this server by, besides the machine's own, "
                  "such as a reverse proxy's or tunnel's; repeat for more. Callers then need the "
                  "access token"),
    argument("--access-token", default=None, metavar="TOKEN",
             help=f"required from every caller; overrides {TOKEN_VAR}, and like --api-key is visible "
                  "in the process list. Without one, a token is made for each run whenever the "
                  "server holds a key or others can reach it, and printed in the page's link"),
    argument("--request-timeout", type=seconds, default=600.0, metavar="SECONDS",
             help="how long a request may wait for a worker to start answering, waiting for one "
                  "to start or free up included (default 600). Past it the caller gets a 504; a "
                  "stream, once started, runs to its end"),
    argument("--share-traffic", action="store_true",
             help="when others can reach it, also show the proxy traffic made with the server's "
                  "key (prompts and replies) on every page. Always on for localhost"),
    argument("--prefer", action="append", default=[], metavar="ENDPOINT",
             help="endpoint name or id to use when several serve a model; repeat to rank more than one"),
    usage="vastai run serverless-ui [--host HOST] [--port PORT] [--allowed-host NAME] "
          "[--access-token TOKEN] [--request-timeout SECONDS] [--share-traffic] "
          "[--prefer ENDPOINT]",
    help="Serve a local page for testing serverless endpoints, and an OpenAI-compatible proxy",
    epilog=deindent("""
        Serves a web page at http://127.0.0.1:8765 for trying your serverless endpoints: a form for
        each route the endpoint serves, live workers, bursts and load runs, and the same request as
        SDK or OpenAI-client code. It also serves an OpenAI-compatible proxy, so existing clients
        can use an endpoint:

            client = OpenAI(base_url="http://127.0.0.1:8765/e/my-endpoint/v1",
                            api_key=os.environ["SERVERLESS_UI_TOKEN"])

        Uses your API key the way every vastai command does (--api-key, VAST_API_KEY, or the
        saved key), held in memory only. Whenever it holds a key, or others can reach it, every
        caller sends an access token: one is made for each run and printed in the page's link,
        or set SERVERLESS_UI_TOKEN to keep one, which programs using the proxy send as their
        API key. It listens on localhost by default. To
        share it, prefer an SSH tunnel to it (ssh -L 8765:127.0.0.1:8765 HOST); it is plain HTTP,
        so put TLS in front of it before binding beyond localhost:

            export SERVERLESS_UI_TOKEN=$(openssl rand -hex 16)
            vastai run serverless-ui --host 0.0.0.0

        Example: vastai run serverless-ui --prefer my-endpoint
    """),
)
def run__serverless_ui(args):
    """Serve the serverless UI and proxy until interrupted."""
    from vastai.serverless.ui import server  # aiohttp app: loaded only for this command

    # The variables are read here, not as argparse defaults: every command module is imported on
    # every vastai call, so a bad value would otherwise break them all.
    host = args.host or os.environ.get("SERVERLESS_UI_HOST") or "127.0.0.1"
    try:
        port = args.port or port_number(os.environ.get("SERVERLESS_UI_PORT") or "8765")
    except argparse.ArgumentTypeError as e:
        sys.exit(f"vastai run serverless-ui: {e}")
    api_key = getattr(args, "api_key", None) or ""
    token = args.access_token if args.access_token is not None else os.environ.get(TOKEN_VAR, "")
    server.serve(
        api_key=api_key, key_source=key_source(api_key),
        host=host, port=port, allowed_hosts=args.allowed_host,
        access_token=token, token_source="--access-token" if args.access_token is not None else TOKEN_VAR,
        share_traffic=args.share_traffic, prefer=args.prefer,
        vast_web_url=getattr(args, "url", None) or server.VAST_WEB_URL,
        request_timeout=args.request_timeout,
    )
