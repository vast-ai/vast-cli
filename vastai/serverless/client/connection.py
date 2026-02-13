import aiohttp
import asyncio
import random
import json
from typing import AsyncIterator, Dict, Optional, Union

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
    Caller is responsible for reading/closing via 'async with'.
    """
    request_fn = session.get if method == "GET" else session.post
    return request_fn(url + route, **kwargs)

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
) -> Union[dict, AsyncIterator[dict]]:
    """
    Make an HTTP request with capped exponential backoff + jitter.

    - On success (non-stream): returns parsed JSON (dict/list).
    - On success (stream=True): returns an async iterator yielding parsed JSON objects.
    - Raises Exception with last status/text after exhausting retries.
    """
    method = method.upper()
    body = body or {}
    # copy so we don't mutate caller's dict
    params = {**(params or {})}
    params["api_key"] = api_key

    headers = {"Authorization": f"Bearer {api_key}"}

    session = await client._get_session()
    ssl_context = await client.get_ssl_context() if client else None

    last_text = ""
    last_status = None

    if stream:
        async def _stream_gen() -> AsyncIterator[dict]:
            nonlocal last_text, last_status
            for attempt in range(1, retries + 1):
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
                    async with await _open_once(
                        session=session,
                        method=method,
                        url=url,
                        route=route,
                        kwargs=kwargs,
                    ) as resp:
                        last_status = resp.status
                        if resp.status != 200:
                            text = await resp.text()
                            last_text = text
                            if not _retryable(resp.status) or attempt == retries:
                                raise Exception(f"HTTP {resp.status} from {url + route}: {text}")
                            await asyncio.sleep(_backoff_delay(attempt))
                            continue

                        async for obj in _iter_sse_json(resp):
                            yield obj

                        return

                except Exception as ex:
                    client.logger.error(f"Stream attempt {attempt} failed: {ex}")
                    if attempt == retries:
                        raise
                    await asyncio.sleep(_backoff_delay(attempt))

        return _stream_gen()

    # Non-streaming path
    for attempt in range(1, retries + 1):
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
            async with await _open_once(
                session=session,
                method=method,
                url=url,
                route=route,
                kwargs=kwargs,
            ) as resp:
                last_status = resp.status
                text = await resp.text()
                last_text = text

                if resp.status == 200:
                    try:
                        return await resp.json(content_type=None)
                    except Exception:
                        raise Exception(f"Invalid JSON from {url + route}:\n{text}")

                if not _retryable(resp.status):
                    raise Exception(f"HTTP {resp.status} from {url + route}: {text}")

                await asyncio.sleep(_backoff_delay(attempt))

        except Exception as ex:
            client.logger.error(f"Attempt {attempt} failed: {ex}")
            if attempt == retries:
                break
            await asyncio.sleep(_backoff_delay(attempt))

    raise Exception(
        f"Too many retries for {url + route} (last_status={last_status}, last_text={last_text[:256]!r})"
    )
