from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class HeroComplex(BaseModel):
    """One reviewed drug-target complex from `data/hero_set.yaml`."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    drug: str = Field(min_length=1)
    pdb: str = Field(pattern=r"^[0-9][A-Z0-9]{3}$")
    ligand_code: str = Field(pattern=r"^[A-Z0-9]{1,5}$")
    ligand_copy: str = Field(pattern=r"^[A-Za-z0-9]+/-?[0-9]+$")
    chain: str = Field(pattern=r"^[A-Za-z0-9]+$")
    target: str = Field(min_length=1)
    organism: str = Field(min_length=1)
    showcase: bool = False
    caption: str | None = None
    note: str = Field(min_length=1)


class HeroSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    complexes: list[HeroComplex] = Field(min_length=1)

    @model_validator(mode="after")
    def one_complex_per_drug(self) -> Self:
        seen: set[str] = set()
        for complex_ in self.complexes:
            key = complex_.drug.casefold()
            if key in seen:
                raise ValueError(f"two complexes for {complex_.drug}")
            seen.add(key)
        return self


def load_hero_set(path: Path) -> HeroSet:
    return HeroSet.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
