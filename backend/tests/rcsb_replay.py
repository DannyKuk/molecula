"""RCSB responses recorded from the live API on 2026-10-11, served by what each request asks for.

Search and GraphQL requests are POSTs to one URL, so they are told apart by their JSON body:
`describe` turns a request into a short readable key. The ibuprofen InChIKey search answered
HTTP 204 with an empty body, so it has no fixture file.
"""

import json
from pathlib import Path

import httpx2

FIXTURES = Path(__file__).parent / "fixtures" / "rcsb"
IMATINIB_INCHIKEY = "KTUFNOKKBVMGRW-UHFFFAOYSA-N"
IBUPROFEN_INCHIKEY = "HEFNNWSXXWATRW-UHFFFAOYSA-N"
IBUPROFEN_SMILES = "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O"
STI_ENTRIES = sorted(
    hit["identifier"]
    for hit in json.loads((FIXTURES / "search_entries_STI.json").read_bytes())["result_set"]
)

INCHIKEY_SEARCH = (
    "search text_chem rcsb_chem_comp_descriptor.InChIKey exact_match {} -> mol_definition"
)
LIGAND_SEARCH = (
    "search text rcsb_nonpolymer_entity_container_identifiers.nonpolymer_comp_id exact_match {}"
    " -> entry"
)
RELAXED_STEREO_SEARCH = "search chemical SMILES graph-relaxed-stereo {} -> mol_definition"
STI_ENTRY_DETAILS = f"graphql entries {','.join(STI_ENTRIES)}"

RECORDED: dict[str, tuple[int, str | None]] = {
    INCHIKEY_SEARCH.format(IMATINIB_INCHIKEY): (200, "search_inchikey_imatinib.json"),
    INCHIKEY_SEARCH.format(IBUPROFEN_INCHIKEY): (204, None),
    RELAXED_STEREO_SEARCH.format(IBUPROFEN_SMILES): (
        200,
        "search_smiles_ibuprofen_relaxed_stereo.json",
    ),
    "GET /rest/v1/core/chemcomp/IBP": (200, "chemcomp_IBP.json"),
    "GET /rest/v1/core/chemcomp/IZP": (200, "chemcomp_IZP.json"),
    LIGAND_SEARCH.format("STI"): (200, "search_entries_STI.json"),
    STI_ENTRY_DETAILS: (200, "graphql_entries_STI.json"),
}


def describe(request: httpx2.Request) -> str:
    """A readable key for a request: the search's terminal query, the GraphQL IDs, or the path."""
    if request.method == "GET":
        return f"GET {request.url.path}"
    body = json.loads(request.content)
    if request.url.path == "/graphql":
        return f"graphql entries {','.join(body['variables']['ids'])}"
    assert body["request_options"] == {"return_all_hits": True}
    query, params = body["query"], body["query"]["parameters"]
    if query["service"] == "chemical":
        terms = [params["descriptor_type"], params["match_type"], params["value"]]
    else:
        terms = [params["attribute"], params["operator"], params["value"]]
    return f"search {query['service']} {' '.join(terms)} -> {body['return_type']}"


class Replay:
    """A MockTransport handler serving the recorded responses by `describe` key.

    `overrides` answer a key once (e.g. a 503 before the recorded response).
    """

    def __init__(self, overrides: dict[str, httpx2.Response] | None = None) -> None:
        self._overrides = dict(overrides or {})
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        key = describe(request)
        if key in self._overrides:
            return self._overrides.pop(key)
        status, fixture = RECORDED[key]
        return httpx2.Response(
            status, content=(FIXTURES / fixture).read_bytes() if fixture else b""
        )
