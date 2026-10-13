import re
from difflib import get_close_matches
from functools import cached_property

from molecula.schemas.compounds import (
    Compound,
    DrugMention,
    Resolution,
    Structure,
    Suggestion,
    SupportedDrug,
)
from molecula.store.compounds import CompoundRecord, CompoundStore
from molecula.store.structures import ConformerFiles

PUBCHEM_COMPOUND_URL = "https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"
MAX_SUGGESTIONS = 3
MIN_PREFIX_LENGTH = 4

# Prescriptions and openFDA name the salt or hydrate ("imatinib mesylate"), the store holds the
# parent compound. Ester words like "acetate" are left out: medroxyprogesterone acetate is a
# different molecule from medroxyprogesterone.
SALT_WORDS = frozenset(
    {
        "anhydrous",
        "besilate",
        "besylate",
        "bisulfate",
        "bitartrate",
        "bromide",
        "calcium",
        "chloride",
        "citrate",
        "dihydrate",
        "dihydrochloride",
        "dimesylate",
        "disodium",
        "fumarate",
        "gluconate",
        "hbr",
        "hcl",
        "hemifumarate",
        "hemihydrate",
        "hyclate",
        "hydrate",
        "hydrobromide",
        "hydrochloride",
        "lactate",
        "magnesium",
        "malate",
        "maleate",
        "mesilate",
        "mesylate",
        "monohydrate",
        "nitrate",
        "oxalate",
        "pamoate",
        "phosphate",
        "potassium",
        "sesquihydrate",
        "sodium",
        "succinate",
        "sulfate",
        "sulphate",
        "tartrate",
        "tosylate",
        "trihydrate",
        "xinafoate",
    }
)


class CompoundService:
    """Drug names to compounds from the local store. Molecula supports exactly what is stored."""

    def __init__(
        self, store: CompoundStore, conformers: ConformerFiles, *, suggestion_cutoff: float
    ) -> None:
        self._store = store
        self._conformers = conformers
        self._suggestion_cutoff = suggestion_cutoff

    def resolve(self, name: str) -> Resolution:
        """The supported drug a name, brand, alias or salt name refers to, ignoring case.

        An unsupported name gets the scope names and aliases it starts or is close to as
        suggestions, never as the answer: look-alike drug names (Celexa, Celebrex) make a silent
        correction unsafe.
        """
        query = " ".join(name.split())
        candidates = name_candidates(query)
        for candidate in candidates:
            if match := self._store.find(candidate):
                return Resolution(
                    query=query,
                    status="found",
                    compound=to_compound(match.compound),
                    matched_alias=match.alias,
                    match_kind=match.kind,
                )
        # The last candidate is the name without salt words, so "imatinb mesylate" finds imatinib.
        suggestions = self._suggest(candidates[-1]) if candidates else []
        return Resolution(query=query, status="not_supported", suggestions=suggestions)

    def _suggest(self, name: str) -> list[Suggestion]:
        """Up to three scope names and aliases that start with the name or are close to it.

        Spellings that start with the name come first, shortest first, from four letters on: a
        typed beginning ("amox") says more than a similar spelling (Diamox, a different drug).
        """
        spellings = self._scope_spellings()
        typed = name.casefold()
        starting = (
            sorted((spelling for spelling in spellings if spelling.startswith(typed)), key=len)
            if len(typed) >= MIN_PREFIX_LENGTH
            else []
        )
        close = get_close_matches(
            typed, list(spellings), n=MAX_SUGGESTIONS, cutoff=self._suggestion_cutoff
        )
        matches = list(dict.fromkeys([*starting, *close]))[:MAX_SUGGESTIONS]
        return [spellings[match] for match in matches]

    def _scope_spellings(self) -> dict[str, Suggestion]:
        """Every scope name and alias by its casefolded spelling; a scope name wins a clash."""
        records = self._store.all()
        aliases = self._store.scope_aliases()
        spellings: dict[str, Suggestion] = {}
        for record in records:
            spellings[record.name.casefold()] = Suggestion(
                alias=record.name, cid=record.cid, name=record.name
            )
        for record in records:
            for alias in aliases.get(record.cid, []):
                spellings.setdefault(
                    alias.casefold(), Suggestion(alias=alias, cid=record.cid, name=record.name)
                )
        return spellings

    def find_mentions(self, text: str) -> list[DrugMention]:
        """The supported drugs a text names by scope name or alias, in the order they appear.

        Only whole words count, and a longer name wins over a name inside it ("acetylsalicylic
        acid"). PubChem synonyms are left out: they include codes and fragments that would match
        ordinary words.
        """
        spellings = self._scope_spellings()
        mentions = []
        for match in self._mention_pattern.finditer(text):
            drug = spellings[match.group().casefold()]
            mentions.append(
                DrugMention(
                    text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    cid=drug.cid,
                    name=drug.name,
                )
            )
        return mentions

    @cached_property
    def _mention_pattern(self) -> re.Pattern[str]:
        # Abbreviations match only in capitals: "ASS" is aspirin in German, "ass" an English word.
        spellings = sorted(
            (suggestion.alias for suggestion in self._scope_spellings().values()),
            key=len,
            reverse=True,
        )
        alternatives = [
            re.escape(spelling) if spelling.isupper() else f"(?i:{re.escape(spelling)})"
            for spelling in spellings
        ]
        return re.compile(rf"(?<!\w)(?:{'|'.join(alternatives)})(?!\w)")

    def get_compound(self, cid: int) -> Compound | None:
        record = self._store.get(cid)
        return to_compound(record) if record else None

    def get_structure(self, cid: int) -> Structure | None:
        """The stored 3D conformer, or None for an unknown CID or a compound without 3D."""
        record = self._store.get(cid)
        if record is None or record.conformer_source is None:
            return None
        sdf = self._conformers.read(cid)
        if sdf is None:
            return None
        return Structure(cid=cid, sdf=sdf, conformer_source=record.conformer_source)

    def list_drugs(self) -> list[SupportedDrug]:
        """Every supported drug by name, with the scope aliases it can be found by."""
        aliases = self._store.scope_aliases()
        return [
            SupportedDrug(
                cid=record.cid,
                name=record.name,
                aliases=aliases.get(record.cid, []),
                has_3d=record.has_3d,
            )
            for record in self._store.all()
        ]


def name_candidates(query: str) -> list[str]:
    """The name as given, then without its salt and hydrate words if any are left after that."""
    if not query:
        return []
    words = query.split()
    parent = [word for word in words if word.casefold() not in SALT_WORDS]
    if parent and len(parent) < len(words):
        return [query, " ".join(parent)]
    return [query]


def to_compound(record: CompoundRecord) -> Compound:
    return Compound(
        cid=record.cid,
        name=record.name,
        inchikey=record.inchikey,
        smiles=record.smiles,
        formula=record.formula,
        molecular_weight=record.mw,
        xlogp=record.xlogp,
        tpsa=record.tpsa,
        hbond_donors=record.hbd,
        hbond_acceptors=record.hba,
        rotatable_bonds=record.rotb,
        heavy_atoms=record.heavy_atoms,
        has_3d=record.has_3d,
        conformer_source=record.conformer_source,
        source=record.source,
        source_url=PUBCHEM_COMPOUND_URL.format(cid=record.cid),
    )
