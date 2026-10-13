# Hero complexes

> **Answer:** all 73 drugs with a usable structure get a reviewed complex in `data/hero_set.yaml`: the drug's therapeutic target, then a human protein, then wild type, then resolution. A stand-in (a related virus, a second target, a debated site) is shown with a caption; an animal version of the human protein is shown without one. The 37 cleanest entries, all ≤ 2.8 Å, are the showcase. Each entry names the exact ligand copy, because the top candidate is often the wrong one.

## Question

Which PDB entry shows each drug bound to the protein it acts on, and which copy of the ligand in it? The 3D view only draws entries from this file (#7), so a wrong pick shows a wrong mechanism.

## What we tried

- **Candidates:** the ranked list from `ingest targets` (`data/build/complex_candidates.md`, [complex candidates](complex-candidates.md)), 69 drugs. Four more by hand: the prodrugs oseltamivir (G39) and tamoxifen (OHT), aspirin (salicylate, SAL) and raltegravir, which has no HIV-1 candidate.
- **Every candidate on the therapeutic target**, checked on 2026-10-12 against the RCSB Data API: ligand completeness, RSCC and "subject of investigation" from the validation report, the residues within 4 Å (`rcsb_target_neighbors`), mutations and the primary citation. Mean ligand B-factors came from the ModelServer.
- **The pocket**, by comparing the residues within 4 Å with the residues known for that site (for 1IEP: Thr315, Met318, Glu286, Asp381, Ile360, His361).
- **The chosen entries again**, on 2026-10-13: each ligand copy exists, is complete, and its chain has the most polymer contacts.

## Result

| | Entries |
|---|---|
| In `hero_set.yaml` | 73 |
| Human protein | 52 |
| ≤ 2.8 Å / 2.8–3.5 Å / > 3.5 Å | 44 / 25 / 4 (ezetimibe 3.58, sertraline 3.53, nicotine 3.7, memantine 3.96) |
| Cryo-EM | 27 |
| Showcase | 37, all ≤ 2.8 Å |
| With a caption | 10 |
| Molecule only | none |

The top-ranked candidate was often not the right one:

| Drug | Top candidate | Problem | Chosen |
|---|---|---|---|
| levothyroxine | 4LNX | T4 at a surface second site; T3 fills the hormone pocket | 1Y0X |
| methotrexate | 3EIG | F31R/Q35E resistant mutant | 1U72 |
| gefitinib | 4I22 | T790M/L858R resistant mutant | 4WKQ |
| estradiol | ranks 1–5 | Y537S or Y364S mutants | 2YJA |
| sildenafil, tadalafil | 1TBF, 1XOZ | PDE5/PDE4 chimeras (17–18 substitutions) | 1UDT, 1UDU |
| ritonavir | 3NDX | 5-mutant protease | 1HXW |
| imatinib, dasatinib | 3PYY, 7N9G | a second drug in the entry | 2HYY, 2GQG |
| zanamivir | 6HCX | avian N9; ChEMBL's target is an H1N1 N1 | 3B7E |
| aspirin (the issue's example) | 1PTH | bromoacetyl-Ser530 from an aspirin analog, not acetyl | 3N8Y chain B |

## What it shows

- **The ranking can't be the pick.** Human-first then resolution puts resistant mutants, chimeras and entries with a second drug on top. A person has to read each one.
- **The candidate row's chain can miss the ligand.** 4MS4 lists GABBR2, but baclofen is in GABBR1; 2P16 and 2W26 list the factor Xa light chain, but apixaban and rivaroxaban sit in the heavy chain. So the file records the ligand copy (`A/600`), and `chain` is the chain the copy touches most.
- **An entry can hold the drug at several sites.** Zolpidem has three copies in 8DD2, lamotrigine two in 8THH, and acetazolamide three in 3HS4. The most-contacts rule picks the right copy, but for zolpidem and lamotrigine only by 1–4 contacts, so the copy is written down.
- **Membrane targets have no sharp structures.** 24 drugs have nothing ≤ 2.8 Å on their target, mostly GPCRs, transporters and ion channels.

## Decided along the way

- **Show every entry that passes review, and mark a showcase** (owner, 2026-10-13). Entries up to 3.5 Å are accepted when the pocket checks out. The four above 3.5 Å are in the set but not in the showcase.
- **No caption for an animal version of the target** (owner, 2026-10-13): mouse COX-2, bovine tubulin, pig Na,K-ATPase, rabbit α2δ-1, rat NMDA, mouse 5-HT3A, yeast CYP51. `organism` keeps the source.
- **A caption where the picture isn't the drug's main target as such:** raltegravir (foamy-virus integrase; no HIV-1 structure exists), aripiprazole (5-HT2A; no D2 structure), metformin (a debated site in complex I), diltiazem (Cav1.1 for Cav1.2), carbamazepine and lamotrigine (Nav1.7 for the brain channels), topiramate (one of several targets), and the active forms of aspirin, oseltamivir and tamoxifen. The owner decided raltegravir, aripiprazole and metformin are shown (2026-10-13).
- **Wild type over resolution** when the sharper entry has a mutation in or near the pocket or is a chimera. Spironolactone is the exception: every MR entry carries S810L in the pocket.
- **Ciprofloxacin: 5BTC over 2XCT.** 5BTC (M. tuberculosis, 2.55 Å) is the real cleavage complex, with the catalytic Tyr129 bound to the cut DNA, and its one change (A90S) puts the serine of S. aureus and E. coli into the pocket. 2XCT (S. aureus, 3.35 Å) has the catalytic tyrosine switched off (GyrA Y123F), checked against PDBe on 2026-10-13.
- **Nucleic acid in the pocket is shown.** Azithromycin binds 23S rRNA (8E42, chain I), and dolutegravir, raltegravir and ciprofloxacin touch DNA.

## Limits

- The papers were not read. Pocket residues were compared with residues known from the literature; numbering offsets (mouse COX-2, erlotinib's mature numbering, the VKOR-GFP fusion) were inferred from residue patterns.
- Contacts come from the deposited model, not the biological assembly.
- Metal ions and cofactors are dropped with the waters, also where they are part of the binding: the zinc in carbonic anhydrase (3HS4) and ACE (1O86), the magnesium ions of the integrase and gyrase complexes, the heme iron fluconazole binds (4WMZ) and the NADPH next to methotrexate (1U72).
- Spironolactone's S810L is the mutation that makes spironolactone an agonist (from the literature, not measured here).

## Reproduce

```bash
cd backend
uv run python -m molecula.ingest targets      # → data/build/complex_candidates.md
uv run pytest tests/ingest/test_hero_set.py
# One entry's ligand copies with completeness and contacts (label asym IDs):
curl -s https://data.rcsb.org/graphql -H 'Content-Type: application/json' -d '{"query":"{ entries(entry_ids: [\"2HYY\"]) { nonpolymer_entities { nonpolymer_comp { chem_comp { id } } nonpolymer_entity_instances { rcsb_nonpolymer_entity_instance_container_identifiers { auth_asym_id auth_seq_id } rcsb_nonpolymer_instance_validation_score { completeness RSCC } rcsb_target_neighbors { target_asym_id target_auth_seq_id target_comp_id distance } } } } }"}'
# Engineered mutations of an entry:
curl -s https://www.ebi.ac.uk/pdbe/api/pdb/entry/mutated_AA_or_NA/2XCT
```
