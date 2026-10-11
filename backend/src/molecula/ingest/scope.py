from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScopeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    name: str = Field(min_length=1)
    aliases: list[str] = []
    hero: bool = False
    note: str | None = None


class Scope(BaseModel):
    """The drugs Molecula covers. Names and aliases must each point to exactly one drug."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    drugs: list[ScopeEntry]

    @model_validator(mode="after")
    def names_and_aliases_are_unambiguous(self) -> Self:
        names: set[str] = set()
        for drug in self.drugs:
            key = drug.name.casefold()
            if key in names:
                raise ValueError(f"duplicate drug name: {drug.name}")
            names.add(key)

        owners: dict[str, str] = {}
        for drug in self.drugs:
            for term in [drug.name, *drug.aliases]:
                owner = owners.setdefault(term.casefold(), drug.name)
                if owner != drug.name:
                    raise ValueError(f"{term!r} points to both {owner} and {drug.name}")
        return self


def load_scope(path: Path) -> Scope:
    return Scope.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
