"""RCSB client tests on recorded responses (see `tests/rcsb_replay.py`)."""

from collections.abc import Callable

import httpx2
import pytest

from molecula.sources.errors import SourceFormatError
from molecula.sources.http import SourceClient
from molecula.sources.rcsb import RcsbClient
from molecula.store.http_cache import HttpCache
from rcsb_replay import (
    IBUPROFEN_INCHIKEY,
    IBUPROFEN_SMILES,
    IMATINIB_INCHIKEY,
    INCHIKEY_SEARCH,
    STI_ENTRIES,
    STI_ENTRY_DETAILS,
    Replay,
)

ABL1_ENTRIES_WITH_STI = [
    "1IEP",
    "1OPJ",
    "2HYY",
    "3K5V",
    "3MS9",
    "3MSS",
    "3PYY",
    "6HD4",
    "6HD6",
    "6NPE",
    "6NPU",
    "6NPV",
    "7N9G",
]


@pytest.fixture
def rcsb(cache: HttpCache) -> Callable[..., RcsbClient]:
    """Makes an RCSB client that replays recorded responses through the store's HTTP cache."""

    def make(handler: Replay | None = None, *, offline: bool = False) -> RcsbClient:
        http = SourceClient(
            cache,
            offline=offline,
            transport=httpx2.MockTransport(handler or Replay()),
            sleep=lambda _: None,
        )
        return RcsbClient(http)

    return make


def chem_comp(inchikey: str | None) -> httpx2.Response:
    descriptor = {"InChIKey": inchikey} if inchikey else None
    return httpx2.Response(200, json={"rcsb_chem_comp_descriptor": descriptor})


def test_imatinib_maps_to_sti_only(rcsb) -> None:
    codes = rcsb().ligand_codes(IMATINIB_INCHIKEY)

    assert codes == ["STI"]
    assert "1N1" not in codes


def test_search_without_hits_returns_an_empty_list(rcsb) -> None:
    handler = Replay()

    assert rcsb(handler).ligand_codes(IBUPROFEN_INCHIKEY) == []
    assert handler.requests[0].url.host == "search.rcsb.org"


def test_empty_search_is_served_from_the_cache_offline(rcsb) -> None:
    rcsb().ligand_codes(IBUPROFEN_INCHIKEY)

    assert rcsb(offline=True).ligand_codes(IBUPROFEN_INCHIKEY) == []


def test_ibuprofen_falls_back_to_the_connectivity_block(rcsb) -> None:
    client = rcsb()

    assert client.ligand_codes(IBUPROFEN_INCHIKEY) == []
    assert client.ligand_codes_by_connectivity(IBUPROFEN_SMILES, IBUPROFEN_INCHIKEY) == [
        "IBP",
        "IZP",
    ]


def test_fallback_drops_codes_with_another_skeleton_or_no_inchikey(rcsb) -> None:
    handler = Replay(
        {
            "GET /rest/v1/core/chemcomp/IBP": chem_comp("XXXXXXXXXXXXXX-UHFFFAOYSA-N"),
            "GET /rest/v1/core/chemcomp/IZP": chem_comp(None),
        }
    )

    assert rcsb(handler).ligand_codes_by_connectivity(IBUPROFEN_SMILES, IBUPROFEN_INCHIKEY) == []


def test_ligand_inchikey_comes_from_the_chem_comp(rcsb) -> None:
    assert rcsb().ligand_inchikey("IBP") == "HEFNNWSXXWATRW-JTQLQIEISA-N"


def test_sti_with_abl1_finds_1iep_through_uniprot_gene_names(rcsb) -> None:
    # 1IEP has no depositor gene name, so a gene-name search on RCSB misses it.
    complexes = rcsb().complexes("STI", ["ABL1"])

    assert [c.pdb_id for c in complexes] == ABL1_ENTRIES_WITH_STI


def test_1iep_is_mouse_abl_at_2_1_angstrom(rcsb) -> None:
    [iep] = [c for c in rcsb().complexes("STI", ["ABL1"]) if c.pdb_id == "1IEP"]

    assert iep.resolution == 2.1
    assert (iep.organism, iep.taxonomy_id) == ("Mus musculus", 10090)
    assert iep.chains == ["A", "B"]
    assert iep.title == "CRYSTAL STRUCTURE OF THE C-ABL KINASE DOMAIN IN COMPLEX WITH STI-571."


def test_gene_names_match_case_insensitively(rcsb) -> None:
    complexes = rcsb().complexes("STI", ["abl1"])

    assert [c.pdb_id for c in complexes] == ABL1_ENTRIES_WITH_STI


def test_complexes_keep_only_entries_with_the_target_gene(rcsb) -> None:
    complexes = rcsb().complexes("STI", ["KIT"])

    assert [(c.pdb_id, c.organism) for c in complexes] == [
        ("1T46", "Homo sapiens"),
        ("8S16", "Homo sapiens"),
    ]


def test_complexes_take_one_search_and_one_graphql_request(rcsb) -> None:
    handler = Replay()

    rcsb(handler).complexes("STI", ["ABL1"])

    assert [r.url.host for r in handler.requests] == ["search.rcsb.org", "data.rcsb.org"]


def test_entries_cover_every_entry_with_the_ligand(rcsb) -> None:
    entries = rcsb().entries(STI_ENTRIES)

    assert sorted(e.pdb_id for e in entries) == STI_ENTRIES


def test_entity_genes_combine_depositor_and_uniprot_names(rcsb) -> None:
    [ppar] = [e for e in rcsb().entries(STI_ENTRIES) if e.pdb_id == "6KTN"]

    # The coactivator peptide (NCOA1) has no depositor gene name, only UniProt's.
    assert sorted(entity.genes for entity in ppar.entities) == [["NCOA1"], ["PPARG", "NR1C3"]]


def test_no_entries_make_no_request(rcsb) -> None:
    handler = Replay()

    assert rcsb(handler).entries([]) == []
    assert handler.requests == []


def test_retries_a_503_then_succeeds(rcsb) -> None:
    handler = Replay({INCHIKEY_SEARCH.format(IMATINIB_INCHIKEY): httpx2.Response(503)})

    assert rcsb(handler).ligand_codes(IMATINIB_INCHIKEY) == ["STI"]
    assert len(handler.requests) == 2


def test_graphql_errors_raise_source_format_error(rcsb) -> None:
    errors = httpx2.Response(200, json={"errors": [{"message": "Validation error"}]})
    handler = Replay({STI_ENTRY_DETAILS: errors})

    with pytest.raises(SourceFormatError):
        rcsb(handler).entries(STI_ENTRIES)


def test_graphql_errors_are_not_served_from_the_cache_on_the_next_call(rcsb) -> None:
    errors = httpx2.Response(200, json={"errors": [{"message": "Validation error"}]})
    handler = Replay({STI_ENTRY_DETAILS: errors})
    client = rcsb(handler)
    with pytest.raises(SourceFormatError):
        client.entries(STI_ENTRIES)

    entries = client.entries(STI_ENTRIES)

    assert sorted(e.pdb_id for e in entries) == STI_ENTRIES
    assert len(handler.requests) == 2


def test_graphql_entries_that_parse_are_served_from_the_cache(rcsb) -> None:
    rcsb().entries(STI_ENTRIES)
    handler = Replay()

    entries = rcsb(handler, offline=True).entries(STI_ENTRIES)

    assert sorted(e.pdb_id for e in entries) == STI_ENTRIES
    assert handler.requests == []
