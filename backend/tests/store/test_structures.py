from pathlib import Path

from molecula.store.structures import ConformerFiles

SDF = "2519\n  RDKit          3D\n\n  0  0  0  0  0  0  0  0  0  0999 V2000\nM  END\n$$$$\n"


def test_writes_and_reads_a_conformer_byte_for_byte(tmp_path: Path) -> None:
    files = ConformerFiles(tmp_path / "structures")

    files.write(2519, SDF)

    assert files.read(2519) == SDF
    assert b"\r\n" not in files.path(2519).read_bytes()


def test_missing_conformer_reads_as_none(tmp_path: Path) -> None:
    assert ConformerFiles(tmp_path).read(1) is None


def test_same_content_leaves_the_file_untouched(tmp_path: Path) -> None:
    files = ConformerFiles(tmp_path)
    files.write(2519, SDF)
    modified = files.path(2519).stat().st_mtime_ns

    files.write(2519, SDF)

    assert files.path(2519).stat().st_mtime_ns == modified


def test_remove_deletes_the_file_and_tolerates_a_missing_one(tmp_path: Path) -> None:
    files = ConformerFiles(tmp_path)
    files.write(2519, SDF)

    files.remove(2519)
    files.remove(2519)

    assert files.read(2519) is None
