from typing import Literal

type SourceName = Literal["pubchem", "chembl", "rcsb", "openfda"]

PUBCHEM: SourceName = "pubchem"
CHEMBL: SourceName = "chembl"
RCSB: SourceName = "rcsb"
OPENFDA: SourceName = "openfda"
