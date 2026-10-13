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
