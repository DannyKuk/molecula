"""ChEMBL client tests on recorded responses (see `tests/chembl_replay.py`)."""

from collections.abc import Callable

import httpx2
import pytest

from chembl_replay import (
    BUPRENORPHINE,
    DOXYCYCLINE,
    IMATINIB,
    Replay,
    first_of_two_pages,
    mechanisms_of,
)
from molecula.sources.chembl import ChemblClient
from molecula.sources.errors import SourceFormatError
from molecula.sources.http import SourceClient
from molecula.store.http_cache import HttpCache


@pytest.fixture
def chembl(cache: HttpCache) -> Callable[..., ChemblClient]:
    """Makes a ChEMBL client that replays recorded responses through the store's HTTP cache."""

    def make(handler: Replay | None = None) -> ChemblClient:
        http = SourceClient(
            cache,
            offline=False,
            transport=httpx2.MockTransport(handler or Replay()),
            sleep=lambda _: None,
        )
        return ChemblClient(http)

    return make


def test_inchikey_finds_the_parent_molecule(chembl) -> None:
    [imatinib] = chembl().molecules_for_inchikey(IMATINIB)

    assert (imatinib.chembl_id, imatinib.pref_name) == ("CHEMBL941", "IMATINIB")
    assert imatinib.parent_chembl_id == "CHEMBL941"


def test_mechanisms_are_found_through_the_parent_id(chembl) -> None:
    mechanisms = chembl().mechanisms("CHEMBL941")

    assert {m.molecule_chembl_id for m in mechanisms} == {"CHEMBL1642"}
    assert [m.target_chembl_id for m in mechanisms] == [
        "CHEMBL1862",
        "CHEMBL1913",
        "CHEMBL1936",
        "CHEMBL2096618",
    ]
    assert mechanisms[0].mechanism_of_action == "Tyrosine-protein kinase ABL inhibitor"
    assert {m.action_type for m in mechanisms} == {"INHIBITOR"}


def test_single_protein_target_gives_accession_and_gene_symbol(chembl) -> None:
    target = chembl().target("CHEMBL1862")

    assert target.pref_name == "Tyrosine-protein kinase ABL1"
    assert (target.target_type, target.organism) == ("SINGLE PROTEIN", "Homo sapiens")
    [abl1] = target.components
    assert (abl1.accession, abl1.gene_symbol) == ("P00519", "ABL1")


def test_fusion_protein_returns_both_components(chembl) -> None:
    target = chembl().target("CHEMBL2096618")

    assert target.target_type == "CHIMERIC PROTEIN"
    assert [(c.accession, c.gene_symbol) for c in target.components] == [
        ("P00519", "ABL1"),
        ("P11274", "BCR"),
    ]


def test_protein_family_returns_every_member(chembl) -> None:
    target = chembl().target("CHEMBL2094253")

    assert (target.pref_name, target.target_type) == ("Cyclooxygenase", "PROTEIN FAMILY")
    assert {(c.accession, c.gene_symbol) for c in target.components} == {
        ("P35354", "PTGS2"),
        ("P23219", "PTGS1"),
    }


def test_drug_without_mechanism_returns_an_empty_list(chembl) -> None:
    assert chembl().mechanisms("CHEMBL1201396") == []


def test_stereo_mismatch_is_found_through_the_connectivity_block(chembl) -> None:
    client = chembl()

    assert client.molecules_for_inchikey(BUPRENORPHINE) == []
    molecules = client.molecules_for_connectivity(BUPRENORPHINE)
    assert len(molecules) == 5
    named = [m for m in molecules if m.pref_name]
    assert [(m.chembl_id, m.pref_name) for m in named] == [("CHEMBL511142", "BUPRENORPHINE")]


def test_molecule_without_hierarchy_is_its_own_parent(chembl) -> None:
    molecules = chembl().molecules_for_connectivity(BUPRENORPHINE)

    unprocessed = next(m for m in molecules if m.chembl_id == "CHEMBL1907075")
    assert unprocessed.hierarchy is None
    assert unprocessed.parent_chembl_id == "CHEMBL1907075"


def test_another_tautomer_matches_neither_key_but_the_name(chembl) -> None:
    client = chembl()

    assert client.molecules_for_inchikey(DOXYCYCLINE) == []
    assert client.molecules_for_connectivity(DOXYCYCLINE) == []
    [doxycycline] = client.molecules_named("doxycycline")
    assert (doxycycline.chembl_id, doxycycline.parent_chembl_id) == ("CHEMBL1200699", "CHEMBL1433")


def test_unknown_name_returns_an_empty_list(chembl) -> None:
    assert chembl().molecules_named("notadrugxyz") == []


def test_mechanisms_over_two_pages_come_back_complete(chembl) -> None:
    handler = Replay(first_of_two_pages())

    mechanisms = chembl(handler).mechanisms("CHEMBL20")

    assert len(mechanisms) == 8
    assert {m.target_chembl_id for m in mechanisms} == {
        "CHEMBL261",
        "CHEMBL205",
        "CHEMBL3242",
        "CHEMBL3729",
    }
    assert [r.url.params.get("offset") for r in handler.requests] == [None, "5"]


def test_unexpected_shape_raises_source_format_error(chembl) -> None:
    handler = Replay({mechanisms_of("CHEMBL941"): httpx2.Response(200, json={"error": "busy"})})

    with pytest.raises(SourceFormatError):
        chembl(handler).mechanisms("CHEMBL941")
