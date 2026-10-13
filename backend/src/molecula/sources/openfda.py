from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from molecula.sources.http import SourceClient
from molecula.sources.parsing import parse

LABELS = "https://api.fda.gov/drug/label.json"
PAGE_SIZE = 100
# openFDA also reads the key from an `api_key` query parameter, but then it would be part of the
# URL, which is cached, stored and logged. The header keeps it out of all three.
API_KEY_HEADER = "X-Api-Key"
LABEL_METADATA = frozenset({"set_id", "id", "version", "effective_time", "openfda"})


class OpenFdaFields(BaseModel):
    """The harmonized `openfda` block; every field is a list, empty when openFDA has no value."""

    model_config = ConfigDict(frozen=True)

    generic_name: list[str] = []
    brand_name: list[str] = []
    substance_name: list[str] = []
    product_type: list[str] = []
    route: list[str] = []
    application_number: list[str] = []


class Label(BaseModel):
    """One drug label (SPL). `sections` holds every text field by its openFDA name, e.g.
    `mechanism_of_action`, `boxed_warning` or the HTML `adverse_reactions_table`."""

    model_config = ConfigDict(frozen=True)

    set_id: str
    effective_time: str
    openfda: OpenFdaFields = OpenFdaFields()
    sections: dict[str, list[str]]

    @model_validator(mode="before")
    @classmethod
    def collect_sections(cls, data: Any) -> Any:
        if not isinstance(data, dict) or "sections" in data:
            return data
        metadata = {key: value for key, value in data.items() if key in LABEL_METADATA}
        sections = {key: value for key, value in data.items() if key not in LABEL_METADATA}
        return {**metadata, "sections": sections}


class ResultsMeta(BaseModel):
    total: int


class Meta(BaseModel):
    results: ResultsMeta


class LabelPage(BaseModel):
    meta: Meta
    labels: list[Label] = Field(alias="results")


class OpenFdaClient:
    """openFDA drug labels: every label listed under a generic name."""

    def __init__(
        self,
        http: SourceClient,
        *,
        api_key: SecretStr | None = None,
        page_size: int = PAGE_SIZE,
    ) -> None:
        self._http = http
        self._api_key = api_key
        self._page_size = page_size

    def labels(self, generic_name: str, *, refresh: bool = False) -> list[Label]:
        """Every label whose generic name contains `generic_name` as a phrase, in `set_id` order.

        Combination products are included ("acetaminophen" also finds hydrocodone bitartrate and
        acetaminophen). Raises SourceNotFound when openFDA has no label for the name.
        """
        search = f'openfda.generic_name:"{generic_name}"'
        labels: list[Label] = []
        while True:
            # Sorting on a unique field keeps the pages from overlapping or skipping labels.
            params = {
                "search": search,
                "sort": "set_id:asc",
                "limit": str(self._page_size),
                "skip": str(len(labels)),
            }
            response = self._http.get(
                LABELS, params=params, headers=self._headers(), refresh=refresh
            )
            page = parse(response, LabelPage)
            labels += page.labels
            if not page.labels or len(labels) >= page.meta.results.total:
                return labels

    def _headers(self) -> dict[str, str]:
        if self._api_key is None:
            return {}
        return {API_KEY_HEADER: self._api_key.get_secret_value()}
