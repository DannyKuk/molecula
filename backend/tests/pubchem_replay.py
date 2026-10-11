"""PubChem responses recorded from the live API on 2026-10-11, served by request path.

`cid_5291_properties_handmade_isomeric_smiles.json` is the recorded imatinib response with the
`SMILES` key renamed to its old name; PubChem no longer returns `IsomericSMILES`.
"""

from pathlib import Path

import httpx2

FIXTURES = Path(__file__).parent / "fixtures" / "pubchem"
PUG_PATH = "/rest/pug"
PROPERTIES = (
    "SMILES,InChIKey,MolecularFormula,MolecularWeight,XLogP,TPSA,"
    "HBondDonorCount,HBondAcceptorCount,RotatableBondCount,HeavyAtomCount"
)


def compound(cid: int, *, has_3d: bool = True) -> dict[str, tuple[int, str]]:
    """The recorded parent, properties, conformer and synonyms responses for a compound."""
    return {
        f"/compound/cid/{cid}/cids/JSON?cids_type=parent": (200, f"cid_{cid}_parent.json"),
        f"/compound/cid/{cid}/property/{PROPERTIES}/JSON": (200, f"cid_{cid}_properties.json"),
        f"/compound/cid/{cid}/SDF?record_type=3d": (200 if has_3d else 404, f"cid_{cid}_3d.sdf"),
        f"/compound/cid/{cid}/synonyms/JSON": (200, f"cid_{cid}_synonyms.json"),
    }


RECORDED = {
    "/compound/name/Gleevec/cids/JSON": (200, "name_gleevec_cids.json"),
    "/compound/name/Tylenol/cids/JSON": (200, "name_tylenol_cids.json"),
    "/compound/name/insulin/cids/JSON": (200, "name_insulin_cids.json"),
    "/compound/name/notadrugxyz/cids/JSON": (404, "name_unknown_cids.json"),
    "/compound/name/imatinib/cids/JSON": (200, "name_imatinib_cids.json"),
    "/compound/name/caffeine/cids/JSON": (200, "name_caffeine_cids.json"),
    "/compound/name/ibuprofen/cids/JSON": (200, "name_ibuprofen_cids.json"),
    "/compound/name/ritonavir/cids/JSON": (200, "name_ritonavir_cids.json"),
    "/compound/name/semaglutide/cids/JSON": (200, "name_semaglutide_cids.json"),
    "/compound/cid/123596/cids/JSON?cids_type=parent": (200, "cid_123596_parent.json"),
    "/compound/cid/70678557/SDF?record_type=3d": (404, "cid_70678557_3d.sdf"),
    **compound(5291),
    **compound(2519),
    **compound(3672),
    **compound(392622, has_3d=False),
    **compound(56843331, has_3d=False),
}


class Replay:
    """A MockTransport handler serving the recorded responses by path and query.

    `overrides` answer a path once (e.g. a 503 before the recorded response).
    """

    def __init__(self, overrides: dict[str, httpx2.Response] | None = None) -> None:
        self._overrides = dict(overrides or {})
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        key = request.url.raw_path.decode().removeprefix(PUG_PATH)
        if key in self._overrides:
            return self._overrides.pop(key)
        status, fixture = RECORDED[key]
        return httpx2.Response(status, content=(FIXTURES / fixture).read_bytes())
