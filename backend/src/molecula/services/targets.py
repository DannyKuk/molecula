from molecula.schemas.compounds import Compound
from molecula.schemas.targets import DrugTargets, Target
from molecula.store.compounds import CompoundStore
from molecula.store.targets import TargetRecord, TargetStore

CHEMBL_TARGET_URL = "https://www.ebi.ac.uk/chembl/explore/target/{target_chembl_id}"
# The targets ingest step writes every target row from ChEMBL.
TARGET_SOURCE = "chembl"


class TargetService:
    """The targets a supported drug acts on, from the local store."""

    def __init__(self, targets: TargetStore, compounds: CompoundStore) -> None:
        self._targets = targets
        self._compounds = compounds

    def get_targets(self, cid: int) -> DrugTargets | None:
        """The drug's targets, an empty list if it has none, or None if the drug isn't stored."""
        if self._compounds.get(cid) is None:
            return None
        return self._drug_targets(cid)

    def targets_of(self, compound: Compound) -> DrugTargets:
        """The targets of a drug resolved from the store, an empty list if it has none."""
        return self._drug_targets(compound.cid)

    def _drug_targets(self, cid: int) -> DrugTargets:
        records = self._targets.get(cid).targets
        return DrugTargets(cid=cid, targets=[to_target(record) for record in records])


def to_target(record: TargetRecord) -> Target:
    return Target(
        target_chembl_id=record.target_chembl_id,
        name=record.name,
        target_type=record.target_type,
        organism=record.organism,
        mechanism=record.mechanism,
        action_type=record.action_type,
        accessions=list(record.accessions),
        gene_symbols=list(record.gene_symbols),
        source=TARGET_SOURCE,
        source_url=CHEMBL_TARGET_URL.format(target_chembl_id=record.target_chembl_id),
    )
