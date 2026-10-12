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
| Safety | openFDA disclaimer; `overdosage` indexed as sensitive, answers put emergency help first; no personal dosing | design decision (§5.5, #92) |
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
| ChEMBL | InChIKey → molecule → mechanism → target → UniProt, gene names | `/chembl/api/data/molecule.json?molecule_structures__standard_inchi_key={key}`, else `…__standard_inchi_key__startswith={first 14 characters}` (both with `only=molecule_chembl_id,pref_name,molecule_hierarchy`); `/mechanism.json?parent_molecule_chembl_id={id}`, then `/target/{tid}.json` | mechanisms hang on the salt form (imatinib mesylate CHEMBL1642), so filter by **`parent_molecule_chembl_id`**; querying the parent's own ID returns nothing. InChIKey lookup verified 2026-10-11 against the 134 PubChem InChIKeys in the store: 130 match exactly; buprenorphine matches only by connectivity block (5 records, one named); doxycycline (other tautomer) and insulin glargine match neither way; semaglutide's block matches 3 unnamed records. The exact match can be the wrong record: glimepiride and minoxidil hit unnamed, mechanism-less entries (GLIMEPIRIDE CHEMBL1481 shows up only by connectivity; MINOXIDIL CHEMBL802 and DOXYCYCLINE, parent CHEMBL1433, only by `pref_name__iexact`). Fluticasone CHEMBL1201396 has no mechanism; ChEMBL lists them on its esters |
| RCSB: ligand code | InChIKey → PDB ligand code | search API, `service: "text_chem"`, attribute `rcsb_chem_comp_descriptor.InChIKey`, `return_type: "mol_definition"` | returns exactly STI, CFF, AIN, TYL. `service: "text"` returns unrelated codes |
| RCSB: stereo fallback | SMILES → candidates whose InChIKey connectivity block matches | `service: "chemical"`, `match_type: "graph-relaxed-stereo"`, then `data.rcsb.org/rest/v1/core/chemcomp/{code}` | ibuprofen → IBP, IZP; donepezil → E20; warfarin → RWF, SWF |
| RCSB: complex | entries with the ligand **and** the target | entries containing the ligand (`rcsb_nonpolymer_entity_container_identifiers.nonpolymer_comp_id`), then one GraphQL request (`data.rcsb.org/graphql`, `entries(entry_ids: …)`) for title, resolution and, per protein entity, chains, gene names and each source organism with its taxonomy lineage (`taxonomy_lineage { name }`); keep the entries with an entity whose depositor gene name or UniProt primary gene name is a target gene, and for a viral target only when the source that carries the gene has the target's species in its lineage | match the **gene name**, not the UniProt accession: many reference structures are non-human (COX from sheep and mouse, 1IEP is mouse ABL). Viral gene names are generic (`pol`, `NA`), so viral targets also need the species (§5.3, checked 2026-10-12). Gene names match ignoring case (mouse `Abl1`), and `gag-pol` counts as `pol`, since many HIV-1 structures name only the polyprotein (§5.3, #83). The search-side AND with `rcsb_entity_source_organism.rcsb_gene_name.value` misses entries whose depositor left the gene empty: STI AND ABL1 returns 11 entries without 1IEP or 3MSS (checked 2026-10-11), and UniProt gene names are not searchable (HTTP 400). UniProt synonyms are left out because they can name another protein (COX2 is also a synonym of MT-CO2) |
| openFDA | label text for the knowledge base | `/drug/label.json?search=openfda.generic_name:"{name}"&sort=set_id:asc&limit=100&skip={n}`, paged until `meta.results.total` (verified 2026-10-11) | 262,895 labels, 1.77 GB zipped. The scope list keeps the corpus small, so no bulk download. The phrase search also finds combination products: on 2026-10-11 ibuprofen returned 1147 labels (970 single-ingredient), acetaminophen 3284 (999), all with unique `set_id`s. Sorting on `set_id` keeps the pages from overlapping; `limit` above 1000 or `skip` above 25000 answers HTTP 400. A name with no labels answers 404 `NOT_FOUND` (paracetamol: US labels say acetaminophen). Some generic names are abbreviated: 6 hydrocodone + acetaminophen labels say `HYDROCODONE/APAP`, so a search for acetaminophen misses them. The optional API key goes in the `X-Api-Key` header (a wrong key answers 403 `API_KEY_INVALID`, so the header is read); the `api_key` query parameter would put it into the cached URL and the logs |
| RDKit | 3D fallback (ETKDG + MMFF), bond orders for PDB ligands | local | only where PubChem has no data |

---

## 4. Architecture: answers come from the local store

```
           build time (python -m molecula.ingest …)                       run time
 PubChem ─┐                                                     ┌─ FastAPI ──> Next.js
 ChEMBL  ─┼─> ingest steps ──> data/build/molecula.db (SQLite)──┤
 RCSB    ─┤                    data/build/structures/           └─ MCP server ──> LangChain agent
 openFDA ─┘                    data/build/index/ (vectors + BM25), data/build/models/
```

- **One service layer** (`backend/src/molecula/services/`). FastAPI routes, agent tools and the MCP server are thin wrappers around the same functions.
- **The store is the supported set.** Services read only the store; a drug that isn't in it is answered as "not supported", and the UI lists what is. Sources are called only by the ingest steps (including the label update, §5.6), through the rate-limited client with retries on 429/503, and every stored row records `source` and `fetched_at`.
- **No live fallback** (decided in #30). For a drug outside the scope a live lookup would only bring properties and 3D, with no label, no targets and no reviewed complex. It can also answer about the wrong drug: PubChem maps "Vicodin" (hydrocodone + acetaminophen) to acetaminophen's CID (checked 2026-10-11). Complexes outside the reviewed hero set would be risky too, because an unreviewed complex can be scientifically wrong (ibuprofen bound to albumin is not its mechanism).
- **Salt and brand names** resolve through the stored synonyms (scope name, scope aliases, top PubChem synonyms) and, failing that, the name without salt and hydrate words ("imatinib mesylate" → imatinib).
- **`OFFLINE=1`** stops the ingest steps from calling a source. Evals always run this way.

**How a fresh clone gets the store** (decided in #35). `data/build/` is gitignored (#34), and building it takes minutes and can hit NCBI's block (§3), so the built store is published as a GitHub release asset and downloaded on the first start.

- `python -m molecula.ingest export` (#117) writes `molecula-store.tar.gz` and `manifest.json` to `data/build/export/`. The archive holds `molecula.db`, `structures/` and `index/` and nothing else from `data/build/`: model weights, eval output and review notes stay local, and so does `data/runtime/` (#40). Run it with the backend stopped and no ingest step running: Chroma writes to `chroma.sqlite3` whenever it opens the index, so a backend starting during the export could change a file while it is packed.
- The archive's `molecula.db` keeps the `http_cache` table but none of its rows, so no raw API response is published, and an ingest step run on a downloaded store works, fetching everything again (~670 PubChem requests for the compounds).
- The manifest records the schema version, the build date, `last_run`, the row count of every table, the embedding model the index was built with, and the archive's size and SHA-256. `last_run` is the oldest `fetched_at` of the stored labels: the label update (#25) asks openFDA for changes since then, and starting from the newest fetch would miss a label that changed after an earlier one was fetched.
- The release is tagged `store-YYYY-MM-DD`, and the settings pin the tag as `STORE_RELEASE`, so code and data versions match. `python -m molecula.ingest fetch` downloads the pinned release, checks the SHA-256 and the schema version and unpacks it into `data/build/`; Docker runs it when the store is missing (#118). The first release is #119.
- **The embedding model comes from Hugging Face, not from the release** (decided 2026-10-13 in #35). Each release asset must be under 2 GiB ([GitHub](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)), and bge-m3's weights alone are one 2,271,145,830-byte file. `fetch` downloads `LOCAL_EMBEDDING_MODEL` into `data/build/models/`, pinned to a revision and checked by hash, and with `OFFLINE=1` and no model it exits with a message, as it does without a store (#118). The manifest names the model because the index refuses queries from another one. Splitting the weights into parts would work but adds joining code to `fetch`; fp16 weights (~1.1 GB) would fit, but they change the vectors, so the index would have to be rebuilt and its recall measured again.
- Not the other options from #34: an ingest on every clone (minutes, NCBI's block), committing the conformers only (no database), or committing the store (growing binary data in the git history). Git LFS counts every clone against its bandwidth quota.
- **First export** (2026-10-13, the store from §5, 3.5 s): a 79 MB archive (78,950,603 bytes), 149.9 MB unpacked: `molecula.db` 13.8 MB (2.0 GB with the HTTP cache), the bge-m3 index 135.1 MB, conformers 0.9 MB. Rows: 134 compounds, 4,343 synonyms, 190 targets, 104 ligand codes, 317 complex candidates, 156 labels, 3,126 label sections, 1 disclaimer.

---

## 5. Pipeline

### 5.1 Scope list (`data/scope.yaml`)

100–150 drugs: commonly prescribed, common OTC, and the hero set. Each entry has a generic name and optional aliases (`Ibuflam: ibuprofen`, `Tylenol: acetaminophen`, `paracetamol: acetaminophen`). A fixed list bounds the corpus, the eval set and the API calls.

### 5.2 Compounds (`ingest compounds`)

name → CID → parent CID → properties, InChIKey, SMILES → 3D SDF (RDKit fallback) → top 30 synonyms for the name layer and for BM25. Peptides such as insulin and semaglutide are marked "no small-molecule 3D". `compound.name` is the scope name; PubChem's title is sometimes a systematic name (glimepiride, doxycycline). Only a complete run (no failures, nothing left unattempted) prunes: it deletes the compounds it didn't store, with their synonyms, targets and conformer files, and any conformer file without a compound, and lists them in its summary.

When PubChem has no conformer, RDKit generates one (ETKDG with a fixed seed, then MMFF) for molecules up to 100 heavy atoms. PubChem skips flexible small molecules too, e.g. ritonavir (50 heavy atoms, 18 rotatable bonds). Larger molecules get `has_3d = false`. Conformers are written to `data/build/structures/compounds/{cid}.sdf`.

Tables: `compound(cid, name, inchikey, smiles, formula, mw, xlogp, tpsa, hbd, hba, rotb, heavy_atoms, has_3d, conformer_source, source, fetched_at)`, `synonym(alias, cid, kind)` with `kind` one of `name`, `alias` (from the scope) or `pubchem`.

Displayed properties come from PubChem (citable). RDKit's Crippen logP and acceptor counts differ by design (imatinib: Crippen 4.59 vs XLogP3 3.5).

### 5.3 Targets and complexes (`ingest targets`)

Runs after `ingest compounds`, for every compound in the store.

1. InChIKey → ChEMBL molecule → parent ID → mechanisms → targets with UniProt accessions and gene symbols. The molecule is looked up by exact InChIKey, then by connectivity block, then by `pref_name`; the next lookup is tried while none of the named molecules has mechanisms. Unnamed records are never picked. This matters for glimepiride (the exact match is an unnamed record), tramadol (the exact match is "(R,R)-TRAMADOL" without mechanisms; the racemate TRAMADOL has them), doxycycline (ChEMBL draws another tautomer, so only the name finds it) and minoxidil, semaglutide and insulin glargine (found by name). Mechanisms are de-duplicated by target, since ChEMBL repeats them across records and salts (ibuprofen, acetazolamide).
2. InChIKey → PDB ligand code(s): exact first; connectivity fallback (stereo-relaxed SMILES search, kept when the ligand's InChIKey shares the connectivity block) only when there is no exact match.
3. For each target and ligand code: entries with the ligand, kept when a protein entity comes from one of the target's genes (depositor or UniProt primary gene name, any organism) → candidate entries with the target's chains. For a **viral target** (the ChEMBL organism contains "virus") the source organism that carries the gene must also have the target's species in its NCBI taxonomy lineage, ignoring case. The species is the ChEMBL organism without the strain in parentheses: "Influenza A virus (A/Puerto Rico/8/1934(H1N1))" → "Influenza A virus". A type in the parentheses stays, because NCBI numbers the species: "Herpes simplex virus (type 1 / strain 17)" → "Herpes simplex virus 1". The gene name `gag-pol` counts as `pol` (#83).
4. Rank per target: human proteins first, then resolution (`rcsb_entry_info.resolution_combined`), entries without one last.
5. A person reviews the candidates in `data/build/complex_candidates.md` and writes the chosen entry to `data/hero_set.yaml`: `pdb, ligand_code, chain, target, organism, note`.

Tables (schema version 3), each row with `source` and `fetched_at`:

- `target(cid, target_chembl_id, molecule_chembl_id, name, target_type, organism, mechanism, action_type, accessions, gene_symbols)`. `molecule_chembl_id` is the record that carries the mechanism (often a salt); `accessions` and `gene_symbols` are JSON arrays.
- `ligand_code(cid, code, matched_on)` with `matched_on` either `inchikey` or `connectivity`.
- `complex_candidate(cid, target_chembl_id, rank, pdb_id, ligand_code, title, resolution, organism, taxonomy_id, chains)`; `chains` is a JSON array.

A drug that fails is reported and skipped; the run stops when a source stops answering. Re-running is served from the HTTP cache and leaves the rows untouched.

**Prodrugs** are bound in their active form, which the automatic search can't find: oseltamivir → G39 (oseltamivir carboxylate), tamoxifen → OHT (4-hydroxytamoxifen), aspirin → salicylate plus an acetylated serine. These are entered in `hero_set.yaml` by hand.

**Gene names cross species, except for viruses.** The match is on gene name in any organism, so mouse ABL1 (1IEP) and sheep COX-1 count. Viral gene names are generic: HIV-1 protease and integrase are both `pol`, so before the species rule (#69) raltegravir's candidates were foamy virus and STLV-1 integrase. Checked live on 2026-10-12 before choosing the rule:

- **UniProt accession:** none of the gene-matched entities for RLT, DLU, RIT or ZMR carries the ChEMBL target's accession (Q7ZJM1, Q72874, B4URF0, P03468, …). HIV-1 and influenza structures use other isolates' entries (P12497, P03367, P03472, …), so this rule would empty ritonavir and zanamivir.
- **ChEMBL `tax_id` in the entity's lineage:** right for HIV-1 (11676), but ChEMBL gives the influenza neuraminidase targets strain IDs (211044, 382835, 518987, 343983, even for the one named plain "Influenza A virus"); none of zanamivir's 23 entities has them, so this rule would empty zanamivir too.
- **Species name in the lineage (chosen):** RCSB's `taxonomy_lineage` lists every ancestor name with synonyms, so a strain's lineage holds its species ("Influenza A virus" above A/tern/Australia/G70C/1975). Raltegravir: none of the 7 RLT entries has HIV-1 integrase (3OYA, 3L2V foamy virus; 7OUG STLV-1; the others influenza PA and a transposase), so it has **no candidate** and its hero complex needs a hand entry or none. Dolutegravir keeps its 4 HIV-1 entries and drops foamy virus (3S3M/N/O) and SIV (6RWN). Ritonavir keeps all 6 HIV-1 protease entries. Zanamivir's influenza A targets keep 18 of 23 (best still 6HCX) and its influenza B targets 3 (1A4G, 4CPZ, 4CPN); 7XVV (Wuhan spiny eel influenza virus) and 7FGC ("unidentified influenza virus") drop out.

**`gag-pol` counts as `pol`** (#83). HIV-1 makes protease, reverse transcriptase and integrase from one Gag-Pol polyprotein, and many structures name only that gene, by the depositor or through UniProt, so they never matched ChEMBL's `pol`. Checked live on 2026-10-12 on every HIV-1 drug with a ligand code (DLU 20 entries, RLT 7, RIT 19), with the species rule kept:

- **Dolutegravir** goes from 4 to 16 HIV-1 entries. The 12 new ones are intasomes: 9C9M (2.01 Å, now rank 1), 6U8Q, and 8FN7…8FNP, which fuse human LAP2 to integrase; the organism comes from the HIV-1 part, which carries the gene. Foamy virus (3S3M/N/O) and SIV (6RWN) stay out.
- **Ritonavir** goes from 6 to 9: 1HXW (the wild-type protease with ritonavir, A-84538), 1RL8 and 1SH9, all HIV-1 protease. 3NDX stays rank 1.
- **Raltegravir** stays at 0: its only `pol` entries are foamy virus and STLV-1.
- Splitting every hyphenated gene name into its parts gave the same entries here, but would also let `gag-pol` match a `gag` target and influenza `PB1-F2` match `PB1`, so only `gag-pol` → `pol` is applied. Rerunning `ingest targets` offline on a copy of the store changed nothing else: 69 compounds with candidates, 302 → 317 candidate rows.

**A type in the strain stays in the species.** RCSB's lineage for 2KI5 (HSV-1 thymidine kinase with acyclovir, taxon 10298) names the species "Simplexvirus humanalpha1" with synonyms such as "Human alphaherpesvirus 1", "Herpes simplex virus 1" and "Herpes simplex virus type 1", but never plain "Herpes simplex virus", which the species rule used to make of ChEMBL's "Herpes simplex virus (type 1 / strain 17)". It has no effect on candidates today: ChEMBL's HSV-1 DNA polymerase target (acyclovir, valacyclovir) has no gene symbol, and no AC2 or TXC entry has the polymerase.

Candidates from the first full run (2026-10-11; best first, organism given when not human; each still needs review):

| Drug | Target | Candidate entries | Spike table |
|---|---|---|---|
| imatinib | ABL1 | 3PYY, 6NPV, 6NPE, 7N9G, 6NPU, 2HYY, then 7 mouse incl. 1IEP (checked: contacts match the literature) | 1IEP, 2HYY |
| | KIT | 1T46, 8S16 | — |
| dasatinib | ABL1 | 7N9G, 2GQG, 4XEY | 2GQG |
| | EPHA2; SRC family | 5I9Y; 3G5D (chicken), 2ZVA (mouse), 3QLG (chicken) | — |
| caffeine | adenosine receptors | 5MZP, 3RFM (both A2A) | 3RFM, 5MZP |
| atorvastatin | HMG-CoA reductase | 1HWK, 8PKN | 1HWK |
| ibuprofen | COX | 4PH9 (mouse), 8ET0 (mouse), 1EQG (sheep), 4RS0 (mouse) | 4PH9 |
| celecoxib | COX-2 | 3LN1 (mouse), 5JW1 (mouse) | 3LN1 |
| diclofenac | COX | 3N8Y (sheep), 1PXX (mouse) | 3N8Y |
| naproxen | COX | 3NT1 (mouse) | 3NT1 |
| methotrexate | DHFR | 3EIG, 1U72, 1DLS, 3IX9 (S. pneumoniae), 1U70 (mouse) | 1U72, 1DLS |
| donepezil | acetylcholinesterase | 6O4W, 4EY7, 7E3H, 1EVE (Torpedo) | 4EY7 |
| gefitinib | EGFR | 4I22, 4WKQ, 3UG2, 2ITZ, 2ITO, 2ITY | 4WKQ |
| erlotinib | EGFR | 1M17, 4HJO | 1M17 |
| sitagliptin | DPP-4 | 1X70, 4FFW (rat) | 1X70 |
| lisinopril | ACE | 1O86, 2C6N | 1O86 |
| acetazolamide | carbonic anhydrases | CA2: 14, best 3HS4 (1.1 Å); CA1: 1AZM, 3W6H; CA12: 1JD0; CA4: 5JN8 | many |
| oseltamivir (G39) | neuraminidase | none: prodrug, hand entry | 17 entries |
| zanamivir | neuraminidase | influenza A: 18 entries, best 6HCX (1.3 Å); influenza B: 1A4G, 4CPZ, 4CPN (#69) | 11 entries |
| ritonavir | HIV-1 protease | 3NDX, 3NDW, 1HXW, 4EYR, 4NJV, 1RL8, 1N49, 2B60, 1SH9 (1HXW, 1RL8, 1SH9 name the gene `gag-pol`, #83) | — |
| | CYP3A | 3NXU, 5VCE, 5VC0, 5VEU, 38FV | 3NXU |
| warfarin | VKORC1 | 6WV3, 6WV4 (human VKOR in a GFP fusion; the organism comes from the source that carries the gene, #68) | 6WV3 |
| tamoxifen (OHT) | ESR1 | none: prodrug, hand entry | 4Q50 |
| sildenafil | PDE5A | 1TBF, 1UDT, 2H42, 3JWQ, 10OZ (cow) | throttled |
| dolutegravir | HIV-1 integrase | 16 HIV-1 intasome entries, best 9C9M (2.01 Å); 12 of them name the gene `gag-pol` (#83) | — |
| raltegravir | HIV-1 integrase | none: no PDB entry has RLT bound to HIV-1 integrase; the first run's 3OYA, 7OUG, 3L2V were foamy virus and STLV-1 (#69) | throttled |
| metformin | mitochondrial complex I | 6 pig respirasome or complex I entries, best 8ZSQ (2.86 Å) | molecule-only |

Molecule-only (no candidate): paracetamol, cetirizine, omeprazole. Of the 134 compounds, 132 have targets (not fluticasone, whose mechanisms ChEMBL lists on its esters, nor guaifenesin, whose only mechanism is "Unknown" without a target) and 70 had candidates in the first run; with the viral species rule raltegravir has none, so 69.

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
- **Safety at index time:** `overdosage` was left out until #92 and is now indexed with `sensitive=true`: 105 of its 127 sections say how an overdose is treated (poison control, charcoal, dialysis, antidotes) and 91 how it shows, which matters offline in an emergency; 23 also state a lethal amount, so answers must put emergency help first and never hand a lethal dose to someone seeking harm (#17). `dosing` is indexed with `sensitive=true`, so general label dosing can be cited but never turned into personal advice.
- `*_table` HTML fields are dropped; the plain-text versions are kept.
- Chunks (`ingest index`, #87): each section on its own, then recursively to 500 tokens with 50 overlap, counted with the `BAAI/bge-small-en-v1.5` tokenizer for every embedding model, so models are compared on the same chunks and no chunk is longer than a BERT-sized model reads (512 tokens). The embedding model itself is `BAAI/bge-m3` since #88 ([embeddings](decisions/embeddings.md)). Whitespace is collapsed. Metadata: `{cid, substance, brand, product_type, section, section_group, sensitive, set_id, effective_time, url}`; IDs `{set_id}:{section}:{n}`.
- **Repeated text is indexed once within a section group.** Measured on 2026-10-12 over the 156 stored labels: `clinical_pharmacology` contains `mechanism_of_action` on 111 of 115 Rx labels that have both, and `pharmacodynamics` on 87 of 89; that text is cut out of `clinical_pharmacology` and kept under the specific section, and a leftover under 10 tokens (the heading) is dropped. OTC `warnings` repeats `do_not_use`, `stop_use`, `ask_doctor` and `when_using` on most Drug Facts labels, but those are another group (`otc_consumer`), so both stay: retrieval filters on the group.
- Vectors in ChromaDB (`data/build/index/chroma/`, one collection, cosine), rebuilt from scratch in an emptied folder: Chroma keeps a deleted collection's files, and a rebuild in place grew the index from 74.8 to 96.7 MB. The collection records the embedding model, and a query with another model is refused, because vectors of two models don't compare. Model weights are saved in `data/build/models/` on the first build, so later builds and the app load them with `OFFLINE=1`.

**Corpus estimate:** a canonical Rx label is 40–170k characters (measured), an OTC label 3–5k. For 120 drugs that is ~8–10M characters ≈ 2–2.5M tokens ≈ 4–5k chunks. Local embeddings handle this on a CPU in minutes. The first full run measured less (below). The first index build (2026-10-12, `bge-small-en-v1.5` on CPU): 3,813 chunks from 156 labels in 105–118 s, a 74.8 MB index, and 129 MB of model files. With the #92 sections: 7,012 chunks in 182 s and a 106.9 MB index (with bge-m3 since #88: 135.1 MB, 2.3 GB of model files); pharmacokinetics is indexed once, under its own name (465 chunks), and `clinical_pharmacology` keeps 107.

**How `ingest labels` works.** It runs after `ingest compounds`, for every compound in the store.

1. **Search name:** the compound's name, which `data/scope.yaml` keeps as the US generic ("acetaminophen", with "paracetamol" as an alias). Aliases are not searched: they are brands or non-US names, and openFDA's `generic_name` holds neither. A 404 means the drug has no US label.
2. **Single ingredient of this drug:** a label counts when it has exactly one `substance_name` and that substance, without salt and hydrate words (the list in `services/compounds.py`), is the compound ("IMATINIB MESYLATE" → imatinib). The phrase search also returns combinations and other drugs, so this filter runs on the whole result. When a product type has no such label, another form of the drug counts: a substance that starts with the compound's name ("FLUTICASONE PROPIONATE").
3. **Most common route:** of those labels, only the ones on the route most of them share are kept, so the canonical label is the drug's usual form (ibuprofen Rx: 233 oral labels, 4 intravenous). A label's `openfda.route` list counts as one value, sorted ("INTRAMUSCULAR,INTRAVENOUS"). Equally common routes go by name; a label without a route counts as a route of its own that loses a tie. In the first run no candidate lacked a route and no two routes tied.
4. **Canonical label**, per product type (`HUMAN PRESCRIPTION DRUG` → `rx`, `HUMAN OTC DRUG` → `otc`): has `mechanism_of_action`, then the brand's own label, then the latest `effective_time`, then the most kept sections, then the lowest `set_id`. **The brand's own label** is one filed under an NDA or BLA (`openfda.application_number`; generics are ANDA, OTC monograph products `M…`, e.g. M013) whose `brand_name` differs from its `generic_name`. The name check leaves out authorized generics and biosimilars, which are filed the same way (on 2026-10-12, 1 of 234 single-ingredient ibuprofen Rx labels and 2 of 22 imatinib labels qualified).
5. **Sections:** only those in the table below are stored; several strings of one section are joined with a blank line.

| `section_group` | Label sections | `sensitive` |
|---|---|---|
| `pharmacology` | `mechanism_of_action`, `clinical_pharmacology`, `pharmacodynamics`, `pharmacokinetics`, `pharmacogenomics`, `microbiology` | |
| `indications` | `indications_and_usage` | |
| `dosing` | `dosage_and_administration` | yes |
| `warnings` | `boxed_warning`, `warnings_and_cautions`, `warnings`, `precautions`, `general_precautions`, `laboratory_tests` (the last three from older Rx labels) | |
| `contraindications` | `contraindications` | |
| `interactions` | `drug_interactions`, `drug_and_or_laboratory_test_interactions` | |
| `adverse_reactions` | `adverse_reactions` | |
| `specific_populations` | `use_in_specific_populations`, `pregnancy`, `teratogenic_effects`, `nonteratogenic_effects`, `labor_and_delivery`, `nursing_mothers`, `pediatric_use`, `geriatric_use`, OTC `pregnancy_or_breast_feeding` | yes |
| `patient_information` | `information_for_patients`, `spl_medguide`, `spl_patient_package_insert`, `patient_medication_information`, `instructions_for_use` | yes |
| `product` | `description`, `dosage_forms_and_strengths`, `how_supplied`, `storage_and_handling`, OTC `inactive_ingredient` | |
| `abuse_dependence` | `drug_abuse_and_dependence`, `abuse`, `dependence`, `controlled_substance` | yes |
| `clinical_studies` | `clinical_studies` | |
| `overdosage` | `overdosage` | yes |
| `otc_consumer` | `do_not_use`, `stop_use`, `ask_doctor`, `ask_doctor_or_pharmacist`, `when_using`, `purpose`, `active_ingredient`, `keep_out_of_reach_of_children`, `other_safety_information` | |

Never stored: the preclinical sections (`nonclinical_toxicology`, `carcinogenesis_and_mutagenesis_and_impairment_of_fertility`, `animal_pharmacology_and_or_toxicology`), `references`, `recent_major_changes`, `spl_unclassified_section`, OTC `questions`, and every `*_table` field. The groups after `adverse_reactions` came with #92: 5.66M → 11.25M stored characters, no canonical label changed.

Tables (schema version 5; version 5 widened the `section_group` check for #92):

- `label(set_id, cid, substance, brand, product_type, effective_time, url, source, fetched_at)`, one row per (`cid`, `product_type`); `product_type` is `rx` or `otc`, `substance` the label's own (often a salt), `url` the DailyMed page `https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}`.
- `label_section(set_id, section, section_group, text, sensitive)`.
- `source_disclaimer(source, text, fetched_at)`: openFDA's `meta.disclaimer`, stored once for the UI.

A pruned compound takes its labels and sections with it (`ON DELETE CASCADE`). A drug that fails is reported and skipped; the run stops when openFDA stops answering. Re-running is served from the HTTP cache and leaves the rows untouched.

**First full run (2026-10-12, with an API key):** 134 compounds, 361 requests, 4 min 24 s. Later runs, including the one with the route rule, made no request and took 5 s.

- **129 compounds have an Rx label, 27 an OTC label.** OTC only: aspirin, dextromethorphan, fexofenadine, pseudoephedrine. **No US label: metamizole** (not approved in the US; 404).
- **5,662,726 characters** in 1,404 sections: Rx 5,588,740 (941 to 108,933 per label, mean 43k), OTC 73,986 (499 to 5,742). By group: warnings 1.59M, pharmacology 1.42M, adverse reactions 1.17M, dosing 0.68M, interactions 0.49M, indications 0.21M, contraindications 0.08M, OTC consumer 0.02M. No `overdosage` or `*_table` section is stored. That is a bit over half the estimate above, because many canonical labels are short PLR labels and most drugs have no OTC label.
- **The HTTP cache is large.** The 361 openFDA pages are 1.97 GB of response bodies; the store grew from 3.0 MB to 1.98 GB. Only the ~5.7 MB of kept sections is needed after the run.
- **Another form used:** fluticasone (propionate Rx, furoate OTC). Escitalopram oxalate matches directly since "oxalate" joined the salt words.
- **Route first changed 23 of 156 picks.** Without it the mechanism and brand rules picked niche products: ibuprofen → Caldolor (IV, the only single-ingredient ibuprofen Rx label with a mechanism section), dexamethasone → Ozurdex (implant), cetirizine → Zerviate (eye drops), clotrimazole → Clotic (ear drops). Now these are oral or topical, and the other changes go the same way (Aloprim → oral allopurinol, Gablofen → oral baclofen, Nexterone → oral amiodarone). Ibuprofen's oral pick has no `mechanism_of_action`; its mechanism is in `clinical_pharmacology`.
- **The usual route isn't always the familiar one.** Acetaminophen's single-ingredient Rx labels are all injections; hydrocortisone's most common Rx route is topical (Proctozone-HC); naloxone's is injection. A few Rx labels are OTC Drug Facts filed as prescription: guaifenesin (941 characters), loratadine (944), diphenhydramine (6,628).

Canonical labels (Rx / OTC, with route; generic labels are named by their brand field):

| Drug | Rx | OTC |
|---|---|---|
| acetaminophen | Acetaminophen (intravenous) | Tylenol 8 HR Arthritis Pain (oral) |
| aspirin | — | Low Dose Aspirin (oral) |
| atorvastatin | Lipitor (oral) | — |
| cetirizine | Cetirizine Hydrochloride (oral) | Zyrtec Allergy (oral) |
| clotrimazole | Clotrimazole (topical) | Clotrimazole (topical) |
| dexamethasone | Hemady (oral) | Seacall Dexamethasone Ointment (topical) |
| ibuprofen | Ibuprofen tablets (oral) | Advil Menstrual Pain (oral) |
| imatinib | Gleevec (oral) | — |
| metamizole | — | — |

The run logs the chosen labels of every drug with their `set_id` and size. Why labels are chosen this way: [decisions/drug-labels.md](decisions/drug-labels.md).

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
