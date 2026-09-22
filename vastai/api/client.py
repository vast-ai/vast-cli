"""HTTP client for the Vast.ai API."""

import os
import re
import json
import sys
import shlex
import time
import requests
from urllib.parse import quote_plus, urlsplit
from typing import Dict, Optional

from vastai.utils import VERSION

try:
    import curlify
except ImportError:
    curlify = None


# Emoji support
_HAS_EMOJI = sys.stdout.encoding and 'utf' in sys.stdout.encoding.lower()
INFO = "\u2139\ufe0f" if _HAS_EMOJI else "[i]"

server_url_default = os.getenv("VAST_URL") or "https://console.vast.ai"

# Status codes that indicate a transient server-side issue worth retrying.
# 429 = rate limited; 502/503/504 = gateway/upstream errors that usually clear.
_RETRYABLE_STATUS = {429, 502, 503, 504}

# Transport-level exceptions worth retrying (network hiccups, slow peers).
# Other requests.RequestException subclasses (e.g. InvalidURL, TooManyRedirects)
# propagate immediately — retrying them would just burn time.
_RETRYABLE_EXC = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
)

# Default per-request timeout. Conservative enough for slow operations like
# log retrieval and instance creation; callers can override per-call.
_DEFAULT_TIMEOUT_SECONDS = 120


def as_curl_command(prep) -> str:
    """Render a prepared request as a runnable, one-flag-per-line curl command.

    Only the noise headers are dropped. ``Authorization`` stays: since #471 it
    is the only thing authenticating the request, and a printed command the
    caller cannot run is worse than printing none at all.
    """
    tokens = shlex.split(curlify.to_curl(prep))
    lines, i = [tokens[0]], 1
    while i < len(tokens):
        token = tokens[i]
        value = tokens[i + 1] if i + 1 < len(tokens) else None
        if token.startswith("-") and value is not None:
            i += 2
            if token == "-H" and not value.lower().startswith("authorization:"):
                continue
            lines.append(f"{token} {shlex.quote(value)}")
        else:
            lines.append(shlex.quote(token))
            i += 1
    return " \\\n  ".join(lines)


def same_site(a: Optional[str], b: Optional[str]) -> bool:
    """Whether two hostnames sit under the same parent domain."""
    if not a or not b:
        return False
    a, b = a.lower(), b.lower()
    return a == b or a.split(".")[-2:] == b.split(".")[-2:]


class VastSession(requests.Session):
    """A session that keeps our auth header across redirects within our domain.

    ``requests`` drops ``Authorization`` on any redirect that changes host. That
    is right for arbitrary hosts and wrong for ours: candidate.vast.ai 301s to
    candidate-server.vast.ai for every path without a trailing slash, so the
    request lands unauthenticated and the server answers 403. The key used to
    ride in the query string, which redirects preserve, which is why moving it
    to a header (#471) surfaced this.
    """

    def __init__(self, server_url: str):
        super().__init__()
        self._host = urlsplit(server_url).hostname

    def rebuild_auth(self, prepared_request, response):
        if same_site(urlsplit(prepared_request.url).hostname, self._host):
            return  # still our own domain: keep the header we set
        super().rebuild_auth(prepared_request, response)


class VastClient:
    """HTTP client for Vast.ai API requests."""

    def __init__(self, api_key=None, server_url=None, retry=3, explain=False, curl=False,
                 timeout=_DEFAULT_TIMEOUT_SECONDS, client_type="sdk"):
        self.api_key = api_key
        self.server_url = server_url or server_url_default
        self.retry = retry
        self.explain = explain
        self.curl = curl
        self.timeout = timeout
        self.user_agent = f"vastai-{client_type}/{VERSION}"

    def _build_url(self, subpath: str, query_args: Optional[Dict] = None) -> str:
        """Build full API URL from subpath and optional query args."""
        if query_args is None:
            query_args = {}
        if not re.match(r"^/api/v(\d)+/", subpath):
            subpath = "/api/v0" + subpath

        if query_args:
            query_json = "&".join(
                "{x}={y}".format(x=x, y=quote_plus(y if isinstance(y, str) else json.dumps(y)))
                for x, y in query_args.items()
            )
            result = self.server_url + subpath + "?" + query_json
        else:
            result = self.server_url + subpath

        if self.explain:
            print("query args:")
            print(query_args)
            print("")
            print(f"base: {self.server_url + subpath + '?'} + query: ")
            print(result)
            print("")
        return result

    def _build_headers(self) -> Dict:
        """Build request headers with auth."""
        result = {"User-Agent": self.user_agent}
        if self.api_key is not None:
            result["Authorization"] = "Bearer " + self.api_key
        return result

    def _request(self, method: str, url: str, headers: Dict, json_data=None,
                 timeout: Optional[float] = None) -> requests.Response:
        """Execute HTTP request with retry/timeout/exception handling.

        Retries are attempted on:
          - ``_RETRYABLE_STATUS`` codes (429, 502, 503, 504)
          - ``_RETRYABLE_EXC`` transport exceptions (ConnectionError, Timeout)

        After exhausting retries, the last response is returned (for status-code
        retries) or the last exception is re-raised (for transport exceptions).
        Non-retryable ``requests`` exceptions propagate immediately.
        """
        effective_timeout = timeout if timeout is not None else self.timeout
        t = 0.15
        r = None
        for i in range(0, self.retry):
            req = requests.Request(method=method, url=url, headers=headers, json=json_data)
            session = VastSession(self.server_url)
            prep = session.prepare_request(req)
            if self.explain:
                print(f"\n{INFO}  Prepared Request:")
                print(f"{prep.method} {prep.url}")
                print(f"Headers: {json.dumps(headers, indent=1)}")
                print(f"Body: {json.dumps(json_data, indent=1)}" + "\n" + "_" * 100 + "\n")

            if self.curl:
                if curlify is None:
                    print("curlify package is required for --curl mode. Install with: pip install curlify")
                    sys.exit(1)
                print("\n" + as_curl_command(prep) + "\n")
                sys.exit(0)

            try:
                r = session.send(prep, timeout=effective_timeout)
            except _RETRYABLE_EXC:
                if i == self.retry - 1:
                    raise
                time.sleep(t)
                t *= 1.5
                continue

            if r.status_code in _RETRYABLE_STATUS and i < self.retry - 1:
                time.sleep(t)
                t *= 1.5
                continue
            break
        return r

    def get(self, subpath: str, query_args: Optional[Dict] = None, json_data=None,
            timeout: Optional[float] = None) -> requests.Response:
        url = self._build_url(subpath, query_args)
        headers = self._build_headers()
        return self._request('GET', url, headers, json_data, timeout=timeout)

    def post(self, subpath: str, query_args: Optional[Dict] = None, json_data=None,
             timeout: Optional[float] = None) -> requests.Response:
        url = self._build_url(subpath, query_args)
        headers = self._build_headers()
        return self._request('POST', url, headers, json_data if json_data is not None else {}, timeout=timeout)

    def put(self, subpath: str, query_args: Optional[Dict] = None, json_data=None,
            timeout: Optional[float] = None) -> requests.Response:
        url = self._build_url(subpath, query_args)
        headers = self._build_headers()
        return self._request('PUT', url, headers, json_data if json_data is not None else {}, timeout=timeout)

    def delete(self, subpath: str, query_args: Optional[Dict] = None, json_data=None,
               timeout: Optional[float] = None) -> requests.Response:
        url = self._build_url(subpath, query_args)
        headers = self._build_headers()
        return self._request('DELETE', url, headers, json_data if json_data is not None else {}, timeout=timeout)
