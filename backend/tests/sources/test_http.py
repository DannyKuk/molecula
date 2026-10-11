from collections.abc import Callable, Iterator
from pathlib import Path

import httpx2
import pytest
from pydantic import BaseModel

from molecula.sources.errors import (
    OfflineError,
    SourceFormatError,
    SourceNotFound,
    SourceResponseError,
    SourceUnavailable,
)
from molecula.sources.http import MAX_ATTEMPTS, USER_AGENT, SourceClient
from molecula.sources.parsing import parse
from molecula.store.db import connect
from molecula.store.http_cache import HttpCache

PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/imatinib/cids/JSON"
RCSB_SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"

Handler = Callable[[httpx2.Request], httpx2.Response]


class FakeClock:
    """Stands in for time.monotonic and time.sleep: sleeping advances the clock."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class Recorder:
    """A MockTransport handler that replays `responses` in order and records each request."""

    def __init__(self, *responses: httpx2.Response | Exception) -> None:
        self._responses = iter(responses)
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return response


class Compound(BaseModel):
    cid: int


def ok(body: bytes = b'{"ok": true}') -> httpx2.Response:
    return httpx2.Response(200, content=body, headers={"content-type": "application/json"})


@pytest.fixture
def cache(tmp_path: Path) -> Iterator[HttpCache]:
    conn = connect(tmp_path / "molecula.db")
    yield HttpCache(conn)
    conn.close()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def make_client(cache: HttpCache, clock: FakeClock) -> Callable[..., SourceClient]:
    def make(handler: Handler, *, offline: bool = False) -> SourceClient:
        return SourceClient(
            cache,
            offline=offline,
            transport=httpx2.MockTransport(handler),
            clock=clock.time,
            sleep=clock.sleep,
        )

    return make


def test_returns_the_response_and_sends_the_user_agent(make_client) -> None:
    handler = Recorder(ok(b'{"cid": 5291}'))

    response = make_client(handler).get(PUBCHEM)

    assert response.json() == {"cid": 5291}
    assert handler.requests[0].headers["user-agent"] == USER_AGENT


def test_headers_are_sent_but_left_out_of_the_cache_key(make_client) -> None:
    sending = Recorder(ok(b'{"v": 1}'))
    make_client(sending).get(PUBCHEM, headers={"X-Api-Key": "first"})
    handler = Recorder()

    response = make_client(handler).get(PUBCHEM, headers={"X-Api-Key": "second"})

    assert sending.requests[0].headers["x-api-key"] == "first"
    assert response.json() == {"v": 1}
    assert handler.requests == []


def test_spaces_requests_to_the_same_source(make_client, clock: FakeClock) -> None:
    client = make_client(Recorder(ok(), ok(), ok()))

    for name in ("imatinib", "aspirin", "caffeine"):
        client.get(f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/cids/JSON")

    assert clock.sleeps == [pytest.approx(0.25), pytest.approx(0.25)]


def test_sources_are_limited_separately(make_client, clock: FakeClock) -> None:
    client = make_client(Recorder(ok(), ok()))

    client.get(PUBCHEM)
    client.get("https://www.ebi.ac.uk/chembl/api/data/target/CHEMBL1862.json")

    assert clock.sleeps == []


def test_hosts_of_one_source_share_its_limit(make_client, clock: FakeClock) -> None:
    client = make_client(Recorder(ok(), ok()))

    client.post_json(RCSB_SEARCH, {"query": {}})
    client.get("https://data.rcsb.org/rest/v1/core/chemcomp/STI")

    assert clock.sleeps == [pytest.approx(0.2)]


def test_unknown_host_is_refused_before_any_request(make_client) -> None:
    handler = Recorder()

    with pytest.raises(ValueError, match=r"example.org"):
        make_client(handler).get("https://example.org/data")

    assert handler.requests == []


def test_retries_a_503_then_succeeds(make_client, clock: FakeClock) -> None:
    handler = Recorder(httpx2.Response(503), ok())

    response = make_client(handler).get(PUBCHEM)

    assert response.status_code == 200
    assert len(handler.requests) == 2
    assert clock.sleeps == [1.0]


def test_retries_connection_errors(make_client) -> None:
    handler = Recorder(httpx2.ConnectError("refused"), ok())

    assert make_client(handler).get(PUBCHEM).status_code == 200


def test_honours_retry_after(make_client, clock: FakeClock) -> None:
    handler = Recorder(httpx2.Response(429, headers={"Retry-After": "7"}), ok())

    make_client(handler).get(PUBCHEM)

    assert clock.sleeps == [7.0]


def test_retry_after_zero_retries_without_backoff(make_client, clock: FakeClock) -> None:
    handler = Recorder(httpx2.Response(503, headers={"Retry-After": "0"}), ok())

    make_client(handler).get(PUBCHEM)

    # The retry still waits for the rate limit's next slot.
    assert clock.sleeps == [0.0, pytest.approx(0.25)]


def test_backs_off_exponentially_then_gives_up(make_client, clock: FakeClock) -> None:
    handler = Recorder(*[httpx2.Response(503)] * MAX_ATTEMPTS)

    with pytest.raises(SourceUnavailable, match="HTTP 503"):
        make_client(handler).get(PUBCHEM)

    assert len(handler.requests) == MAX_ATTEMPTS
    assert clock.sleeps == [1.0, 2.0, 4.0, 8.0]


def test_not_found_raises_source_not_found(make_client) -> None:
    with pytest.raises(SourceNotFound):
        make_client(Recorder(httpx2.Response(404))).get(PUBCHEM)


def test_other_errors_are_not_retried(make_client) -> None:
    handler = Recorder(httpx2.Response(400))

    with pytest.raises(SourceResponseError) as error:
        make_client(handler).get(PUBCHEM)

    assert error.value.status == 400
    assert len(handler.requests) == 1


def test_offline_raises_before_any_request(make_client) -> None:
    handler = Recorder()

    with pytest.raises(OfflineError):
        make_client(handler, offline=True).get(PUBCHEM)

    assert handler.requests == []


def test_cached_response_is_served_without_a_request(make_client) -> None:
    first = Recorder(ok(b'{"cid": 5291}'))
    make_client(first).get(PUBCHEM)
    second = Recorder()

    response = make_client(second).get(PUBCHEM)

    assert response.json() == {"cid": 5291}
    assert response.headers["content-type"] == "application/json"
    assert second.requests == []


def test_cache_is_served_when_offline(make_client) -> None:
    make_client(Recorder(ok(b'{"cid": 5291}'))).get(PUBCHEM)

    assert make_client(Recorder(), offline=True).get(PUBCHEM).json() == {"cid": 5291}


def test_refresh_forces_a_request_and_updates_the_cache(make_client) -> None:
    make_client(Recorder(ok(b'{"v": 1}'))).get(PUBCHEM)
    refreshing = Recorder(ok(b'{"v": 2}'))

    assert make_client(refreshing).get(PUBCHEM, refresh=True).json() == {"v": 2}
    assert len(refreshing.requests) == 1
    assert make_client(Recorder()).get(PUBCHEM).json() == {"v": 2}


def test_not_found_is_cached_and_raised_again_offline(make_client) -> None:
    with pytest.raises(SourceNotFound):
        make_client(Recorder(httpx2.Response(404))).get(PUBCHEM)
    handler = Recorder()

    with pytest.raises(SourceNotFound):
        make_client(handler, offline=True).get(PUBCHEM)

    assert handler.requests == []


def test_refresh_asks_again_after_a_cached_not_found(make_client) -> None:
    with pytest.raises(SourceNotFound):
        make_client(Recorder(httpx2.Response(404))).get(PUBCHEM)

    assert make_client(Recorder(ok())).get(PUBCHEM, refresh=True).json() == {"ok": True}


def test_other_failures_are_not_cached(make_client) -> None:
    with pytest.raises(SourceResponseError):
        make_client(Recorder(httpx2.Response(400))).get(PUBCHEM)
    handler = Recorder(ok())

    make_client(handler).get(PUBCHEM)

    assert len(handler.requests) == 1


def test_posts_with_different_bodies_are_cached_apart(make_client) -> None:
    make_client(Recorder(ok(b'["STI"]'))).post_json(RCSB_SEARCH, {"q": "imatinib"})
    handler = Recorder(ok(b'["CFF"]'))

    response = make_client(handler).post_json(RCSB_SEARCH, {"q": "caffeine"})

    assert response.json() == ["CFF"]
    assert len(handler.requests) == 1


def test_a_body_that_fails_to_parse_is_asked_for_again(make_client) -> None:
    with pytest.raises(SourceFormatError):
        parse(make_client(Recorder(ok(b'{"error": "busy"}'))).get(PUBCHEM), Compound)
    handler = Recorder(ok(b'{"cid": 5291}'))

    assert parse(make_client(handler).get(PUBCHEM), Compound).cid == 5291
    assert len(handler.requests) == 1


def test_a_cached_body_that_fails_to_parse_is_dropped(make_client) -> None:
    make_client(Recorder(ok(b'{"error": "busy"}'))).get(PUBCHEM)
    with pytest.raises(SourceFormatError):
        parse(make_client(Recorder()).get(PUBCHEM), Compound)
    handler = Recorder(ok(b'{"cid": 5291}'))

    assert parse(make_client(handler).get(PUBCHEM), Compound).cid == 5291
    assert len(handler.requests) == 1


def test_a_body_that_parses_stays_cached(make_client) -> None:
    parse(make_client(Recorder(ok(b'{"cid": 5291}'))).get(PUBCHEM), Compound)
    handler = Recorder()

    assert parse(make_client(handler).get(PUBCHEM), Compound).cid == 5291
    assert handler.requests == []


def test_offline_a_cached_body_that_fails_to_parse_keeps_failing_to_parse(make_client) -> None:
    make_client(Recorder(ok(b'{"error": "busy"}'))).get(PUBCHEM)
    offline = make_client(Recorder(), offline=True)

    for _ in range(2):
        with pytest.raises(SourceFormatError):
            parse(offline.get(PUBCHEM), Compound)
