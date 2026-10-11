"""PubChem client tests on recorded responses (see `tests/pubchem_replay.py`)."""

import httpx2
import pytest

from molecula.sources.errors import SourceFormatError, SourceNotFound
from pubchem_replay import FIXTURES, PROPERTIES, Replay


def test_salt_brand_resolves_to_its_parent(pubchem) -> None:
    client = pubchem()

    [salt] = client.cids_for_name("Gleevec")

    assert salt == 123596
    assert client.parent_cids(salt) == [5291]


def test_brand_resolves_to_the_generic(pubchem) -> None:
    assert pubchem().cids_for_name("Tylenol") == [1983]


def test_properties_match_the_spike_report(pubchem) -> None:
    props = pubchem().properties(5291)

    assert props.cid == 5291
    assert (
        props.smiles == "CC1=C(C=C(C=C1)NC(=O)C2=CC=C(C=C2)CN3CCN(CC3)C)NC4=NC=CC(=N4)C5=CN=CC=C5"
    )
    assert props.inchikey == "KTUFNOKKBVMGRW-UHFFFAOYSA-N"
    assert props.formula == "C29H31N7O"
    assert props.molecular_weight == 493.6
    assert (props.xlogp, props.tpsa) == (3.5, 86.3)
    assert (props.hbd, props.hba, props.rotatable_bonds, props.heavy_atoms) == (2, 7, 7, 37)


def test_properties_accept_the_legacy_smiles_key(pubchem) -> None:
    legacy = (FIXTURES / "cid_5291_properties_handmade_isomeric_smiles.json").read_bytes()
    handler = Replay(
        {f"/compound/cid/5291/property/{PROPERTIES}/JSON": httpx2.Response(200, content=legacy)}
    )

    assert pubchem(handler).properties(5291).smiles.startswith("CC1=C(C=C(C=C1)NC(=O)")


def test_conformer_is_returned_as_sdf(pubchem) -> None:
    sdf = pubchem().conformer_sdf(5291)

    assert sdf is not None
    assert sdf.splitlines()[3].split()[:2] == ["68", "72"]
    assert sdf.rstrip().endswith("$$$$")


def test_protein_without_3d_returns_none(pubchem) -> None:
    client = pubchem()

    [insulin] = client.cids_for_name("insulin")

    assert client.conformer_sdf(insulin) is None


def test_synonyms_keep_pubchems_order(pubchem) -> None:
    synonyms = pubchem().synonyms(5291)

    assert synonyms[0] == "Imatinib"
    assert len(synonyms) == 166


def test_unknown_name_raises_source_not_found(pubchem) -> None:
    with pytest.raises(SourceNotFound):
        pubchem().cids_for_name("notadrugxyz")


def test_retries_a_503_then_succeeds(pubchem) -> None:
    handler = Replay({"/compound/name/Tylenol/cids/JSON": httpx2.Response(503)})

    assert pubchem(handler).cids_for_name("Tylenol") == [1983]
    assert len(handler.requests) == 2


def test_names_are_url_encoded(pubchem) -> None:
    handler = Replay({"/compound/name/insulin%20glargine%2Fx/cids/JSON": httpx2.Response(404)})

    with pytest.raises(SourceNotFound):
        pubchem(handler).cids_for_name("insulin glargine/x")

    assert handler.requests[0].url.raw_path.endswith(b"/insulin%20glargine%2Fx/cids/JSON")


def test_unexpected_shape_raises_source_format_error(pubchem) -> None:
    fault = httpx2.Response(200, json={"Fault": {"Code": "PUGREST.ServerBusy"}})
    handler = Replay({"/compound/name/Tylenol/cids/JSON": fault})

    with pytest.raises(SourceFormatError):
        pubchem(handler).cids_for_name("Tylenol")
