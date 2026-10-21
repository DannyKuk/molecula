"""openFDA label searches recorded from the live API on 2026-10-11 without an API key.

The fixtures are hand-trimmed: every section string is cut to its first 40 characters (an Rx
label is 40-170k characters) and the JSON is re-indented. Everything else, including the
`openfda` block and `meta`, is as recorded.

- imatinib: 22 labels, all single-ingredient imatinib mesylate.
- "hydrocodone apap": 6 combination labels whose generic name is written HYDROCODONE/APAP or
  HYDROCODONE APAP, each with two substance names. Recorded once with the client's default page
  size and once with `limit=4`, which takes two pages (`*_limit4_page1.json`, `*_page2.json`).
- paracetamol: openFDA has US labels only, so it answers 404 with `NOT_FOUND`.

Two searches were recorded on 2026-10-12 (with an API key, which changes nothing in the answer)
and cut down to a few chosen labels each, with `meta.results` set to match; the labels themselves
are trimmed like the others:

- ibuprofen (1147 labels): Caldolor (intravenous, the only single-ingredient Rx label with a
  `mechanism_of_action` section), three oral ibuprofen tablet labels (the newest keeps the first
  250 characters of `clinical_pharmacology`, which hold the mechanism sentence), an ibuprofen +
  famotidine label, Advil Menstrual Pain (ibuprofen sodium, OTC), a store-brand OTC label and
  Advil Dual Action (ibuprofen + acetaminophen, OTC).
- acetaminophen (3284 labels): two generic Rx injection labels, Apadaz (benzhydrocodone +
  acetaminophen, an oral brand label with a mechanism section), an oral hydrocodone +
  acetaminophen label, Feverall (rectal, OTC), Tylenol 8 HR and a store-brand children's label
  (oral, OTC), and Advil Dual Action.

Count queries for the label update (#341), recorded on 2026-10-21 without an API key and not
trimmed. They ask about the canonical labels `canonical_labels` picks from the three searches
above (Gleevec 20260713, two acetaminophen and two ibuprofen labels):

- `count_listed.json`: all five set_ids are listed; `count_listed_gleevec.json`: Gleevec alone,
  the request that reads `meta.last_updated` (2026-10-20).
- `count_newer_none.json`: none of the five has a newer version (404); `count_newer_gleevec.json`:
  the same with Gleevec's effective time set to 20200101, so Gleevec comes back.
"""

import re
from pathlib import Path

import httpx2

from molecula.sources.openfda import PAGE_SIZE

FIXTURES = Path(__file__).parent / "fixtures" / "openfda"
LABEL_PATH = "/drug/label.json"

RECORDED: dict[tuple[str, int, int], tuple[int, str]] = {
    ("imatinib", PAGE_SIZE, 0): (200, "labels_imatinib.json"),
    ("hydrocodone apap", PAGE_SIZE, 0): (200, "labels_hydrocodone_apap.json"),
    ("hydrocodone apap", 4, 0): (200, "labels_hydrocodone_apap_limit4_page1.json"),
    ("hydrocodone apap", 4, 4): (200, "labels_hydrocodone_apap_limit4_page2.json"),
    ("paracetamol", PAGE_SIZE, 0): (404, "labels_paracetamol_not_found.json"),
    ("ibuprofen", PAGE_SIZE, 0): (200, "labels_ibuprofen_selected.json"),
    ("acetaminophen", PAGE_SIZE, 0): (200, "labels_acetaminophen_selected.json"),
}


GLEEVEC = "211ef2da-2868-4a77-8055-1cb2cd78e24b"
# The canonical labels of the three searches and their effective times when the counts were
# recorded.
CANONICAL_TIMES = {
    "464e404a-1957-44a2-a53a-f2a9d3c15bde": "20260828",
    "3af22fc8-e4e0-4863-8696-6bc1257047cb": "20241113",
    "2144eff0-d7ab-486d-b116-a4ff3ae2afe2": "20260908",
    "ae1625f4-ef32-4d4f-bf54-c44085843e41": "20260820",
    GLEEVEC: "20260713",
}
RECORDED_COUNTS: dict[tuple[object, ...], tuple[int, str]] = {
    ("listed", frozenset(CANONICAL_TIMES)): (200, "count_listed.json"),
    ("listed", frozenset({GLEEVEC})): (200, "count_listed_gleevec.json"),
    ("newer than recorded", frozenset()): (404, "count_newer_none.json"),
    ("newer than recorded", frozenset({GLEEVEC})): (200, "count_newer_gleevec.json"),
}
NEWER_CLAUSE = re.compile(r'set_id:"([^"]+)" AND effective_time:\{(\d{8}) TO \*\]')


def describe_count(request: httpx2.Request) -> tuple[object, ...]:
    """What a count query asks: which labels are listed, or which have a newer version, keyed
    by the labels asked about with an older time than recorded."""
    params = request.url.params
    assert params["count"] == "set_id"
    search = params["search"]
    if clauses := NEWER_CLAUSE.findall(search):
        assert {set_id for set_id, _ in clauses} == set(CANONICAL_TIMES)
        older = {set_id for set_id, time in clauses if time < CANONICAL_TIMES[set_id]}
        return ("newer than recorded", frozenset(older))
    return ("listed", frozenset(re.findall(r'"([^"]+)"', search)))


def describe(request: httpx2.Request) -> tuple[str, int, int]:
    """The generic name, page size and offset a label search asks for."""
    params = request.url.params
    assert request.url.path == LABEL_PATH
    assert params["sort"] == "set_id:asc"
    name = params["search"].removeprefix('openfda.generic_name:"').removesuffix('"')
    return name, int(params["limit"]), int(params["skip"])


class Replay:
    """A MockTransport handler serving the recorded searches by `describe` key.

    `overrides` answer a key once (e.g. a 503 before the recorded response).
    """

    def __init__(
        self, overrides: dict[tuple[str, int, int], httpx2.Response] | None = None
    ) -> None:
        self._overrides = dict(overrides or {})
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if "count" in request.url.params:
            status, fixture = RECORDED_COUNTS[describe_count(request)]
            return httpx2.Response(status, content=(FIXTURES / fixture).read_bytes())
        key = describe(request)
        if key in self._overrides:
            return self._overrides.pop(key)
        status, fixture = RECORDED[key]
        return httpx2.Response(status, content=(FIXTURES / fixture).read_bytes())
