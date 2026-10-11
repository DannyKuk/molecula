# Data plan

Where Molecula's data comes from, how it is turned into the local store, and what is known to work. Everything marked **verified** was run live against the real APIs on 2026-10-11 (see `docs/spikes/data-check/`). Everything else is a design decision or an assumption and says so.

---

## 1. Summary

All the data the app needs exists, is free, and can be fetched by script. The early problems (wrong ligand codes, no targets found) were bugs in the queries, not gaps in the data. Section 3 has the corrected queries.

Known limits, and how the app handles them:

1. **There is no free structured drug–drug interaction database.** NLM's RxNav interaction API was shut down in January 2024, and DrugBank needs a licence. Interaction questions are answered by retrieval over the labels' `drug_interactions` sections, with citations and no "safe/unsafe" verdict.
2. **openFDA has US labels only.** Paracetamol and non-US brands (e.g. Ibuflam) need a name layer: PubChem synonyms for generics, plus a small hand-written brand map.
3. **Some drugs have no target complex.** Paracetamol, metformin, cetirizine and omeprazole either have no clear target or no structure of the drug bound to it. They get a molecule-only view, and the app explains why.

---

## 2. Features → data

| Feature | Data | Status |
|---|---|---|
| Knowledge base: embeddings, chunking, similarity search | openFDA labels (Rx + OTC), section-aware chunks | verified |
| Query translation | brand / non-US name → US generic; German → English; multi-query | name layer verified (PubChem) |
| Structured retrieval | chunk metadata `{substance, section_group, product_type, source}` with self-query filters; SQL tables for properties and targets | metadata verified in every label |
| Agent tools | PubChem (properties, 3D), ChEMBL (mechanism → target), RCSB (complex), own contact calculation | verified |
| Safety | openFDA disclaimer; `overdosage` not indexed; no personal dosing | design decision (§5.5) |
| Sources in the UI | every chunk has `set_id`, `effective_time` and a DailyMed link | verified |
| Hybrid search | BM25 next to embeddings: drug names, "QT prolongation", "CYP3A4" need exact matches | design decision |
| Tools as an MCP server | the data services exposed through FastMCP (§4) | design decision |
| Remote MCP server | public PubChem MCP at `https://pubchem.caseyjhand.com/mcp` | verified (answered `initialize`); community-run, so the local tools stay the default |
| RAG evaluation and A/B tests | QA set generated from label sections; dense vs hybrid, query translation on/off | design decision |
| Knowledge-base updates | openFDA `effective_time` filter; the bulk export is refreshed weekly | verified (latest export 2026-10-09) |
| Multi-language | German query → English retrieval → German answer | design decision |

---

## 3. Sources (verified)

| Source | Use | Query | Notes |
|---|---|---|---|
| PubChem PUG REST | name → CID, parent compound, properties, 3D SDF, synonyms | `/compound/name/{name}/cids/JSON`, `/compound/cid/{cid}/cids/JSON?cids_type=parent`, `/compound/cid/{cid}/property/…/JSON`, `/compound/cid/{cid}/SDF?record_type=3d` | throttles with HTTP 503; ≤ 4 req/s with backoff. NCBI's edge also blocks an IP with HTTP 429 for several minutes; on 2026-10-11 that hit at about 1.2 req/s after ~230 requests, so ingest steps stop on a block and resume from the cache. The property is `SMILES` (formerly `IsomericSMILES`) |
| ChEMBL | drug → mechanism → target → UniProt, gene names | `/chembl/api/data/mechanism.json?parent_molecule_chembl_id={id}`, then `/target/{tid}.json` | mechanisms hang on the salt form (imatinib mesylate CHEMBL1642), so filter by **`parent_molecule_chembl_id`**; querying the parent's own ID returns nothing |
| RCSB: ligand code | InChIKey → PDB ligand code | search API, `service: "text_chem"`, attribute `rcsb_chem_comp_descriptor.InChIKey`, `return_type: "mol_definition"` | returns exactly STI, CFF, AIN, TYL. `service: "text"` returns unrelated codes |
| RCSB: stereo fallback | SMILES → candidates whose InChIKey connectivity block matches | `service: "chemical"`, `match_type: "graph-relaxed-stereo"`, then `data.rcsb.org/rest/v1/core/chemcomp/{code}` | ibuprofen → IBP, IZP; donepezil → E20; warfarin → RWF, SWF |
| RCSB: complex | entries with the ligand **and** the target | entries containing the ligand (`rcsb_nonpolymer_entity_container_identifiers.nonpolymer_comp_id`), then one GraphQL request (`data.rcsb.org/graphql`, `entries(entry_ids: …)`) for title, resolution and, per protein entity, organism, chains and gene names; keep the entries with an entity whose depositor gene name or UniProt primary gene name is a target gene | match the **gene name**, not the UniProt accession: many reference structures are non-human (COX from sheep and mouse, 1IEP is mouse ABL). Gene names match ignoring case (mouse `Abl1`). The search-side AND with `rcsb_entity_source_organism.rcsb_gene_name.value` misses entries whose depositor left the gene empty: STI AND ABL1 returns 11 entries without 1IEP or 3MSS (checked 2026-10-11), and UniProt gene names are not searchable (HTTP 400). UniProt synonyms are left out because they can name another protein (COX2 is also a synonym of MT-CO2) |
| openFDA | label text for the knowledge base | `/drug/label.json` per drug in scope | 262,895 labels, 1.77 GB zipped. The scope list keeps the corpus small, so no bulk download |
| RDKit | 3D fallback (ETKDG + MMFF), bond orders for PDB ligands | local | only where PubChem has no data |

---

## 4. Architecture: answers come from the local store

```
           build time (python -m molecula.ingest …)                       run time
 PubChem ─┐                                                     ┌─ FastAPI ──> Next.js
 ChEMBL  ─┼─> ingest steps ──> data/build/molecula.db (SQLite)──┤
 RCSB    ─┤                    data/build/structures/           └─ MCP server ──> LangChain agent
 openFDA ─┘                    data/build/index/ (vectors + BM25)
```

- **One service layer** (`backend/src/molecula/services/`). FastAPI routes, agent tools and the MCP server are thin wrappers around the same functions.
- **The store is the supported set.** Services read only the store; a drug that isn't in it is answered as "not supported", and the UI lists what is. Sources are called only by the ingest steps (including the label update, §5.6), through the rate-limited client with retries on 429/503, and every stored row records `source` and `fetched_at`.
- **No live fallback** (decided in #30). For a drug outside the scope a live lookup would only bring properties and 3D, with no label, no targets and no reviewed complex. It can also answer about the wrong drug: PubChem maps "Vicodin" (hydrocodone + acetaminophen) to acetaminophen's CID (checked 2026-10-11). Complexes outside the reviewed hero set would be risky too, because an unreviewed complex can be scientifically wrong (ibuprofen bound to albumin is not its mechanism).
- **Salt and brand names** resolve through the stored synonyms (scope name, scope aliases, top PubChem synonyms) and, failing that, the name without salt and hydrate words ("imatinib mesylate" → imatinib).
- **`OFFLINE=1`** stops the ingest steps from calling a source. Evals always run this way.

---

## 5. Pipeline

### 5.1 Scope list (`data/scope.yaml`)

100–150 drugs: commonly prescribed, common OTC, and the hero set. Each entry has a generic name and optional aliases (`Ibuflam: ibuprofen`, `Tylenol: acetaminophen`, `paracetamol: acetaminophen`). A fixed list bounds the corpus, the eval set and the API calls.

### 5.2 Compounds (`ingest compounds`)

name → CID → parent CID → properties, InChIKey, SMILES → 3D SDF (RDKit fallback) → top 30 synonyms for the name layer and for BM25. Peptides such as insulin and semaglutide are marked "no small-molecule 3D". `compound.name` is the scope name; PubChem's title is sometimes a systematic name (glimepiride, doxycycline).

When PubChem has no conformer, RDKit generates one (ETKDG with a fixed seed, then MMFF) for molecules up to 100 heavy atoms. PubChem skips flexible small molecules too, e.g. ritonavir (50 heavy atoms, 18 rotatable bonds). Larger molecules get `has_3d = false`. Conformers are written to `data/build/structures/compounds/{cid}.sdf`.

Tables: `compound(cid, name, inchikey, smiles, formula, mw, xlogp, tpsa, hbd, hba, rotb, heavy_atoms, has_3d, conformer_source, source, fetched_at)`, `synonym(alias, cid, kind)` with `kind` one of `name`, `alias` (from the scope) or `pubchem`.

Displayed properties come from PubChem (citable). RDKit's Crippen logP and acceptor counts differ by design (imatinib: Crippen 4.59 vs XLogP3 3.5).

### 5.3 Targets and complexes (`ingest targets`)

1. InChIKey → ChEMBL parent ID → mechanisms → target, action type, UniProt accessions, gene names.
2. InChIKey → PDB ligand code(s): exact first, connectivity fallback second.
3. Entries with the ligand code, kept when a protein entity comes from a target gene (depositor or UniProt primary gene name) → candidate entries.
4. Rank by resolution (`rcsb_entry_info.resolution_combined`); prefer human proteins.
5. A person reviews the candidates and writes the chosen entry to `data/hero_set.yaml`: `pdb, ligand_code, chain, target, organism, note`.

**Prodrugs** are bound in their active form, which the automatic search can't find: oseltamivir → G39 (oseltamivir carboxylate), tamoxifen → OHT (4-hydroxytamoxifen), aspirin → salicylate plus an acetylated serine. These are entered in `hero_set.yaml` by hand.

Candidates found automatically (each still needs review; full output in `docs/spikes/data-check/hero_scan.json`):

| Drug | Target | Candidate entries |
|---|---|---|
| imatinib | ABL1 (mouse) | 1IEP (checked: contacts match the literature), 2HYY |
| dasatinib | ABL1 | 2GQG |
| caffeine | adenosine A2A receptor | 3RFM, 5MZP |
| atorvastatin | HMG-CoA reductase | 1HWK |
| ibuprofen | COX-2 (mouse) | 4PH9 |
| celecoxib | COX-2 | 3LN1 |
| diclofenac | COX-2 | 3N8Y |
| naproxen | COX-2 | 3NT1 |
| methotrexate | DHFR | 1U72, 1DLS |
| donepezil | acetylcholinesterase | 4EY7 |
| gefitinib | EGFR | 4WKQ |
| erlotinib | EGFR | 1M17 |
| sitagliptin | DPP-4 | 1X70 |
| lisinopril | ACE | 1O86 |
| acetazolamide | carbonic anhydrase II | many; pick the best resolution |
| oseltamivir (G39) | neuraminidase | 17 entries |
| zanamivir | neuraminidase | 11 entries |
| ritonavir | HIV protease, CYP3A4 | 3NXU (CYP3A4) |
| warfarin | VKORC1 | 6WV3 |
| tamoxifen (OHT) | ESR1 | 4Q50 |

Molecule-only by design: paracetamol, metformin, cetirizine, omeprazole. Sildenafil and raltegravir hit a PubChem throttle during the scan and need a re-run (VIA / 1UDT exists).

### 5.4 Complex processing (`ingest complexes`)

- **PDB ligands have no hydrogens and no bond orders.** RDKit `AssignBondOrdersFromTemplate` with the SMILES from the chem-comp record fixes the bonds and the donor/acceptor typing.
- Pick one chain and ligand copy by rule: complete ligand → most contacts → lowest B-factor. Record the choice. (1IEP chain A gives 6 H-bonds, chain B 5.)
- Drop waters, ions and buffer molecules (GOL, EDO, SO4, …).
- Contacts: pocket residues ≤ 4.0 Å, H-bonds between N/O atoms ≤ 3.3 Å. This reproduces the published imatinib–ABL contacts (Ile360, Thr315, Met318, Asp381, Glu286, His361).
- Output: one compact JSON per complex (CA trace with secondary structure, pocket atoms, ligand atoms and bonds, contacts), so the frontend never parses mmCIF.

### 5.5 Labels → knowledge base (`ingest labels`)

Measured on single-ingredient labels:

| Drug | Rx labels | Rx with `mechanism_of_action` | Rx unique by text hash | OTC labels | OTC unique |
|---|---|---|---|---|---|
| imatinib | 22 | 21 | 20 | 0 | 0 |
| atorvastatin | 246 | 215 | 86 | 0 | 0 |
| ibuprofen | 205 | 3 | 46 | 649 | 342 |
| cetirizine | 20 | 13 | 11 | 363 | 146 |
| acetaminophen | 7 | 7 | 5 | 304 | 223 |
| caffeine | 15 | 6 | 9 | 46 | 22 |

Consequences:

- **Text-hash dedup doesn't work.** Generic manufacturers change small details, so 20 of 22 imatinib labels count as unique. Instead, keep **one canonical label per (substance, Rx)** and **one per (substance, OTC)**:
  - single ingredient (`len(openfda.substance_name) == 1`)
  - has `mechanism_of_action`, then brand / reference label, then latest `effective_time`, then most sections
- **Mechanism text is often in `clinical_pharmacology`.** Older (non-PLR) Rx labels, ibuprofen's for example, have no `mechanism_of_action` section. Both map to `section_group = "pharmacology"`.
- **Section groups** cover the three layouts (PLR Rx, older Rx, OTC Drug Facts): `pharmacology, indications, dosing, warnings, contraindications, interactions, adverse_reactions, otc_consumer`.
- **Safety at index time:** `overdosage` is not indexed (it lists toxic doses). `dosing` is indexed with `sensitive=true`, so general label dosing can be cited but never turned into personal advice.
- `*_table` HTML fields are dropped; the plain-text versions are kept.
- Chunks: split by section, then recursively to ~500 tokens with 50 overlap. Metadata: `{cid, substance, brand, product_type, section_group, set_id, effective_time, url}`.

**Corpus estimate:** a canonical Rx label is 40–170k characters (measured), an OTC label 3–5k. For 120 drugs that is ~8–10M characters ≈ 2–2.5M tokens ≈ 4–5k chunks. Local embeddings handle this on a CPU in minutes.

### 5.6 Updates (`ingest update`)

For each drug in scope, query openFDA with `effective_time:[{last_run} TO *]`. If the canonical label changed, re-chunk and re-embed only that drug and log the change. Triggered from the UI and on a schedule.

### 5.7 Eval datasets (`backend/evals/`)

- **Tool accuracy:** ~50 questions with exact answers from the `compound` table, scored automatically.
- **RAG QA:** ~60 questions generated from canonical label sections, reviewed by hand (generated "ground truths" are often wrong). Scored with RAGAs: faithfulness, answer relevancy, context precision and recall.
- **Safety:** ~40 prompts covering personal dosing, lethal dose, synthesis, and injection hidden in retrieved text.
- **Multi-language:** 15 German questions compared with the English answers.

---

## 6. Risks

| Risk | Impact | Handling |
|---|---|---|
| Scope grows faster than the core gets finished | high | core features first; 3D polish last |
| Label text is long and legalistic, so answers read dry | medium | prompt for plain language with citations; optionally Wikipedia pharmacology sections for the hero drugs (CC BY-SA, attributed) as a second source |
| Interaction answers read as medical advice | medium | quote labels with citations; show the openFDA disclaimer; no verdicts |
| Community PubChem MCP goes offline | low | used only as the remote-MCP option; local tools are the default |
| Local 8B models are unreliable at tool calling | medium | measured in the benchmarks; cloud model stays the default |
| PubChem / RCSB flakiness | low | local store, retries, `OFFLINE=1` |
| Licensing | low | openFDA CC0, PDB free, PubChem mostly public domain, ChEMBL CC BY-SA 3.0 (attributed). Raw dumps are not committed |
