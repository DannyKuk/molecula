# Complex candidates

> **Answer:** ChEMBL mechanisms give a drug's targets, the drug's InChIKey gives its PDB ligand codes, and an entry counts as a candidate when the ligand is bound to a protein whose **gene name** is a target gene, in any organism, except that a **viral** target also needs its own virus species. Candidates rank human first, then by resolution. A person picks the hero complex from them.

## Question

The app shows a drug bound to its target in 3D. For each drug in the store, which PDB entries show it bound to the protein it acts on, and which one comes first? The answer has to come from the local store, be checkable by a person, and never show the drug on the wrong protein as if it were the mechanism.

## What we tried

- **Targets:** InChIKey → ChEMBL molecule → parent → mechanisms → targets with UniProt accessions and gene symbols.
- **Ligand codes:** the exact InChIKey in RCSB's chem-comp search, and when that finds nothing, a stereo-relaxed SMILES search kept only where the InChIKey's first 14 characters (the connectivity) match.
- **Entries:** every entry with the ligand code, then one GraphQL request for their protein entities. Three ways to tie an entity to a target: the UniProt accession, a gene-name filter in the search, and gene names compared in our code.
- **Viral targets** (#69), checked live on 2026-10-12: the UniProt accession, the ChEMBL `tax_id` in the entity's taxonomy lineage, and the species name in that lineage.

## Result

| Way to match an entity to the target | ABL1 + imatinib (STI) | Viral targets |
|---|---|---|
| UniProt accession | misses 1IEP (mouse ABL1) and every sheep or mouse COX | 0 entities for raltegravir, dolutegravir, ritonavir or zanamivir |
| Gene filter in the search (`STI AND ABL1`) | 11 entries, without 1IEP or 3MSS (the depositor left the gene empty) | — |
| **Gene name, depositor or UniProt, in our code** | **13 entries, 1IEP included** | wrong virus: `pol` and `NA` are shared |

Viral targets, before → after the species rule:

| Drug | Target | Before | After |
|---|---|---|---|
| raltegravir | HIV-1 integrase | 3OYA, 3L2V (foamy virus), 7OUG (STLV-1) | **none**: no PDB entry has RLT on HIV-1 integrase |
| dolutegravir | HIV-1 integrase | 8 (3 foamy virus, 1 SIV, 4 HIV-1) | 4 HIV-1: 8W34, 8W09, 8W2R, 6VDK |
| ritonavir | HIV-1 protease | 6 HIV-1, best 3NDX | the same 6 |
| zanamivir | influenza A neuraminidase (2 targets) | 23 each, influenza A and B mixed | 18, best 6HCX |
| zanamivir | influenza B neuraminidase (2 targets) | 23 each | 3: 1A4G, 4CPZ, 4CPN |
| oseltamivir, tenofovir, acyclovir, valacyclovir | influenza, HIV-1, HBV, HSV-1 | none | none (prodrug, or no gene symbol) |

The full run: 132 of 134 compounds have targets; 70 had candidates, 69 with the species rule. The candidate table per drug is in [`docs/data-plan.md` §5.3](../data-plan.md#53-targets-and-complexes-ingest-targets).

## What it shows

- **The gene name is what crosses species.** Many reference structures are not human: 1IEP is mouse ABL1, the COX structures come from sheep and mouse. UniProt accessions are per species, and the searchable gene field is only the depositor's, which 1IEP leaves empty. UniProt's gene names are only in the data API, so the match runs in our code.
- **Viral gene names don't identify the protein.** HIV-1 protease and integrase are both `pol`, as are foamy virus and STLV-1 integrase. The accession and the ChEMBL `tax_id` both fail, because structures use other isolates' accessions and ChEMBL gives influenza targets strain IDs (211044, 382835, …) that no zanamivir entry carries. The species name ("Influenza A virus" from "Influenza A virus (A/Puerto Rico/8/1934(H1N1))") is in every strain's lineage, so it works.

## Decided along the way

- **The organism comes from the source that carries the gene** (#68). 6WV3 fuses human VKORC1 to GFP, which is listed first; it used to rank as jellyfish. With the fix, loperamide's 9PY4 and losartan's 9EAI moved to rank 1.
- **Human first, then resolution**, entries without a resolution last. Ties keep the PDB ID order, so a rerun gives the same ranks.
- **A person picks the hero complex** (#6) into `data/hero_set.yaml`. Many structures of a drug show it on a transport protein rather than its target (ibuprofen and warfarin on albumin), a gene-matched entry can still be the wrong protein, and prodrugs are bound in their active form, which the InChIKey can't find: oseltamivir → G39, tamoxifen → OHT. These are entered by hand.
- **No UniProt synonyms.** They can name another protein: COX2 is also a synonym of MT-CO2.

## Limits

- "Is a virus" is the word "virus" in ChEMBL's organism name. It holds for every target in the store, but a renamed taxon could slip through.
- HIV-1 intasome entries that only name the gene `gag-pol` (6U8Q, 8FN7…8FNP, 9C9M for dolutegravir) never matched ChEMBL's `pol`.
- "Herpes simplex virus (type 1 / strain 17)" gives a species name NCBI doesn't use. That has no effect now, because the target has no gene symbol.

## Reproduce

```bash
cd backend
uv run python -m molecula.ingest targets            # → data/build/complex_candidates.md
uv run pytest tests/sources/test_rcsb.py tests/ingest/test_targets.py
# Entries with raltegravir (RLT), and a source's lineage:
curl -s https://search.rcsb.org/rcsbsearch/v2/query -H 'Content-Type: application/json' -d '{"query":{"type":"terminal","service":"text","parameters":{"attribute":"rcsb_nonpolymer_entity_container_identifiers.nonpolymer_comp_id","operator":"exact_match","value":"RLT"}},"return_type":"entry","request_options":{"return_all_hits":true}}'
curl -s https://data.rcsb.org/graphql -H 'Content-Type: application/json' -d '{"query":"{ entries(entry_ids: [\"3OYA\", \"8W34\"]) { rcsb_id polymer_entities { rcsb_entity_source_organism { scientific_name taxonomy_lineage { name } } } } }"}'
```
