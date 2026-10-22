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
from molecula.store.compounds import CompoundRecord, CompoundStore, SynonymMatch
from molecula.store.structures import ConformerFiles

PUBCHEM_COMPOUND_URL = "https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"
MAX_SUGGESTIONS = 3
MIN_PREFIX_LENGTH = 4
# How close a word must be to a drug spelling to be taken as a possible drug name. Over the 94
# retrieval questions and 280 input-check messages, 0.8 also took English words ("raise" for
# Gralise, "score" for Coreg); 0.85 took only drug names, misspelled or in German (#287).
NEAR_CUTOFF = 0.85
# Shorter words are left out: abbreviations like "ASS" count only in capitals.
MIN_NEAR_NAME_LENGTH = 5
NEGATION_BEFORE = re.compile(r"(?i)\bnon[- ]?$")
NEGATION_AFTER = re.compile(r"(?i)^[- ]?free\b")

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

        A product name the store doesn't know is the one supported drug named in it: "Voltaren
        arthritis gel" is diclofenac, by its alias Voltaren. A name with two drugs in it stays
        unknown rather than picking one.

        An unsupported name gets the scope names and aliases it starts or is close to as
        suggestions, never as the answer: look-alike drug names (Celexa, Celebrex) make a silent
        correction unsafe.
        """
        query = " ".join(name.split())
        candidates = name_candidates(query)
        for candidate in candidates:
            if match := self._store.find(candidate):
                return found(query, match)
        if match := self._drug_inside(query):
            return found(query, match)
        # The last candidate is the name without salt words, so "imatinb mesylate" finds imatinib.
        suggestions = self._suggest(candidates[-1]) if candidates else []
        return Resolution(query=query, status="not_supported", suggestions=suggestions)

    def _drug_inside(self, name: str) -> SynonymMatch | None:
        """The one supported drug a name mentions, by the stored spelling it mentions it with.
        A drug the name says the product lacks ("Non-Aspirin", "aspirin free") doesn't count."""
        mentions = [mention for mention in self.find_mentions(name) if not negated(name, mention)]
        if len({mention.cid for mention in mentions}) != 1:
            return None
        match = self._store.find(mentions[0].text)
        return match if match and match.compound.cid == mentions[0].cid else None

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

    def _brand_spellings(self) -> dict[str, Suggestion]:
        """The label brands that aren't also a scope name or alias, by `spelling_key`."""
        scope = {spelling_key(spelling) for spelling in self._scope_spellings()}
        names = {record.cid: record.name for record in self._store.all()}
        spellings: dict[str, Suggestion] = {}
        for cid, brands in self._store.label_brands().items():
            for brand in brands:
                key = spelling_key(brand)
                if key not in scope and cid in names:
                    spellings.setdefault(key, Suggestion(alias=brand, cid=cid, name=names[cid]))
        return spellings

    def _mention_spellings(self) -> dict[str, Suggestion]:
        scope = {spelling_key(s.alias): s for s in self._scope_spellings().values()}
        return scope | self._brand_spellings()

    def find_mentions(self, text: str) -> list[DrugMention]:
        """The supported drugs a text names by scope name, alias or label brand, in the order
        they appear.

        Only whole words count, and a longer name wins over a name inside it ("acetylsalicylic
        acid"). PubChem synonyms are left out: they include codes and fragments that would match
        ordinary words.
        """
        spellings = self._mention_spellings()
        mentions = []
        for match in self._mention_pattern.finditer(text):
            drug = spellings[spelling_key(match.group())]
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

    def find_names(self, text: str) -> list[str]:
        """The words of a text that may name a drug, as written: each mention of a supported
        drug, then each other word close to one of their spellings ("Gleevc", "Cetirizin").
        Resolving them is left to `resolve`, which suggests a drug for a misspelling rather than
        taking it for that drug."""
        mentions = self.find_mentions(text)
        spellings = list(self._mention_spellings())
        near = [
            word.group()
            for word in re.finditer(rf"\w{{{MIN_NEAR_NAME_LENGTH},}}", text)
            if not any(mention.start <= word.start() < mention.end for mention in mentions)
            and get_close_matches(spelling_key(word.group()), spellings, n=1, cutoff=NEAR_CUTOFF)
        ]
        return list(dict.fromkeys([*(mention.text for mention in mentions), *near]))

    @cached_property
    def _mention_pattern(self) -> re.Pattern[str]:
        # Abbreviations match only in capitals: "ASS" is aspirin in German, "ass" an English word.
        # A label brand matches only with a capital first letter, because some brands are
        # ordinary words ("Stay Awake", "anti-diarrheal").
        scope = [
            (spelling, re.escape(spelling) if spelling.isupper() else f"(?i:{re.escape(spelling)})")
            for spelling in (suggestion.alias for suggestion in self._scope_spellings().values())
        ]
        brands = [(s.alias, brand_pattern(s.alias)) for s in self._brand_spellings().values()]
        alternatives = sorted([*scope, *brands], key=lambda pair: len(pair[0]), reverse=True)
        return re.compile(rf"(?<!\w)(?:{'|'.join(pattern for _, pattern in alternatives)})(?!\w)")

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


def spelling_key(spelling: str) -> str:
    """A spelling compared ignoring case, with hyphens as spaces: "Tirosint-SOL" is the label's
    "Tirosint SOL"."""
    return spelling.casefold().replace("-", " ")


def brand_pattern(brand: str) -> str:
    """A label brand with a capital first letter, the rest in any case and its words joined by a
    space or a hyphen."""
    words = re.split(r"[\s-]+", brand[1:])
    return f"{re.escape(brand[0].upper())}(?i:{'[ -]'.join(re.escape(word) for word in words)})"


def negated(name: str, mention: DrugMention) -> bool:
    """Whether `name` says its product is without the drug it mentions: "non-" before the
    mention or "free" after it."""
    return bool(
        NEGATION_BEFORE.search(name[: mention.start]) or NEGATION_AFTER.match(name[mention.end :])
    )


def found(query: str, match: SynonymMatch) -> Resolution:
    return Resolution(
        query=query,
        status="found",
        compound=to_compound(match.compound),
        matched_alias=match.alias,
        match_kind=match.kind,
    )


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
