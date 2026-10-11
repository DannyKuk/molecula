# Name resolution: from a typed name to a supported drug

> **Answer:** a name is looked up in the store only, ignoring case: the scope name first, then the scope's hand-written aliases (brands, non-US names, German spellings), then the top 30 PubChem synonyms of each drug. If that misses, the name is tried once more without salt and hydrate words ("imatinib mesylate" → imatinib). Anything else is `not_supported`, with up to three close scope names or aliases as **suggestions** (`difflib`, cutoff 0.8). A suggestion is never applied on its own: the user picks it. Look-alike drug names such as Celexa and Celebrex make a silent correction unsafe.

## Question

People type brands (Gleevec, Tylenol), non-US names (paracetamol, Ibuflam), the salt name from a prescription (metformin hydrochloride) and typos (Gleevek). Each has to land on the right stored drug or on a clear "not supported", never on a different drug. And it has to work offline, because the app never calls a source at run time ([local store](local-store.md)).

## What we tried

- **Every scope name through PubChem** (PR #26): does it resolve to exactly one parent compound, and is PubChem's title usable as a display name?
- **Brands and foreign names against PubChem** in the data check and while recording fixtures (spike, PR #31, PR #32).
- **Resolution on the built store** (PR #49): brands, aliases, salt names, combination brands, vague names.
- **Suggestions** with `difflib.get_close_matches` over the scope names and aliases, cutoff 0.8, on the real store (#51, PR #78), and the similarity of known look-alike pairs.
- **Rechecked on 2026-10-12** against a copy of the store: 134 drugs, 323 scope names and aliases, 4,020 PubChem synonyms.

## Result

**Names that resolve, or don't**

| Typed | What it is | Result | Matched on |
|---|---|---|---|
| Gleevec | US brand | imatinib | scope alias |
| Tylenol / paracetamol | US brand / non-US name | acetaminophen | scope alias |
| Ibuflam | German brand, unknown to PubChem (404) | ibuprofen | scope alias |
| imatinib mesylate | salt name | imatinib | name without salt words |
| metformin hydrochloride | salt name | metformin | name without salt words |
| Doxycycline hyclate | salt name | doxycycline | PubChem synonym |
| metformine | French name | metformin | PubChem synonym |
| Vicodin | hydrocodone + acetaminophen | `not_supported` | – |
| Bactrim | trimethoprim + sulfamethoxazole | `not_supported` | – |
| insulin | vague: the scope has insulin glargine | `not_supported` | – |

**Suggestions for unsupported names** (cutoff 0.8)

| Typed | Suggested | Status |
|---|---|---|
| ibuprofin | ibuprofen | `not_supported` |
| paracetamoll | paracetamol (acetaminophen) | `not_supported` |
| Gleevek | Gleevec (imatinib) | `not_supported` |
| Zyrtek | Zyrtec (cetirizine) | `not_supported` |
| amoxicilin | amoxicillin | `not_supported` |
| asprin | aspirin | `not_supported` |
| imatinb mesylate | imatinib | `not_supported` |
| Celexa | none: Celebrex scores 0.714 | `not_supported` |
| hydroxizine | none: L-thyroxine scores 0.727 | `not_supported` |
| xyz | none | `not_supported` |

**PubChem titles that differ from the scope name** (6 of 129, PR #26)

| Scope name | PubChem title |
|---|---|
| ibuprofen | Ibuprofen, (+-)- |
| levothyroxine | Thyroxine |
| albuterol | Salbutamol |
| hydrocortisone | Cortisol |
| glimepiride, doxycycline | a systematic (IUPAC) name |

## What it shows

- **Hand-written aliases are needed.** PubChem knows neither Ibuflam nor the German spellings Amlodipin and Torasemid (PR #32), and openFDA spells the US names (torsemide, acetaminophen).
- **PubChem synonyms add salt and foreign names for free**, but they are noisy: most are registry codes and systematic names. They are used to find a drug, never to suggest one.
- **0.8 separates typos from look-alikes** on this store: every typo above scores high enough, and the closest look-alikes (0.714, 0.727) stay below.
- **A suggestion must not become an answer.** Medicine has known look-alike names (Celexa / Celebrex, hydroxyzine / hydralazine), so a silent correction could answer about the wrong drug (#51).
- **Combination brands stay unsupported.** PubChem maps them to one ingredient, and combination products aren't in the scope.

## Decided along the way

- **The display name is the scope name**, not PubChem's title (#4 comment, #29).
- **Priority when a spelling matches several drugs:** scope name, then scope alias, then PubChem synonym (PR #49). The scope loader already refuses an alias that points to two drugs (PR #26), and two scope names for one parent compound are refused (PR #34).
- **Salt words:** "phosphate" and "succinate" are in, so "dexamethasone sodium phosphate" finds dexamethasone. "Acetate" is out, because medroxyprogesterone acetate is a different molecule from medroxyprogesterone. A name without salt words counts only if it matches a stored name exactly (PR #49).
- **Plain "insulin" stays unsupported.** Mapping it to insulin glargine would be wrong (PR #49).
- **Misspellings are not aliases.** "Trapentadol" from a hand-written list was read as tapentadol, not added (PR #32).
- **Suggestions come from the 323 scope names and aliases only**, best first, at most three; where two drugs share a spelling, the scope name wins. They are matched on the name without salt words (PR #78).
- **The cutoff is a setting**, `NAME_SUGGESTION_CUTOFF` (default 0.8); a value outside 0–1 stops the app at startup (PR #78).
- **No live PubChem lookup for unknown names.** Besides the reasons in [local store](local-store.md), every typo sent to PubChem would become a cached 404 (#30 comment).

## Limits

- **No phonetic matching** (out of scope in #51).
- **German spellings exist only for the drugs on the hand-written list** (PR #32); the rest of the scope has none yet.
- **Nobody sees the suggestions yet.** The drugs page (#79) and the chat's "not supported" answer (#16) are still to show them.
- **A combination brand gets a bare "not supported"**, without saying that it is a combination Molecula doesn't cover (#30 comment).
- **The cutoff was checked on one store and a short list of typos.** A new scope entry can bring a new look-alike pair; the look-alike tests in `tests/services/test_compounds.py` use the store's real names.

## Reproduce

```bash
cd backend
uv run pytest tests/services/test_compounds.py               # resolution, salt words, suggestions, look-alikes
uv run uvicorn molecula.main:app --port 8000                 # reads data/build/molecula.db
curl "http://localhost:8000/drugs/resolve?name=Gleevek"      # not_supported, suggests Gleevec (imatinib)
curl "http://localhost:8000/drugs/resolve?name=Celexa"       # not_supported, no suggestion
uv run python -c "import difflib; print(difflib.SequenceMatcher(None, 'celexa', 'celebrex').ratio())"   # 0.714...
```
