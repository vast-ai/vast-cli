"""HTTP client for the Vast.ai API."""

import os
import re
import json
import sys
import time
import requests
from urllib.parse import quote_plus
from typing import Dict, Optional

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


class VastClient:
    """HTTP client for Vast.ai API requests."""

    def __init__(self, api_key=None, server_url=None, retry=3, explain=False, curl=False,
                 timeout=_DEFAULT_TIMEOUT_SECONDS):
        self.api_key = api_key
        self.server_url = server_url or server_url_default
        self.retry = retry
        self.explain = explain
        self.curl = curl
        self.timeout = timeout

    def _build_url(self, subpath: str, query_args: Optional[Dict] = None) -> str:
        """Build full API URL from subpath and optional query args."""
        if query_args is None:
            query_args = {}
        if self.api_key is not None:
            query_args["api_key"] = self.api_key
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
        result = {}
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
            session = requests.Session()
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
                as_curl = curlify.to_curl(prep)
                simple = re.sub(r" -H '[^']*'", '', as_curl)
                parts = re.split(r'(?=\s+-\S+)', simple)
                pp = parts[-1].split("'")
                pp[-3] += "\n "
                parts = [*parts[:-1], *[x.rstrip() for x in "'".join(pp).split("\n")]]
                print("\n" + ' \\\n  '.join(parts).strip() + "\n")
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
