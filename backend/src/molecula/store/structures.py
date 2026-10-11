from collections.abc import Collection
from pathlib import Path


class ConformerFiles:
    """3D conformers as SDF files, one per CID, next to the SQLite store."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    @property
    def directory(self) -> Path:
        return self._directory

    def path(self, cid: int) -> Path:
        return self._directory / f"{cid}.sdf"

    def read(self, cid: int) -> str | None:
        path = self.path(cid)
        return path.read_text(encoding="utf-8", newline="") if path.exists() else None

    def write(self, cid: int, sdf: str) -> None:
        """Write the conformer, leaving the file untouched when its content is the same."""
        if self.read(cid) == sdf:
            return
        self._directory.mkdir(parents=True, exist_ok=True)
        self.path(cid).write_text(sdf, encoding="utf-8", newline="")

    def remove(self, cid: int) -> None:
        self.path(cid).unlink(missing_ok=True)

    def prune(self, keep: Collection[int]) -> list[int]:
        """Delete every conformer whose CID isn't in `keep` and return the deleted CIDs in order."""
        stored = (int(path.stem) for path in self._directory.glob("*.sdf") if path.stem.isdigit())
        removed = sorted(cid for cid in stored if cid not in keep)
        for cid in removed:
            self.remove(cid)
        return removed
