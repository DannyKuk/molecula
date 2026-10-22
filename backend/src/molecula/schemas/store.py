from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class StoreManifest(BaseModel):
    """What a published store snapshot holds, written next to its archive by `ingest export`."""

    model_config = ConfigDict(frozen=True)

    schema_version: int
    built_at: datetime
    # Since when the labels are known to be current: the start of the last label update that
    # checked every drug, else the oldest label fetch.
    last_run: datetime | None
    embedding_model: str
    row_counts: dict[str, int]
    archive: str
    archive_bytes: int
    sha256: Sha256
