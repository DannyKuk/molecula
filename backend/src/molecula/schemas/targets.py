from pydantic import BaseModel, ConfigDict


class Target(BaseModel):
    """A target the drug acts on and ChEMBL's mechanism for it."""

    model_config = ConfigDict(frozen=True)

    target_chembl_id: str
    name: str
    target_type: str
    organism: str | None
    mechanism: str
    action_type: str | None
    accessions: list[str]
    gene_symbols: list[str]
    source: str
    source_url: str


class DrugTargets(BaseModel):
    """The targets of a supported drug. An empty list means ChEMBL lists no mechanism for it."""

    model_config = ConfigDict(frozen=True)

    cid: int
    targets: list[Target]
