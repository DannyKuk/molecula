"""openFDA client tests on recorded responses (see `tests/openfda_replay.py`)."""

import logging
import sqlite3
from collections.abc import Callable

import httpx2
import pytest
from pydantic import SecretStr

from molecula.sources.errors import SourceFormatError, SourceNotFound
from molecula.sources.http import SourceClient
from molecula.sources.openfda import API_KEY_HEADER, PAGE_SIZE, OpenFdaClient
from molecula.store.http_cache import HttpCache
from openfda_replay import Replay

FAKE_KEY = "fake-openfda-key-4f2a9c"


@pytest.fixture
def openfda(cache: HttpCache) -> Callable[..., OpenFdaClient]:
    """Makes an openFDA client that replays recorded responses through the store's HTTP cache."""

    def make(
        handler: Replay | None = None,
        *,
        api_key: SecretStr | None = None,
        page_size: int = PAGE_SIZE,
        offline: bool = False,
    ) -> OpenFdaClient:
        http = SourceClient(
            cache,
            offline=offline,
            transport=httpx2.MockTransport(handler or Replay()),
            sleep=lambda _: None,
        )
        return OpenFdaClient(http, api_key=api_key, page_size=page_size)

    return make


def test_imatinib_labels_parse_with_metadata_and_sections(openfda) -> None:
    labels = openfda().labels("imatinib")

    assert len(labels) == 22
    assert len({label.set_id for label in labels}) == 22
    assert {s for label in labels for s in label.openfda.substance_name} == {"IMATINIB MESYLATE"}
    gleevec = next(label for label in labels if label.openfda.brand_name == ["Gleevec"])
    assert gleevec.set_id == "211ef2da-2868-4a77-8055-1cb2cd78e24b"
    assert gleevec.effective_time == "20260713"
    assert gleevec.openfda.generic_name == ["IMATINIB MESYLATE"]
    assert gleevec.openfda.product_type == ["HUMAN PRESCRIPTION DRUG"]
    assert gleevec.sections["mechanism_of_action"][0].startswith("12.1 Mechanism of Action")
    assert "indications_and_usage" in gleevec.sections


def test_label_metadata_is_kept_out_of_the_sections(openfda) -> None:
    [label, *_] = openfda().labels("imatinib")

    assert not {"set_id", "id", "version", "effective_time", "openfda"} & label.sections.keys()


def test_combination_product_lists_both_substances(openfda) -> None:
    labels = openfda().labels("hydrocodone apap")

    assert len(labels) == 6
    for label in labels:
        assert sorted(label.openfda.substance_name) == ["ACETAMINOPHEN", "HYDROCODONE BITARTRATE"]
    assert "Norco" in {brand for label in labels for brand in label.openfda.brand_name}


def test_search_over_two_pages_comes_back_complete(openfda) -> None:
    handler = Replay()

    labels = openfda(handler, page_size=4).labels("hydrocodone apap")

    assert [label.set_id for label in labels] == [
        label.set_id for label in openfda().labels("hydrocodone apap")
    ]
    assert [r.url.params["skip"] for r in handler.requests] == ["0", "4"]


def test_unknown_name_raises_source_not_found(openfda) -> None:
    with pytest.raises(SourceNotFound):
        openfda().labels("paracetamol")


def test_not_found_is_answered_from_the_cache_offline(openfda) -> None:
    with pytest.raises(SourceNotFound):
        openfda().labels("paracetamol")

    with pytest.raises(SourceNotFound):
        openfda(Replay(), offline=True).labels("paracetamol")


def test_unexpected_shape_raises_source_format_error(openfda) -> None:
    handler = Replay({("imatinib", PAGE_SIZE, 0): httpx2.Response(200, json={"error": "busy"})})

    with pytest.raises(SourceFormatError):
        openfda(handler).labels("imatinib")


def test_api_key_is_sent_but_not_stored_or_logged(
    openfda, conn: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    # A 503 first, so the retry warning with the request URL is logged too.
    handler = Replay({("imatinib", PAGE_SIZE, 0): httpx2.Response(503)})

    openfda(handler, api_key=SecretStr(FAKE_KEY)).labels("imatinib")

    assert [r.headers[API_KEY_HEADER] for r in handler.requests] == [FAKE_KEY, FAKE_KEY]
    assert all(FAKE_KEY not in str(r.url) for r in handler.requests)
    stored = conn.execute("SELECT key, url FROM http_cache").fetchall()
    assert len(stored) == 1
    assert all(FAKE_KEY not in value for row in stored for value in row)
    assert "retrying" in caplog.text
    assert FAKE_KEY not in caplog.text


def test_cache_entry_is_shared_with_and_without_a_key(openfda) -> None:
    openfda(api_key=SecretStr(FAKE_KEY)).labels("imatinib")
    handler = Replay()

    assert len(openfda(handler).labels("imatinib")) == 22
    assert handler.requests == []
