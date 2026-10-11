"""openFDA label searches recorded from the live API on 2026-10-11 without an API key.

The fixtures are hand-trimmed: every section string is cut to its first 40 characters (an Rx
label is 40-170k characters) and the JSON is re-indented. Everything else, including the
`openfda` block and `meta`, is as recorded.

- imatinib: 22 labels, all single-ingredient imatinib mesylate.
- "hydrocodone apap": 6 combination labels whose generic name is written HYDROCODONE/APAP or
  HYDROCODONE APAP, each with two substance names. Recorded once with the client's default page
  size and once with `limit=4`, which takes two pages (`*_limit4_page1.json`, `*_page2.json`).
- paracetamol: openFDA has US labels only, so it answers 404 with `NOT_FOUND`.
"""

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
}


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
        key = describe(request)
        if key in self._overrides:
            return self._overrides.pop(key)
        status, fixture = RECORDED[key]
        return httpx2.Response(status, content=(FIXTURES / fixture).read_bytes())
