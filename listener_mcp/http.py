"""One shared HTTP client with polite defaults: a real User-Agent, timeouts,
and exponential backoff on 429/5xx. Every source goes through this so rate
limiting lives in one place."""

import time

import httpx

USER_AGENT = "ticmint-internet-listener/1.0 (+https://github.com/dannygrowthmarketing/ticmint-internet-listener)"

_client: httpx.Client | None = None


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            timeout=httpx.Timeout(20.0, connect=10.0),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )
    return _client


class SourceError(RuntimeError):
    """Raised when a source is unreachable after retries. The agent records it
    in the run log and carries on with the other sources."""


def get_json(url: str, *, params=None, headers=None, retries: int = 3, method: str = "GET", data=None, auth=None):
    delay = 2.0
    last = None
    for attempt in range(retries + 1):
        try:
            r = client().request(method, url, params=params, headers=headers, data=data, auth=auth)
        except httpx.HTTPError as e:
            last = f"{type(e).__name__}: {e}"
        else:
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}"
            if r.status_code not in (429, 500, 502, 503, 504):
                break
            retry_after = r.headers.get("retry-after")
            if retry_after and retry_after.isdigit():
                delay = min(float(retry_after), 60.0)
        if attempt < retries:
            time.sleep(delay)
            delay *= 2
    raise SourceError(f"{url} -> {last}")
