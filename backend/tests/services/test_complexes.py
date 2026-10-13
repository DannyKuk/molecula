from pathlib import Path

import pytest

from molecula.services.complexes import ComplexService
from molecula.store.structures import ComplexFiles
from store_records import IMATINIB_COMPLEX


@pytest.fixture
def files(tmp_path: Path) -> ComplexFiles:
    return ComplexFiles(tmp_path / "complexes")


def test_returns_the_stored_complex(files: ComplexFiles) -> None:
    files.write(5291, IMATINIB_COMPLEX.model_dump_json())

    assert ComplexService(files).get_complex(5291) == IMATINIB_COMPLEX


def test_drug_without_a_stored_complex_has_none(files: ComplexFiles) -> None:
    files.write(5291, IMATINIB_COMPLEX.model_dump_json())

    assert ComplexService(files).get_complex(3672) is None


def test_store_without_complexes_has_none(files: ComplexFiles) -> None:
    assert ComplexService(files).get_complex(5291) is None
    assert not files.directory.exists()


def test_a_file_stored_without_the_rcsb_link_gets_it(files: ComplexFiles) -> None:
    stored = IMATINIB_COMPLEX.model_dump_json(exclude={"source_url"})
    files.write(5291, stored)

    found = ComplexService(files).get_complex(5291)

    assert "source_url" not in stored
    assert found is not None
    assert found.model_dump()["source_url"] == "https://www.rcsb.org/structure/2HYY"
