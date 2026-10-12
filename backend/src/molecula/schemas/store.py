from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class StoreManifest(BaseModel):
    """What a published store snapshot holds, written next to its archive by `ingest export`."""

    model_config = ConfigDict(frozen=True)

    schema_version: int
    built_at: datetime
    # The oldest label fetch: the label update (#25) asks openFDA for changes since then.
    last_run: datetime | None
    embedding_model: str
    row_counts: dict[str, int]
    archive: str
    archive_bytes: int
    sha256: Sha256
