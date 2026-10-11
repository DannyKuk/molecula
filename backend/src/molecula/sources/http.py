import hashlib
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from importlib.metadata import version
from threading import Lock
from typing import Any

import httpx2

from molecula.sources.errors import (
    OfflineError,
    SourceNotFound,
    SourceResponseError,
    SourceUnavailable,
)
from molecula.store.http_cache import CachedResponse, HttpCache

logger = logging.getLogger(__name__)

REQUESTS_PER_SECOND = {"pubchem": 4.0, "chembl": 4.0, "rcsb": 5.0, "openfda": 4.0}
HOST_SOURCES = {
    "pubchem.ncbi.nlm.nih.gov": "pubchem",
    "www.ebi.ac.uk": "chembl",
    "search.rcsb.org": "rcsb",
    "data.rcsb.org": "rcsb",
    "files.rcsb.org": "rcsb",
    "api.fda.gov": "openfda",
}
# PubChem signals throttling with 503 rather than 429.
RETRY_STATUSES = frozenset({429, 503})
MAX_ATTEMPTS = 5
BACKOFF_SECONDS = 1.0
MAX_WAIT_SECONDS = 60.0
TIMEOUT = httpx2.Timeout(30.0, connect=10.0)
USER_AGENT = f"molecula/{version('molecula')} (+https://github.com/DannyKuk/molecula)"


class RateLimiter:
    """Spaces calls at least `1 / per_second` apart, across threads."""

    def __init__(
        self, per_second: float, clock: Callable[[], float], sleep: Callable[[float], None]
    ) -> None:
        self._interval = 1.0 / per_second
        self._clock = clock
        self._sleep = sleep
        self._next_slot = 0.0
        self._lock = Lock()

    def wait(self) -> None:
        with self._lock:
            delay = self._next_slot - self._clock()
            if delay > 0:
                self._sleep(delay)
            self._next_slot = self._clock() + self._interval


class SourceClient:
    """The one HTTP client every source uses: rate limits, retries, OFFLINE and the cache.

    Successful responses and 404s are cached in the store and served from there on the next call,
    also when offline. `refresh=True` skips the cache and overwrites the entry.
    """

    def __init__(
        self,
        cache: HttpCache,
        *,
        offline: bool,
        transport: httpx2.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> None:
        self._cache = cache
        self._offline = offline
        self._sleep = sleep
        self._max_attempts = max_attempts
        self._limiters = {
            source: RateLimiter(rate, clock, sleep) for source, rate in REQUESTS_PER_SECOND.items()
        }
        self._http = httpx2.Client(
            transport=transport,
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )

    def get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        refresh: bool = False,
    ) -> httpx2.Response:
        """GET through the cache. `headers` are sent but not part of the cache key, stored URL or
        log lines, so they suit credentials, never anything that changes the answer."""
        request = self._http.build_request("GET", url, params=params, headers=headers)
        return self._send(request, refresh)

    def post_json(
        self, url: str, payload: dict[str, Any], *, refresh: bool = False
    ) -> httpx2.Response:
        return self._send(self._http.build_request("POST", url, json=payload), refresh)

    def close(self) -> None:
        self._http.close()

    def _send(self, request: httpx2.Request, refresh: bool) -> httpx2.Response:
        key = cache_key(request)
        if not refresh and (cached := self._cache.get(key)):
            return checked(to_response(cached, request))
        if self._offline:
            raise OfflineError(f"OFFLINE=1, not requesting {request.url}")
        response = self._send_with_retries(request)
        # A 404 is an answer too (an unknown name, no 3D conformer), so it is cached and stays
        # available offline; other failures are not.
        if response.is_success or response.status_code == 404:
            self._cache.put(
                key,
                str(request.url),
                CachedResponse(
                    response.status_code, response.headers.get("content-type"), response.content
                ),
            )
        return checked(response)

    def _send_with_retries(self, request: httpx2.Request) -> httpx2.Response:
        limiter = self._limiter_for(request.url.host)
        for attempt in range(1, self._max_attempts + 1):
            limiter.wait()
            try:
                response = self._http.send(request)
            except httpx2.TransportError as error:
                failure, wait = type(error).__name__, backoff(attempt)
            else:
                if response.status_code not in RETRY_STATUSES:
                    return response
                failure = f"HTTP {response.status_code}"
                wait = retry_after(response)
                if wait is None:
                    wait = backoff(attempt)
            if attempt < self._max_attempts:
                wait = min(wait, MAX_WAIT_SECONDS)
                logger.warning("%s: %s, retrying in %.1fs", request.url, failure, wait)
                self._sleep(wait)
        raise SourceUnavailable(f"{request.url}: {failure} after {self._max_attempts} attempts")

    def _limiter_for(self, host: str) -> RateLimiter:
        if host not in HOST_SOURCES:
            raise ValueError(f"no rate limit configured for {host}; add it to HOST_SOURCES")
        return self._limiters[HOST_SOURCES[host]]


def cache_key(request: httpx2.Request) -> str:
    digest = hashlib.sha256(f"{request.method} {request.url}\n".encode())
    digest.update(request.content)
    return digest.hexdigest()


def to_response(cached: CachedResponse, request: httpx2.Request) -> httpx2.Response:
    headers = {"content-type": cached.content_type} if cached.content_type else {}
    return httpx2.Response(cached.status, headers=headers, content=cached.body, request=request)


def checked(response: httpx2.Response) -> httpx2.Response:
    if response.is_success:
        return response
    if response.status_code == 404:
        raise SourceNotFound(str(response.request.url))
    raise SourceResponseError(str(response.request.url), response.status_code)


def backoff(attempt: int) -> float:
    return BACKOFF_SECONDS * 2 ** (attempt - 1)


def retry_after(response: httpx2.Response) -> float | None:
    """Seconds from a `Retry-After` header, which is either a number or an HTTP date."""
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        pass
    try:
        return max((parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds(), 0.0)
    except TypeError, ValueError:
        return None
