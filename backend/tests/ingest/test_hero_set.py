from pathlib import Path

import pytest
from pydantic import ValidationError

from molecula.config import REPO_ROOT
from molecula.ingest.hero_set import HeroSet, load_hero_set
from molecula.ingest.scope import load_scope

ENTRY = {
    "drug": "imatinib",
    "pdb": "2HYY",
    "ligand_code": "STI",
    "ligand_copy": "A/600",
    "chain": "A",
    "target": "ABL1 (BCR-ABL)",
    "organism": "Homo sapiens",
    "note": "human ABL1, 2.4 Å",
}


def hero_set(*complexes: dict[str, object]) -> HeroSet:
    return HeroSet.model_validate({"complexes": list(complexes)})


def test_loads_an_entry_with_defaults(tmp_path: Path) -> None:
    path = tmp_path / "hero_set.yaml"
    path.write_text(
        "complexes:\n"
        "  - drug: imatinib\n"
        "    pdb: 2HYY\n"
        '    ligand_code: "STI"\n'
        "    ligand_copy: A/600\n"
        "    chain: A\n"
        "    target: ABL1\n"
        "    organism: Homo sapiens\n"
        "    note: human ABL1\n",
        encoding="utf-8",
    )

    (entry,) = load_hero_set(path).complexes

    assert entry.pdb == "2HYY"
    assert entry.ligand_copy == "A/600"
    assert entry.showcase is False
    assert entry.caption is None


def test_two_complexes_for_one_drug_fail_case_insensitively() -> None:
    with pytest.raises(ValidationError, match="two complexes for"):
        hero_set(ENTRY, {**ENTRY, "drug": "Imatinib", "pdb": "1IEP"})


@pytest.mark.parametrize(
    "change",
    [
        {"pdb": "2hyy"},
        {"pdb": "HYY2"},
        {"ligand_code": "sti"},
        {"ligand_copy": "A"},
        {"ligand_copy": "A-600"},
        {"chain": ""},
        {"note": ""},
        {"resolution": 2.4},
    ],
)
def test_malformed_entries_fail(change: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        hero_set({**ENTRY, **change})


def test_a_copy_on_a_multi_letter_chain_and_negative_residue_loads() -> None:
    (entry,) = hero_set({**ENTRY, "ligand_copy": "S2/-5", "chain": "S7"}).complexes

    assert entry.ligand_copy == "S2/-5"


def test_the_repo_hero_set_is_valid_and_in_scope() -> None:
    complexes = {c.drug: c for c in load_hero_set(REPO_ROOT / "data" / "hero_set.yaml").complexes}
    scope = {drug.name for drug in load_scope(REPO_ROOT / "data" / "scope.yaml").drugs}

    assert set(complexes) - scope == set()
    assert complexes["imatinib"].organism == "Homo sapiens"
    assert any(c.showcase for c in complexes.values())


@pytest.mark.parametrize(
    ("drug", "active_form"),
    [("oseltamivir", "G39"), ("tamoxifen", "OHT"), ("aspirin", "SAL")],
)
def test_the_repo_hero_set_shows_prodrugs_in_their_active_form(drug: str, active_form: str) -> None:
    complexes = {c.drug: c for c in load_hero_set(REPO_ROOT / "data" / "hero_set.yaml").complexes}

    assert complexes[drug].ligand_code == active_form
    assert complexes[drug].caption
