"""ChEMBL responses recorded from the live API on 2026-10-11, served by request path.

The InChIKeys are PubChem's, as the compounds ingest stores them:
- imatinib `KTUFNOKKBVMGRW-UHFFFAOYSA-N` matches ChEMBL exactly.
- buprenorphine `RMRJXGBAOAMLHD-IHFGGWKQSA-N` has stereo ChEMBL doesn't record, so only the
  connectivity block matches (five molecules, BUPRENORPHINE among them).
- doxycycline `SGKRLCUYIXIAHR-AKNGSSGZSA-N` matches neither way: ChEMBL draws a different
  tautomer, so even the connectivity block differs.

Fluticasone (CHEMBL1201396) has no mechanism of its own; ChEMBL lists them on its esters.

No mechanism list in scope is longer than ChEMBL's default page of 20, so the paging test serves
acetazolamide's mechanisms recorded with `limit=5` (`mechanism_CHEMBL20_limit5_page*.json`) in
place of the default page. Both files are unedited; the second one is served at the `next` path
the first one names.
"""

from pathlib import Path

import httpx2

FIXTURES = Path(__file__).parent / "fixtures" / "chembl"
API_PATH = "/chembl/api/data"
ONLY = "only=molecule_chembl_id%2Cpref_name%2Cmolecule_hierarchy"
IMATINIB = "KTUFNOKKBVMGRW-UHFFFAOYSA-N"
BUPRENORPHINE = "RMRJXGBAOAMLHD-IHFGGWKQSA-N"
DOXYCYCLINE = "SGKRLCUYIXIAHR-AKNGSSGZSA-N"


def by_inchikey(inchikey: str) -> str:
    return f"/molecule.json?molecule_structures__standard_inchi_key={inchikey}&{ONLY}"


def by_connectivity(inchikey: str) -> str:
    block = inchikey[:14]
    return f"/molecule.json?molecule_structures__standard_inchi_key__startswith={block}&{ONLY}"


def mechanisms_of(parent: str) -> str:
    return f"/mechanism.json?parent_molecule_chembl_id={parent}"


RECORDED = {
    by_inchikey(IMATINIB): (200, "molecule_inchikey_imatinib.json"),
    by_inchikey(BUPRENORPHINE): (200, "molecule_inchikey_buprenorphine.json"),
    by_connectivity(BUPRENORPHINE): (200, "molecule_connectivity_buprenorphine.json"),
    by_inchikey(DOXYCYCLINE): (200, "molecule_inchikey_doxycycline.json"),
    by_connectivity(DOXYCYCLINE): (200, "molecule_connectivity_doxycycline.json"),
    mechanisms_of("CHEMBL941"): (200, "mechanism_CHEMBL941.json"),
    mechanisms_of("CHEMBL1201396"): (200, "mechanism_CHEMBL1201396.json"),
    "/mechanism.json?limit=5&offset=5&parent_molecule_chembl_id=CHEMBL20": (
        200,
        "mechanism_CHEMBL20_limit5_page2.json",
    ),
    "/target/CHEMBL1862.json": (200, "target_CHEMBL1862.json"),
    "/target/CHEMBL2096618.json": (200, "target_CHEMBL2096618.json"),
    "/target/CHEMBL2094253.json": (200, "target_CHEMBL2094253.json"),
}


def first_of_two_pages() -> dict[str, httpx2.Response]:
    """Acetazolamide's first `limit=5` page, served for the client's default mechanism request."""
    page = (FIXTURES / "mechanism_CHEMBL20_limit5_page1.json").read_bytes()
    return {mechanisms_of("CHEMBL20"): httpx2.Response(200, content=page)}


class Replay:
    """A MockTransport handler serving the recorded responses by path and query.

    `overrides` answer a path once (e.g. a 503 before the recorded response).
    """

    def __init__(self, overrides: dict[str, httpx2.Response] | None = None) -> None:
        self._overrides = dict(overrides or {})
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        key = request.url.raw_path.decode().removeprefix(API_PATH)
        if key in self._overrides:
            return self._overrides.pop(key)
        status, fixture = RECORDED[key]
        return httpx2.Response(status, content=(FIXTURES / fixture).read_bytes())
