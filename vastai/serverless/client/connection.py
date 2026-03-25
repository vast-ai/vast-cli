# connection.py
import aiohttp
import asyncio
import random
import json
from typing import AsyncIterator, Dict, Optional, Any

_JITTER_CAP_SECONDS = 5.0

def _retryable(status: int) -> bool:
    return status in (408, 429) or (500 <= status < 600)

def _backoff_delay(attempt: int) -> float:
    # capped exponential backoff with jitter
    return min((2 ** attempt) + random.uniform(0, 1), _JITTER_CAP_SECONDS)

def _build_kwargs(
    *,
    headers: Dict[str, str],
    params: Dict[str, str],
    ssl_context,
    timeout: Optional[float],
    body: Optional[dict],
    method: str,
    stream: bool,
) -> Dict:
    return {
        "headers": headers,
        "params": params,
        "ssl": ssl_context,
        "timeout": aiohttp.ClientTimeout(total=None if stream else timeout),
        **({"json": body} if method != "GET" and body else {}),
    }

async def _iter_sse_json(resp: aiohttp.ClientResponse) -> AsyncIterator[dict]:
    """
    Yield JSON objects from an SSE/text stream. Accepts lines starting with 'data:' or raw JSONL.
    """
    buffer = b""
    async for chunk in resp.content.iter_any():
        if not chunk:
            continue
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue
            if line.startswith(b"data:"):
                line = line[5:].strip()
            try:
                yield json.loads(line.decode("utf-8"))
            except Exception:
                # Ignore keepalives/bad fragments
                continue

    # flush tail if present
    tail = buffer.strip()
    if tail:
        try:
            yield json.loads(tail.decode("utf-8"))
        except Exception:
            pass

async def _open_once(
    *,
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    route: str,
    kwargs: Dict,
):
    """
    Execute one HTTP attempt and return the aiohttp response object.
    Caller is responsible for reading/closing via 'async with' or resp.release()/resp.close().
    """
    request_fn = session.get if method == "GET" else session.post
    return await request_fn(url + route, **kwargs)

async def _make_request(
    client,
    route: str,
    api_key: str,
    url: str = "",
    body: Optional[dict] = None,
    params: Optional[dict] = None,
    method: str = "GET",
    retries: int = 5,
    timeout: float = 30,
    stream: bool = False,
) -> Dict[str, Any]:
    """
    Make an HTTP request with capped exponential backoff + jitter, returning a structured result.

    - Never raises for HTTP non-2xx responses. Instead returns result with ok=False and status/text/json.
    - Raises only for "mechanical" failures (aiohttp/transport) and invalid JSON on successful (2xx) responses.

    Return shape (non-stream):
      {
        "ok": bool,
        "status": int|None,
        "url": str,
        "headers": dict,
        "text": str,
        "json": Any|None,
        "retryable": bool,
        "attempt": int
      }

    Return shape (stream=True, ok=True adds "stream"):
      { ... , "stream": AsyncIterator[dict] }
    """
    method = method.upper()
    body = body or {}
    params = {**(params or {})}
    params["api_key"] = api_key

    headers = {"Authorization": f"Bearer {api_key}"}

    session = await client._get_session()
    ssl_context = await client.get_ssl_context() if client else None

    full_url = url + route

    last_result: Dict[str, Any] = {
        "ok": False,
        "status": None,
        "url": full_url,
        "headers": {},
        "text": "",
        "json": None,
        "retryable": False,
        "attempt": 0,
    }

    # STREAMING PATH (open upfront so we can return status + a stream iterator)
    if stream:
        for attempt in range(1, retries + 1):
            last_result["attempt"] = attempt
            try:
                kwargs = _build_kwargs(
                    headers=headers,
                    params=params,
                    ssl_context=ssl_context,
                    timeout=timeout,
                    body=body,
                    method=method,
                    stream=True,
                )

                resp = await _open_once(
                    session=session,
                    method=method,
                    url=url,
                    route=route,
                    kwargs=kwargs,
                )

                status = resp.status
                last_result["status"] = status
                last_result["headers"] = dict(resp.headers)
                last_result["retryable"] = _retryable(status)

                if status < 200 or status >= 300:
                    text = await resp.text()
                    last_result["text"] = text

                    # best-effort JSON parse (do not raise)
                    try:
                        if text and text.lstrip().startswith(("{", "[")):
                            last_result["json"] = json.loads(text)
                    except Exception:
                        pass

                    resp.release()

                    if last_result["retryable"] and attempt < retries:
                        await asyncio.sleep(_backoff_delay(attempt))
                        continue

                    # final non-2xx: return what we saw
                    return last_result

                # 2xx: return stream iterator that owns the response lifetime
                last_result["ok"] = True
                last_result["text"] = ""  # streaming: we don't pre-read body

                async def _stream_iter() -> AsyncIterator[dict]:
                    try:
                        async for obj in _iter_sse_json(resp):
                            yield obj
                    finally:
                        try:
                            resp.release()
                        except Exception:
                            pass

                last_result["stream"] = _stream_iter()
                return last_result

            except asyncio.TimeoutError as ex:
                if attempt == retries:
                    raise TimeoutError(f"Request to {full_url} timed out after {timeout}s") from ex
                await asyncio.sleep(_backoff_delay(attempt))
            except Exception as ex:
                if attempt == retries:
                    raise ex
                await asyncio.sleep(_backoff_delay(attempt))

        return last_result

    # NON-STREAMING PATH
    for attempt in range(1, retries + 1):
        last_result["attempt"] = attempt
        try:
            kwargs = _build_kwargs(
                headers=headers,
                params=params,
                ssl_context=ssl_context,
                timeout=timeout,
                body=body,
                method=method,
                stream=False,
            )

            async with await (session.get(full_url, **kwargs) if method == "GET" else session.post(full_url, **kwargs)) as resp:
                status = resp.status
                text = await resp.text()

                result: Dict[str, Any] = {
                    "ok": 200 <= status < 300,
                    "status": status,
                    "url": full_url,
                    "headers": dict(resp.headers),
                    "text": text,
                    "json": None,
                    "retryable": _retryable(status),
                    "attempt": attempt,
                }

                if result["ok"]:
                    # Successful responses are expected to be JSON; invalid JSON is a hard failure
                    try:
                        result["json"] = await resp.json(content_type=None)
                    except Exception:
                        raise Exception(f"Invalid JSON from {full_url}:\n{text}")

                    # Debug: log the exact response
                    if hasattr(client, 'logger'):
                        client.logger.debug(f"_make_request response from {route}: {result}")

                    return result

                # Non-2xx: best-effort JSON parse (do not raise)
                try:
                    if text and text.lstrip().startswith(("{", "[")):
                        result["json"] = json.loads(text)
                except Exception:
                    pass

                # Retry only if retryable and attempts remain
                if result["retryable"] and attempt < retries:
                    last_result = result
                    await asyncio.sleep(_backoff_delay(attempt))
                    continue

                # Debug: log the exact response for non-2xx
                if hasattr(client, 'logger'):
                    client.logger.debug(f"_make_request response from {route}: {result}")

                return result

        except asyncio.TimeoutError as ex:
            if attempt == retries:
                raise TimeoutError(f"Request to {full_url} timed out after {timeout}s") from ex
            await asyncio.sleep(_backoff_delay(attempt))
        except Exception as ex:
            if attempt == retries:
                raise ex
            await asyncio.sleep(_backoff_delay(attempt))

    return last_result
