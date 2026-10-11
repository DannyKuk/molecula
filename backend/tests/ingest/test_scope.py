from pathlib import Path

import pytest
from pydantic import ValidationError

from molecula.config import REPO_ROOT
from molecula.ingest.scope import Scope, load_scope

HERO_CANDIDATES = {
    "imatinib", "dasatinib", "caffeine", "atorvastatin", "ibuprofen", "celecoxib",
    "diclofenac", "naproxen", "methotrexate", "donepezil", "gefitinib", "erlotinib",
    "sitagliptin", "lisinopril", "acetazolamide", "oseltamivir", "zanamivir", "ritonavir",
    "warfarin", "tamoxifen", "sildenafil", "raltegravir",
}  # fmt: skip
MOLECULE_ONLY = {"acetaminophen", "metformin", "cetirizine", "omeprazole"}


def scope(*drugs: dict[str, object]) -> Scope:
    return Scope.model_validate({"drugs": list(drugs)})


def test_loads_names_aliases_and_flags(tmp_path: Path) -> None:
    path = tmp_path / "scope.yaml"
    path.write_text(
        "drugs:\n"
        "  - name: acetaminophen\n"
        "    aliases: [paracetamol, Tylenol]\n"
        "  - name: imatinib\n"
        "    hero: true\n"
        "    note: checked\n",
        encoding="utf-8",
    )

    loaded = load_scope(path)

    first, second = loaded.drugs
    assert first.name == "acetaminophen"
    assert first.aliases == ["paracetamol", "Tylenol"]
    assert first.hero is False
    assert second.hero is True
    assert second.note == "checked"


def test_duplicate_names_fail_case_insensitively() -> None:
    with pytest.raises(ValidationError, match="duplicate drug name"):
        scope({"name": "ibuprofen"}, {"name": "Ibuprofen"})


def test_alias_pointing_to_two_drugs_fails_case_insensitively() -> None:
    with pytest.raises(ValidationError, match="points to both"):
        scope(
            {"name": "acetaminophen", "aliases": ["Panadol"]},
            {"name": "ibuprofen", "aliases": ["panadol"]},
        )


def test_alias_that_is_another_drugs_name_fails() -> None:
    with pytest.raises(ValidationError, match="points to both"):
        scope({"name": "acetaminophen"}, {"name": "ibuprofen", "aliases": ["Acetaminophen"]})


def test_repeating_a_drugs_own_name_as_alias_is_allowed() -> None:
    assert scope({"name": "aspirin", "aliases": ["Aspirin"]}).drugs[0].aliases == ["Aspirin"]


@pytest.mark.parametrize("entry", [{"name": ""}, {"name": "x", "brand": "y"}, {"aliases": ["y"]}])
def test_malformed_entries_fail(entry: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        scope(entry)


def test_the_repo_scope_file_is_valid_and_complete() -> None:
    drugs = load_scope(REPO_ROOT / "data" / "scope.yaml").drugs
    names = {drug.name for drug in drugs}

    assert 100 <= len(drugs) <= 150
    assert HERO_CANDIDATES - {drug.name for drug in drugs if drug.hero} == set()
    assert MOLECULE_ONLY - names == set()
