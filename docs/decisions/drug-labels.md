# Drug labels

> **Answer:** The chatbot answers from **one openFDA label per drug and product type** (Rx and OTC). The label must have a single ingredient that is the drug itself. Among those labels, only the ones on the **drug's most common route** are kept. From these, the pick is the one with a `mechanism_of_action` section, then the brand's own label, then the newest. Thirteen groups of sections are stored, including pregnancy, patient leaflets and dosage forms (#92). `overdosage` never is, and dosing, specific populations, patient leaflets and abuse are flagged sensitive. 133 of 134 drugs have a label (11.1M characters); metamizole has no US label.

## Question

openFDA has hundreds of labels for a common drug: generics, repackagers, combinations, injections, creams. Which text should retrieval search? The text has to be:
- **about this drug alone**, not a combination product;
- **the usual product**, so "how does ibuprofen work" isn't answered from an eye drop or an IV label;
- **citable**: a `set_id`, a date and a DailyMed link;
- **safe to index**: no toxic-dose text, and dosing that is never turned into personal advice.

## What we tried

- **Text-hash dedup** of each drug's labels.
- **A rule-based pick per (drug, product type)**: single ingredient, then mechanism section → brand → newest → most sections, on all 134 drugs in the store.
- **The same rule with the most common route first**, after the first run picked niche products.

## Result

| | Labels found | Single-ingredient | Kept |
|---|---|---|---|
| imatinib | 22 | 22 (20 unique by text hash) | 1 Rx |
| ibuprofen | 1,147 | 970 (237 Rx, 733 OTC) | 1 Rx, 1 OTC |
| acetaminophen | 3,284 | 999 (21 Rx, 978 OTC) | 1 Rx, 1 OTC |

| Pick | Rule without route | With route first |
|---|---|---|
| ibuprofen Rx | Caldolor (IV) | ibuprofen tablets (oral; 233 oral vs 4 IV labels) |
| dexamethasone Rx | Ozurdex (implant in the eye) | Hemady (oral) |
| cetirizine Rx | Zerviate (eye drops) | cetirizine tablets (oral) |
| clotrimazole Rx | Clotic (ear drops) | clotrimazole (topical) |
| acetaminophen OTC | Feverall (rectal) | Tylenol 8 HR (oral) |

Full run: 129 Rx and 27 OTC labels, 5,662,726 characters, 361 requests in 4.4 min. A re-run made 0 requests and took 5 s. Per-drug tables are in [data-plan §5.5](../data-plan.md#55-labels--knowledge-base-ingest-labels).

## What it shows

- **Dedup by text doesn't work.** Generics change small details, so 20 of 22 imatinib labels are "unique".
- **The mechanism rule alone favours odd products.** Ibuprofen's only single-ingredient Rx label with `mechanism_of_action` is the IV Caldolor. Route first changed 23 of 156 picks, nearly all to the oral or topical form. Older labels keep the mechanism in `clinical_pharmacology`, which is stored in the same `pharmacology` group.
- **The phrase search also returns combinations.** Without the single-substance filter, acetaminophen's Rx pick would be Apadaz (benzhydrocodone + acetaminophen): it has a mechanism section and is a brand label. The oral hydrocodone + acetaminophen labels would also make oral the most common route, although every single-ingredient acetaminophen Rx label is an injection.
- **Coverage is good.** 5.7M characters with the first eight groups, 11.1M with all thirteen (#92), against the 8–10M estimate.

## Decided along the way

- **Search name:** the store name, which `scope.yaml` keeps as the US generic. Aliases are brands or non-US names, which openFDA's `generic_name` doesn't hold ("paracetamol" answers 404).
- **Salts count as the drug**, using the salt words from `services/compounds.py` ("oxalate" was added). When a product type has no label of the drug itself, another form counts: fluticasone propionate or furoate.
- **Brand's own label:** filed under an NDA or BLA, with a brand name that isn't the generic name. This leaves out authorized generics and biosimilars.
- **Route:** the route list counts as one sorted value. Equally common routes go by name; no route loses a tie.
- **Sections:** thirteen groups (eight until #92). `overdosage`, the preclinical sections, references, change notes and the `*_table` HTML copies are never stored. Dosing, the specific populations, the patient leaflets and abuse and dependence are stored with `sensitive = 1`: they may be quoted, never turned into personal advice. openFDA's disclaimer is stored once for the UI.
- **The patient-facing sections are kept** (#92). The first section list left out pregnancy, children and older people, patient leaflets, dosage forms and inactive ingredients without a reason, although users ask about them most. Measured on the 156 canonical labels (2026-10-12): `pregnancy` is on 123 of 129 Rx labels, `pediatric_use` on 122, `information_for_patients` on 117, a medication guide on 51. Adding them took the stored text from 5.66M to 11.10M characters and changed no canonical label. The patient leaflets and `keep_out_of_reach_of_children` hold no overdose passage with an amount; the abuse sections describe abuse routes as warnings (27 sentences on crushing, snorting or injecting), as `warnings_and_cautions` already did (7 sentences).

## Limits

- **Some Rx labels are really OTC Drug Facts**: guaifenesin (941 characters) and loratadine (944) have no real prescribing information.
- **The usual route isn't always the familiar one.** Acetaminophen's single-ingredient Rx labels are all injections; hydrocortisone's Rx pick is a topical cream (Proctozone-HC), not a tablet.
- **The HTTP cache is 1.97 GB** for 5.7 MB of stored text. It only matters for rebuilding; the planned snapshot (#35) leaves it out.
- US labels only. A drug without one (metamizole) answers from properties and targets, without label text.

## Reproduce

```bash
cd backend
uv run python -m molecula.ingest compounds         # the store's drugs, from data/scope.yaml
uv run python -m molecula.ingest labels            # OPENFDA_API_KEY in .env lifts the daily limit
OFFLINE=1 uv run python -m molecula.ingest labels  # re-run from the cache: no requests, same rows
uv run pytest tests/ingest/test_labels.py          # selection on recorded openFDA responses
```
