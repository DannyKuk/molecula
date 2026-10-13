from molecula.schemas.complexes import Complex
from molecula.store.structures import ComplexFiles


class ComplexService:
    """The reviewed drug-target complexes, as the complexes ingest step stored them.

    Only the drugs in `data/hero_set.yaml` have one. A complex is never fetched at run time, so
    any other drug has none, whatever the OFFLINE setting.
    """

    def __init__(self, files: ComplexFiles) -> None:
        self._files = files

    def get_complex(self, cid: int) -> Complex | None:
        text = self._files.read(cid)
        return Complex.model_validate_json(text) if text is not None else None
