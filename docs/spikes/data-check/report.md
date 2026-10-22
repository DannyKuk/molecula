# Molecula data check

## 1. PubChem: names, salts, properties, 3D structures

### Gleevec  (imatinib, brand name, sold as a salt)
  OK    resolved to CID 123596
  WARN  CID 123596 is a salt or mixture, parent compound is CID 5291. The app must switch to the parent.
  OK    properties: MolecularFormula=C29H31N7O, MolecularWeight=493.6, XLogP=3.5, TPSA=86.3, HBondDonorCount=2, HBondAcceptorCount=7, RotatableBondCount=7, HeavyAtomCount=37
  OK    3D conformer available (68 atoms incl. hydrogens)

### imatinib  (generic name)
  OK    resolved to CID 5291
  OK    properties: MolecularFormula=C29H31N7O, MolecularWeight=493.6, XLogP=3.5, TPSA=86.3, HBondDonorCount=2, HBondAcceptorCount=7, RotatableBondCount=7, HeavyAtomCount=37
  OK    3D conformer available (68 atoms incl. hydrogens)

### caffeine  (simple)
  OK    resolved to CID 2519
  OK    properties: MolecularFormula=C8H10N4O2, MolecularWeight=194.19, XLogP=-0.1, TPSA=58.4, HBondDonorCount=0, HBondAcceptorCount=3, RotatableBondCount=0, HeavyAtomCount=14
  OK    3D conformer available (24 atoms incl. hydrogens)

### ibuprofen  (racemic mixture)
  OK    resolved to CID 3672
  OK    properties: MolecularFormula=C13H18O2, MolecularWeight=206.28, XLogP=3.5, TPSA=37.3, HBondDonorCount=1, HBondAcceptorCount=2, RotatableBondCount=4, HeavyAtomCount=15
  OK    3D conformer available (33 atoms incl. hydrogens)

### Tylenol  (US brand name for paracetamol)
  OK    resolved to CID 1983
  OK    properties: MolecularFormula=C8H9NO2, MolecularWeight=151.16, XLogP=0.5, TPSA=49.3, HBondDonorCount=2, HBondAcceptorCount=2, RotatableBondCount=1, HeavyAtomCount=11
  OK    3D conformer available (20 atoms incl. hydrogens)

### paracetamol  (non-US generic name)
  OK    resolved to CID 1983
  OK    properties: MolecularFormula=C8H9NO2, MolecularWeight=151.16, XLogP=0.5, TPSA=49.3, HBondDonorCount=2, HBondAcceptorCount=2, RotatableBondCount=1, HeavyAtomCount=11
  OK    3D conformer available (20 atoms incl. hydrogens)

### Aspirin  (everyday)
  OK    resolved to CID 2244
  OK    properties: MolecularFormula=C9H8O4, MolecularWeight=180.16, XLogP=1.2, TPSA=63.6, HBondDonorCount=1, HBondAcceptorCount=4, RotatableBondCount=3, HeavyAtomCount=13
  OK    3D conformer available (21 atoms incl. hydrogens)

### atorvastatin  (larger drug, 41 heavy atoms)
  OK    resolved to CID 60823
  OK    properties: MolecularFormula=C33H35FN2O5, MolecularWeight=558.6, XLogP=5, TPSA=112, HBondDonorCount=4, HBondAcceptorCount=6, RotatableBondCount=12, HeavyAtomCount=41
  OK    3D conformer available (76 atoms incl. hydrogens)

### cetirizine  (antihistamine)
  OK    resolved to CID 2678
  OK    properties: MolecularFormula=C21H25ClN2O3, MolecularWeight=388.9, XLogP=1.7, TPSA=53, HBondDonorCount=1, HBondAcceptorCount=5, RotatableBondCount=8, HeavyAtomCount=27
  OK    3D conformer available (52 atoms incl. hydrogens)

### Ibuflam  (German brand, probably unknown to PubChem)
  FAIL  name not resolved (HTTP 404)

### insulin  (protein, no small-molecule 3D expected)
  OK    resolved to CID 70678557
  OK    properties: MolecularFormula=C256H381N65O77S6, MolecularWeight=5794, XLogP=-12.8, TPSA=2450, HBondDonorCount=78, HBondAcceptorCount=89, RotatableBondCount=178, HeavyAtomCount=404
  WARN  no PubChem 3D conformer (HTTP 404). The app needs the RDKit fallback or a 'not supported' answer.

### semaglutide  (peptide drug, too big/flexible for PubChem 3D)
  OK    resolved to CID 56843331
  OK    properties: MolecularFormula=C187H291N45O59, MolecularWeight=4114, XLogP=-5.8, TPSA=1650, HBondDonorCount=57, HBondAcceptorCount=63, RotatableBondCount=151, HeavyAtomCount=291
  WARN  no PubChem 3D conformer (HTTP 404). The app needs the RDKit fallback or a 'not supported' answer.

## 2. Demo numbers vs PubChem

Demo values come from RDKit. logP differs by design: RDKit uses Crippen logP, PubChem uses XLogP3. H-bond acceptor counts also use different rules.

| Molecule | MW demo / PubChem | logP demo / PubChem | TPSA | HBD | HBA | Rot. bonds |
|---|---|---|---|---|---|---|
| imatinib | 493.6 / 493.6 | 4.59 / 3.5 | 86.3 / 86.3 | 2 / 2 | 7 / 7 | 7 / 7 |
| caffeine | 194.2 / 194.19 | -1.03 / -0.1 | 61.8 / 58.4 | 0 / 0 | 3 / 3 | 0 / 0 |
| ibuprofen | 206.3 / 206.28 | 3.07 / 3.5 | 37.3 / 37.3 | 1 / 1 | 1 / 2 | 4 / 4 |

## 3. RCSB PDB: can we find drug-protein complexes automatically?

### imatinib
  OK    PubChem InChIKey KTUFNOKKBVMGRW-UHFFFAOYSA-N maps to PDB ligand code(s): 1N1, 2PE, 3YY, ACT, ALA, ARG, ASN, ASP, BOG, CL, CLR, CYS, DCM, EDO, FAD, FYH, FYW, GLN, GLU, GLY, GOL, HIS, ILE, KWD, KWP, KWV, LEU, LYS, MET, MG, MRD, MS7, MS9, MYR, PHE, PO4, PRO, SER, SO4, STI, STJ, THR, TRP, TYR, UDP, VAL, ZN
  OK    23 PDB entries contain 1N1, e.g. 2GQG, 2Y6O, 2ZVA, 3G5D, 3K54, 3LFA, 3OCT, 3OHT

### caffeine
  OK    PubChem InChIKey RYYVLZVUVIJVGH-UHFFFAOYSA-N maps to PDB ligand code(s): 055, 117, 25D, 26B, 43M, 700, A1BYZ, A1C3Z, A1CXI, A1LV1, A1LVX, ACP, ACT, ADP, ALA, ARG, ASN, ASP, ATP, BIN, BMA, CA, CFF, CL, CLR, CO, CPS, CSO, CYS, DMS, EDO, F0U, FE, FES, FRU, GLC, GLN, GLU, GLY, GOL, GXU, HEM, HIS, ILE, IMD, IMP, KDH, KVR, L9R, LEU, LLP, LYS, MAN, MES, MET, MG, MPD, MRD, MSE, NA, NAG, NBG, OLA, OLC, PCW, PHE, PLC, PLP, PO4, POV, PRD_900003, PRO, PYR, SAH, SAM, SEP, SER, SO4, TAR, THR, TRP, TRS, TYR, U1C, UNK, VAL, ZN
  OK    1 PDB entries contain 055, e.g. 3DDW

### ibuprofen
  WARN  exact InChIKey HEFNNWSXXWATRW-UHFFFAOYSA-N not in PDB (stereo or protonation may differ), trying the connectivity block
  WARN  no match on connectivity either
  ...   falling back to the known ligand code IBP
  OK    15 PDB entries contain IBP, e.g. 1EQG, 28ZJ, 2BXG, 2PWS, 2WD9, 3IB2, 3P6H, 4JTR

### Aspirin
  OK    PubChem InChIKey BSYNRYMUTXBXSQ-UHFFFAOYSA-N maps to PDB ligand code(s): AIN, ALA, ARG, ASN, ASP, BMA, CA, CO3, CYS, DMS, EOH, FE, GLN, GLU, GLY, HEM, HIS, ILE, IOD, LEU, LYS, MAN, MET, NAG, NDG, PHE, PRO, SCN, SEP, SER, SO4, THR, TRP, TYR, VAL, ZN
  OK    8 PDB entries contain AIN, e.g. 1OXR, 1TGM, 2QQT, 3GCL, 3IAZ, 4NSB, 6MQF, 8J3W

### paracetamol
  OK    PubChem InChIKey RZVAJINKPMORJF-UHFFFAOYSA-N maps to PDB ligand code(s): ALA, ARG, ASN, ASP, BMA, CA, CL, CO3, CXS, CYS, EDO, FE, GLN, GLU, GLY, GOL, HEM, HIS, ILE, IOD, K, LEU, LYS, MAN, MET, MPD, NAG, PHE, PRO, SCN, SEP, SER, SO4, THR, TRP, TYL, TYR, VAL, ZN
  OK    202 PDB entries contain ALA, e.g. 1D0K, 1E8K, 1HSB, 1KL6, 1PIN, 1QTE, 1RXQ, 1TA9

## 4. 1IEP downloaded from RCSB vs the cleaned file the demo used

  OK    raw file: protein chains ['A', 'B'], imatinib (STI) copies in chains ['A', 'B'], 172 water atoms, hydrogens present: False
  WARN  raw entries need cleaning before display: pick one chain and ligand copy, drop waters and other het groups. The demo file was already cleaned.
  OK    chain A: 37 ligand heavy atoms, 274 protein residues
  OK    polar contacts < 3.3 Å from the raw file: Ile360 2.67 Å, Thr315 2.88 Å, Asp381 2.9 Å, Met318 2.9 Å, Glu286 3.0 Å, His361 3.19 Å
  OK    identical to the six contacts shown in the demo
  ...   run from the molecula-prototype folder to compare coordinates with the demo file

## 5. openFDA drug labels: what text would the knowledge base get?

  OK    imatinib: 22 labels match. First: Imatinib Mesylate / IMATINIB MESYLATE, HUMAN PRESCRIPTION DRUG
        sections: indications_and_usage (3823 chars), mechanism_of_action (1012 chars), dosage_and_administration (12227 chars), warnings_and_cautions (13021 chars), contraindications (37 chars), drug_interactions (2182 chars), adverse_reactions (39833 chars), clinical_pharmacology (10782 chars)
  OK    ibuprofen: 1147 labels match. First: Ibuprofen Dye Free / IBUPROFEN, HUMAN OTC DRUG
        sections: indications_and_usage (181 chars), dosage_and_administration (351 chars), warnings (2615 chars), do_not_use (129 chars), stop_use (487 chars), active_ingredient (108 chars)
  OK    acetaminophen: 3284 labels match. First: Pain Reliever Extra Strength / ACETAMINOPHEN, HUMAN OTC DRUG
        sections: indications_and_usage (198 chars), dosage_and_administration (301 chars), warnings (1360 chars), do_not_use (265 chars), stop_use (209 chars), active_ingredient (55 chars)
  WARN  paracetamol: no label found via generic_name
  OK    caffeine: 424 labels match. First: Stay Awake / CAFFEINE, HUMAN OTC DRUG
        sections: indications_and_usage (89 chars), dosage_and_administration (138 chars), warnings (690 chars), do_not_use (71 chars), stop_use (82 chars), active_ingredient (50 chars)
  OK    Gleevec: 1 labels match. First: Gleevec / IMATINIB MESYLATE, HUMAN PRESCRIPTION DRUG
        sections: indications_and_usage (3799 chars), mechanism_of_action (1011 chars), dosage_and_administration (11580 chars), warnings_and_cautions (12360 chars), contraindications (37 chars), drug_interactions (2040 chars), adverse_reactions (39113 chars), clinical_pharmacology (10441 chars)

### Prescription labels (these carry mechanism of action, OTC labels don't)

  OK    ibuprofen: 20 Rx labels with mechanism. First: Ibuprofen and famotidine
        12.1 Mechanism of Action Ibuprofen and famotidine tablet is a fixed-combination tablet of ibuprofen and famotidine. The ibuprofen component has analgesic, anti- inflammatory, and antipyretic properties. The mechanism of action of the ibuprofen component of ibuprofen and famotidine tablet, like that ...
  OK    acetaminophen: 144 Rx labels with mechanism. First: Hydrocodone Bitartrate and Acetaminophen
        Mechanism of Action Hydrocodone is a full opioid agonist with relative selectivity for the mu-opioid (µ) receptor, although it can interact with other opioid receptors at higher doses. The principal therapeutic action of hydrocodone is analgesia. Like all full opioid agonists, there is no ceiling ef...
  OK    caffeine: 16 Rx labels with mechanism. First: Butalbital, Acetaminophen, Caffeine and Codeine Phosphate
        12.1 Mechanism of Action Butalbital, a barbiturate, is a GABA A receptor agonist and may inhibit excitatory AMPA receptors. The precise mechanism of the analgesic properties of acetaminophen is not established but is thought to involve central actions. Caffeine is a methylxanthine and CNS stimulant....

Notes: openFDA covers US labels only, so names like 'paracetamol' or German brands need mapping first (PubChem synonyms help). OTC labels (Drug Facts) use different sections than prescription labels, so chunking must handle both layouts.
