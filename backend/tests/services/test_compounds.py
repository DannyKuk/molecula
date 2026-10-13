import ast
import inspect
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from molecula.schemas.compounds import (
    ConformerSource,
    DrugMention,
    Match,
    Suggestion,
    SupportedDrug,
)
from molecula.services import compounds
from molecula.services.compounds import CompoundService, name_candidates
from molecula.store.compounds import CompoundRecord, CompoundStore, Synonym
from molecula.store.structures import ConformerFiles

FETCHED_AT = datetime(2026, 10, 11, tzinfo=UTC)
SDF = "5291\n  stored conformer\n$$$$\n"
SUGGESTION_CUTOFF = 0.8
# Copied from the built store (2026-10-12). Citalopram, hydroxyzine and hydralazine aren't in it.
SCOPE = [
    (3672, "ibuprofen", ["Advil", "Motrin", "Nurofen", "Ibuflam"]),
    (1983, "acetaminophen", ["paracetamol", "Tylenol", "Panadol", "ben-u-ron"]),
    (5291, "imatinib", ["Gleevec", "Glivec"]),
    (2678, "cetirizine", ["Zyrtec"]),
    (33613, "amoxicillin", ["Amoxil"]),
    (2244, "aspirin", ["acetylsalicylic acid", "ASA", "ASS"]),
    (4091, "metformin", ["Glucophage"]),
    (60823, "atorvastatin", ["Lipitor", "Sortis"]),
    (2662, "celecoxib", ["Celebrex"]),
    (27447, "cephalexin", ["cefalexin", "Keflex"]),
    (146570, "escitalopram", ["Lexapro", "Cipralex"]),
    (3652, "hydroxychloroquine", ["Plaquenil"]),
    (5754, "hydrocortisone", []),
    (5819, "levothyroxine", ["Levothyroxin", "Synthroid", "Euthyrox", "L-thyroxine"]),
    (4594, "omeprazole", ["Omeprazol", "Prilosec"]),
    (9568614, "esomeprazole", ["Nexium"]),
    (4679, "pantoprazole", ["Pantoprazol", "Protonix", "Pantozol"]),
    (3883, "lansoprazole", ["Prevacid"]),
]


def record(cid: int, name: str, conformer_source: ConformerSource | None = "pubchem"):
    return CompoundRecord(
        cid=cid,
        name=name,
        inchikey=f"INCHIKEY-{cid}",
        smiles="C",
        formula="C",
        mw=100.0,
        xlogp=1.0,
        tpsa=10.0,
        hbd=1,
        hba=1,
        rotb=0,
        heavy_atoms=10,
        conformer_source=conformer_source,
        source="pubchem",
    )


@pytest.fixture
def store(conn: sqlite3.Connection) -> CompoundStore:
    store = CompoundStore(conn)
    store.save(
        record(5291, "imatinib"),
        [Synonym("imatinib", "name"), Synonym("Gleevec", "alias"), Synonym("Glamox", "pubchem")],
        FETCHED_AT,
    )
    store.save(
        record(3672, "ibuprofen"),
        [Synonym("ibuprofen", "name"), Synonym("Ibuflam", "alias"), Synonym("Advil", "alias")],
        FETCHED_AT,
    )
    store.save(record(4091, "metformin"), [Synonym("metformin", "name")], FETCHED_AT)
    store.save(record(60823, "atorvastatin"), [Synonym("atorvastatin", "name")], FETCHED_AT)
    store.save(
        record(56843331, "semaglutide", conformer_source=None),
        [Synonym("semaglutide", "name")],
        FETCHED_AT,
    )
    return store


@pytest.fixture
def conformers(tmp_path: Path) -> ConformerFiles:
    files = ConformerFiles(tmp_path / "structures" / "compounds")
    files.write(5291, SDF)
    return files


@pytest.fixture
def service(store: CompoundStore, conformers: ConformerFiles) -> CompoundService:
    return CompoundService(store, conformers, suggestion_cutoff=SUGGESTION_CUTOFF)


@pytest.fixture
def scope_store(conn: sqlite3.Connection) -> CompoundStore:
    """The built store's scope names and aliases of the drugs near the misspellings tested here."""
    store = CompoundStore(conn)
    for cid, name, aliases in SCOPE:
        store.save(
            record(cid, name),
            [Synonym(name, "name"), *(Synonym(alias, "alias") for alias in aliases)],
            FETCHED_AT,
        )
    return store


@pytest.fixture
def scope_service(scope_store: CompoundStore, conformers: ConformerFiles) -> CompoundService:
    return CompoundService(scope_store, conformers, suggestion_cutoff=SUGGESTION_CUTOFF)


@pytest.mark.parametrize("name", ["Ibuflam", "ibuflam", "IBUFLAM", "  Ibuflam "])
def test_alias_resolves_in_any_case(service: CompoundService, name: str) -> None:
    resolution = service.resolve(name)

    assert resolution.status == "found"
    assert resolution.compound is not None
    assert resolution.compound.name == "ibuprofen"
    assert (resolution.matched_alias, resolution.match_kind) == ("Ibuflam", "alias")
    assert resolution.match == Match(compound=resolution.compound, alias="Ibuflam", kind="alias")
    assert resolution.query == name.strip()
    assert resolution.suggestions == []


def test_pubchem_synonym_resolves(service: CompoundService) -> None:
    resolution = service.resolve("glamox")

    assert resolution.compound is not None
    assert resolution.compound.cid == 5291
    assert resolution.match_kind == "pubchem"


@pytest.mark.parametrize(
    ("name", "cid"),
    [
        ("imatinib mesylate", 5291),
        ("Metformin HCl", 4091),
        ("metformin  hydrochloride", 4091),
        ("atorvastatin calcium trihydrate", 60823),
    ],
)
def test_salt_name_resolves_to_the_stored_parent(
    service: CompoundService, name: str, cid: int
) -> None:
    resolution = service.resolve(name)

    assert resolution.status == "found"
    assert resolution.compound is not None
    assert resolution.compound.cid == cid
    assert resolution.match_kind == "name"


@pytest.mark.parametrize("name", ["Vicodin", "notadrugxyz", "sodium chloride", "", "   "])
def test_name_outside_the_store_is_not_supported(service: CompoundService, name: str) -> None:
    resolution = service.resolve(name)

    assert resolution.status == "not_supported"
    assert resolution.compound is None
    assert resolution.matched_alias is None
    assert resolution.match is None
    assert resolution.suggestions == []


@pytest.mark.parametrize(
    ("name", "suggestion"),
    [
        ("ibuprofin", Suggestion(alias="ibuprofen", cid=3672, name="ibuprofen")),
        ("paracetamoll", Suggestion(alias="paracetamol", cid=1983, name="acetaminophen")),
        ("Gleevek", Suggestion(alias="Gleevec", cid=5291, name="imatinib")),
        ("ZYRTEK", Suggestion(alias="Zyrtec", cid=2678, name="cetirizine")),
        ("amoxicilin", Suggestion(alias="amoxicillin", cid=33613, name="amoxicillin")),
        ("asprin", Suggestion(alias="aspirin", cid=2244, name="aspirin")),
        ("metformine", Suggestion(alias="metformin", cid=4091, name="metformin")),
        ("atorvastatine", Suggestion(alias="atorvastatin", cid=60823, name="atorvastatin")),
        ("metformine hydrochloride", Suggestion(alias="metformin", cid=4091, name="metformin")),
    ],
)
def test_misspelled_name_or_brand_suggests_the_supported_spelling(
    scope_service: CompoundService, name: str, suggestion: Suggestion
) -> None:
    resolution = scope_service.resolve(name)

    assert resolution.suggestions == [suggestion]


def test_suggestion_never_changes_the_status(scope_service: CompoundService) -> None:
    resolution = scope_service.resolve("ibuprofin")

    assert resolution.status == "not_supported"
    assert (resolution.compound, resolution.matched_alias, resolution.match_kind) == (
        None,
        None,
        None,
    )
    assert [suggestion.name for suggestion in resolution.suggestions] == ["ibuprofen"]


@pytest.mark.parametrize("name", ["Celexa", "hydroxizine", "xyz"])
def test_look_alike_or_unrelated_name_gets_no_suggestion(
    scope_service: CompoundService, name: str
) -> None:
    resolution = scope_service.resolve(name)

    assert resolution.status == "not_supported"
    assert resolution.suggestions == []


def test_at_most_three_suggestions_best_first(
    scope_store: CompoundStore, conformers: ConformerFiles
) -> None:
    # At 0.6 pantoprazole and lansoprazole are close enough too, but rank below these three.
    service = CompoundService(scope_store, conformers, suggestion_cutoff=0.6)

    resolution = service.resolve("omeprazoe")

    assert [suggestion.alias for suggestion in resolution.suggestions] == [
        "omeprazole",
        "Omeprazol",
        "esomeprazole",
    ]


def test_cutoff_setting_decides_how_close_a_suggestion_must_be(
    scope_store: CompoundStore, conformers: ConformerFiles
) -> None:
    strict = CompoundService(scope_store, conformers, suggestion_cutoff=0.9)

    assert strict.resolve("Gleevek").suggestions == []


def test_pubchem_synonyms_are_never_suggested(service: CompoundService) -> None:
    # "Glamox" is imatinib's PubChem synonym in the store fixture, close to "Glamix".
    assert service.resolve("Glamix").suggestions == []


def test_scope_name_wins_over_a_pubchem_synonym_of_another_compound(
    store: CompoundStore, service: CompoundService
) -> None:
    # Saved first, so the shared alias's oldest row belongs to the wrong compound.
    store.save(
        record(2519, "caffeine"),
        [Synonym("caffeine", "name"), Synonym("theophylline", "pubchem")],
        FETCHED_AT,
    )
    store.save(record(2153, "theophylline"), [Synonym("theophylline", "name")], FETCHED_AT)

    resolution = service.resolve("Theophylline")

    assert resolution.compound is not None
    assert resolution.compound.cid == 2153
    assert resolution.match_kind == "name"


def test_service_has_no_source_client() -> None:
    imports = {
        node.module
        for node in ast.walk(ast.parse(inspect.getsource(compounds)))
        if isinstance(node, ast.ImportFrom) and node.module
    }

    assert not any(module.startswith("molecula.sources") for module in imports)


def test_get_compound_carries_the_pubchem_source(service: CompoundService) -> None:
    compound = service.get_compound(5291)

    assert compound is not None
    assert compound.name == "imatinib"
    assert compound.source == "pubchem"
    assert compound.source_url == "https://pubchem.ncbi.nlm.nih.gov/compound/5291"


def test_get_compound_of_an_unknown_cid_is_none(service: CompoundService) -> None:
    assert service.get_compound(1) is None


def test_get_structure_returns_the_stored_conformer(service: CompoundService) -> None:
    structure = service.get_structure(5291)

    assert structure is not None
    assert (structure.sdf, structure.conformer_source) == (SDF, "pubchem")


@pytest.mark.parametrize(
    "cid",
    [
        56843331,  # semaglutide: a peptide without 3D
        3672,  # ibuprofen: stored with 3D, but its file is missing
        1,  # not stored
    ],
)
def test_get_structure_without_a_conformer_is_none(service: CompoundService, cid: int) -> None:
    assert service.get_structure(cid) is None


def test_list_drugs_has_the_scope_aliases_and_no_pubchem_synonyms(
    service: CompoundService,
) -> None:
    drugs = {drug.name: drug for drug in service.list_drugs()}

    assert list(drugs) == ["atorvastatin", "ibuprofen", "imatinib", "metformin", "semaglutide"]
    assert drugs["imatinib"] == SupportedDrug(
        cid=5291, name="imatinib", aliases=["Gleevec"], has_3d=True
    )
    assert drugs["ibuprofen"].aliases == ["Ibuflam", "Advil"]
    assert drugs["metformin"].aliases == []
    assert drugs["semaglutide"].has_3d is False


@pytest.mark.parametrize(
    ("query", "candidates"),
    [
        ("imatinib", ["imatinib"]),
        ("imatinib mesylate", ["imatinib mesylate", "imatinib"]),
        ("ESCITALOPRAM OXALATE", ["ESCITALOPRAM OXALATE", "ESCITALOPRAM"]),
        ("Doxycycline Hyclate", ["Doxycycline Hyclate", "Doxycycline"]),
        ("sodium chloride", ["sodium chloride"]),
        ("medroxyprogesterone acetate", ["medroxyprogesterone acetate"]),
        ("", []),
    ],
)
def test_name_candidates(query: str, candidates: list[str]) -> None:
    assert name_candidates(query) == candidates


def mentioned(service: CompoundService, text: str) -> list[tuple[str, str]]:
    return [(mention.text, mention.name) for mention in service.find_mentions(text)]


def test_find_mentions_finds_brands_and_names_in_a_sentence(
    scope_service: CompoundService,
) -> None:
    mentions = scope_service.find_mentions("Can I take Tylenol with advil?")

    assert mentions == [
        DrugMention(text="Tylenol", start=11, end=18, cid=1983, name="acetaminophen"),
        DrugMention(text="advil", start=24, end=29, cid=3672, name="ibuprofen"),
    ]


def test_find_mentions_reads_german_questions(scope_service: CompoundService) -> None:
    assert mentioned(scope_service, "Darf ich Ibuflam und Paracetamol zusammen nehmen?") == [
        ("Ibuflam", "ibuprofen"),
        ("Paracetamol", "acetaminophen"),
    ]


@pytest.mark.parametrize(
    ("text", "mentions"),
    [
        ("Is acetylsalicylic acid an NSAID?", [("acetylsalicylic acid", "aspirin")]),
        ("How does esomeprazole differ?", [("esomeprazole", "esomeprazole")]),
        ("Is ben-u-ron safe for kids?", [("ben-u-ron", "acetaminophen")]),
        ("When do I take L-thyroxine?", [("L-thyroxine", "levothyroxine")]),
        ("Gleevecs and imatinibs", []),
    ],
)
def test_find_mentions_matches_whole_names_only_longest_first(
    scope_service: CompoundService, text: str, mentions: list[tuple[str, str]]
) -> None:
    assert mentioned(scope_service, text) == mentions


@pytest.mark.parametrize(
    ("text", "mentions"),
    [
        ("Hilft ASS gegen Kopfschmerzen?", [("ASS", "aspirin")]),
        ("Is ASA the same drug?", [("ASA", "aspirin")]),
        ("This pain is a pain in the ass", []),
        ("Is asa safe?", []),
    ],
)
def test_find_mentions_matches_abbreviations_only_in_capitals(
    scope_service: CompoundService, text: str, mentions: list[tuple[str, str]]
) -> None:
    assert mentioned(scope_service, text) == mentions


def test_find_mentions_keeps_every_mention_and_skips_pubchem_synonyms(
    service: CompoundService,
) -> None:
    assert mentioned(service, "Gleevec or imatinib, not Glamox") == [
        ("Gleevec", "imatinib"),
        ("imatinib", "imatinib"),
    ]


def test_find_mentions_in_text_without_a_drug_is_empty(scope_service: CompoundService) -> None:
    assert scope_service.find_mentions("What helps against a headache?") == []
