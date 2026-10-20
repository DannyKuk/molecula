import type { RetrievalTrace } from "./tool-cards";

// Tool results recorded from the local store (search_labels from a gpt-oss-20b answer), trimmed.

/** `resolve_drug` for Gleevec. */
export const GLEEVEC_FOUND = {
  status: "found",
  query: "Gleevec",
  cid: 5291,
  name: "imatinib",
  matched_alias: "Gleevec",
  match_kind: "alias",
  source: "pubchem",
  source_url: "https://pubchem.ncbi.nlm.nih.gov/compound/5291",
};

/** `resolve_drug` for a misspelled Tylenol. */
export const TYLENOLL_NOT_SUPPORTED = {
  status: "not_supported",
  query: "Tylenoll",
  suggestions: [{ alias: "Tylenol", cid: 1983, name: "acetaminophen" }],
};

/** `get_properties` for metformin. */
export const METFORMIN_PROPERTIES = {
  status: "found",
  query: "metformin",
  compound: {
    cid: 4091,
    name: "metformin",
    inchikey: "XZWYZXLIPXDOLR-UHFFFAOYSA-N",
    smiles: "CN(C)C(=N)N=C(N)N",
    formula: "C4H11N5",
    molecular_weight: 129.16,
    xlogp: -1.3,
    tpsa: 91.5,
    hbond_donors: 3,
    hbond_acceptors: 1,
    rotatable_bonds: 2,
    heavy_atoms: 9,
    has_3d: true,
    conformer_source: "pubchem",
    source: "pubchem",
    source_url: "https://pubchem.ncbi.nlm.nih.gov/compound/4091",
  },
};

/** `get_properties` for ibuprofen, as `compare_drugs` returns it. */
export const IBUPROFEN_PROPERTIES = {
  status: "found",
  query: "ibuprofen",
  compound: {
    cid: 3672,
    name: "ibuprofen",
    inchikey: "HEFNNWSXXWATRW-UHFFFAOYSA-N",
    smiles: "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
    formula: "C13H18O2",
    molecular_weight: 206.28,
    xlogp: 3.5,
    tpsa: 37.3,
    hbond_donors: 1,
    hbond_acceptors: 2,
    rotatable_bonds: 4,
    heavy_atoms: 15,
    has_3d: true,
    conformer_source: "pubchem",
    source: "pubchem",
    source_url: "https://pubchem.ncbi.nlm.nih.gov/compound/3672",
  },
};

/** `get_properties` for naproxen. */
export const NAPROXEN_PROPERTIES = {
  status: "found",
  query: "naproxen",
  compound: {
    cid: 156391,
    name: "naproxen",
    inchikey: "CMWTZPSULFXXJA-VIFPVBQESA-N",
    smiles: "C[C@@H](C1=CC2=C(C=C1)C=C(C=C2)OC)C(=O)O",
    formula: "C14H14O3",
    molecular_weight: 230.26,
    xlogp: 3.3,
    tpsa: 46.5,
    hbond_donors: 1,
    hbond_acceptors: 3,
    rotatable_bonds: 3,
    heavy_atoms: 17,
    has_3d: true,
    conformer_source: "pubchem",
    source: "pubchem",
    source_url: "https://pubchem.ncbi.nlm.nih.gov/compound/156391",
  },
};

/** `compare_drugs` for ibuprofen, naproxen and a name outside the store. */
export const COMPARISON_WITH_UNSUPPORTED = {
  drugs: [
    {
      status: "found",
      query: "ibuprofen",
      compound: {
        cid: 3672,
        name: "ibuprofen",
        inchikey: "HEFNNWSXXWATRW-UHFFFAOYSA-N",
        smiles: "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
        formula: "C13H18O2",
        molecular_weight: 206.28,
        xlogp: 3.5,
        tpsa: 37.3,
        hbond_donors: 1,
        hbond_acceptors: 2,
        rotatable_bonds: 4,
        heavy_atoms: 15,
        has_3d: true,
        conformer_source: "pubchem",
        source: "pubchem",
        source_url: "https://pubchem.ncbi.nlm.nih.gov/compound/3672",
      },
    },
    {
      status: "found",
      query: "naproxen",
      compound: {
        cid: 156391,
        name: "naproxen",
        inchikey: "CMWTZPSULFXXJA-VIFPVBQESA-N",
        smiles: "C[C@@H](C1=CC2=C(C=C1)C=C(C=C2)OC)C(=O)O",
        formula: "C14H14O3",
        molecular_weight: 230.26,
        xlogp: 3.3,
        tpsa: 46.5,
        hbond_donors: 1,
        hbond_acceptors: 3,
        rotatable_bonds: 3,
        heavy_atoms: 17,
        has_3d: true,
        conformer_source: "pubchem",
        source: "pubchem",
        source_url: "https://pubchem.ncbi.nlm.nih.gov/compound/156391",
      },
    },
    { status: "not_supported", query: "Vicodinx", suggestions: [] },
  ],
};

/** `get_targets` for metformin; its first target's 50 genes cut to 8. */
export const METFORMIN_TARGETS = {
  status: "found",
  query: "metformin",
  cid: 4091,
  name: "metformin",
  targets: [
    {
      target_chembl_id: "CHEMBL2363065",
      name: "Mitochondrial complex I (NADH dehydrogenase)",
      target_type: "PROTEIN COMPLEX",
      organism: "Homo sapiens",
      mechanism: "Mitochondrial complex I (NADH dehydrogenase) inhibitor",
      action_type: "INHIBITOR",
      accessions: [
        "P03923",
        "O95299",
        "O00217",
        "P03901",
        "P56556",
        "P03886",
        "O95139",
        "O00483",
        "Q86Y39",
        "P17568",
        "P03891",
        "O75306",
        "P03915",
        "P51970",
        "O43674",
        "P03905",
        "P03897",
        "O14561",
        "O15239",
        "O43181",
        "O43676",
        "O43677",
        "O43678",
        "O43920",
        "O75251",
        "O75380",
        "O75438",
        "O75489",
        "O95167",
        "O95168",
        "O95169",
        "O95178",
        "O95182",
        "O95298",
        "O96000",
        "P19404",
        "P28331",
        "P49821",
        "P56181",
        "Q16718",
        "Q16795",
        "Q8N183",
        "Q9BU61",
        "Q9NRX3",
        "Q9NX14",
        "Q9P032",
        "Q9P0J0",
        "Q9UI09",
        "Q9Y375",
        "Q9Y6M9",
      ],
      gene_symbols: [
        "MT-ND6",
        "NDUFA10",
        "NDUFS8",
        "MT-ND4L",
        "NDUFA6",
        "MT-ND1",
        "NDUFB6",
        "COXFA4",
      ],
      source: "chembl",
      source_url: "https://www.ebi.ac.uk/chembl/explore/target/CHEMBL2363065",
    },
    {
      target_chembl_id: "CHEMBL3391681",
      name: "Glycerol-3-phosphate dehydrogenase, mitochondrial",
      target_type: "SINGLE PROTEIN",
      organism: "Homo sapiens",
      mechanism: "Mitochondrial glycerol-3-phosphate dehydrogenase inhibitor",
      action_type: "INHIBITOR",
      accessions: ["P43304"],
      gene_symbols: ["GPD2"],
      source: "chembl",
      source_url: "https://www.ebi.ac.uk/chembl/explore/target/CHEMBL3391681",
    },
  ],
};

/** `get_targets` for a drug ChEMBL lists no mechanism for. */
export const GUAIFENESIN_TARGETS = {
  status: "found",
  query: "guaifenesin",
  cid: 3516,
  name: "guaifenesin",
  targets: [],
};

/** `get_complex` for imatinib; its 23 contacts cut to 10. */
export const IMATINIB_COMPLEX = {
  status: "found",
  query: "imatinib",
  cid: 5291,
  name: "imatinib",
  pdb_id: "2HYY",
  target: "ABL1 (BCR-ABL)",
  organism: "Homo sapiens",
  ligand_code: "STI",
  caption: null,
  hydrogen_bonds: [
    { residue: "ILE360", chain: "A", residue_atom: "O", ligand_atom: "N51", distance: 2.72 },
    { residue: "MET318", chain: "A", residue_atom: "N", ligand_atom: "N3", distance: 2.94 },
    { residue: "ASP381", chain: "A", residue_atom: "N", ligand_atom: "O29", distance: 2.98 },
    { residue: "THR315", chain: "A", residue_atom: "OG1", ligand_atom: "N13", distance: 3.01 },
    { residue: "GLU286", chain: "A", residue_atom: "OE2", ligand_atom: "N21", distance: 3.09 },
    { residue: "HIS361", chain: "A", residue_atom: "O", ligand_atom: "N51", distance: 3.12 },
  ],
  contacts: [
    { residue: "ILE360", chain: "A", distance: 2.72 },
    { residue: "MET318", chain: "A", distance: 2.94 },
    { residue: "ASP381", chain: "A", distance: 2.97 },
    { residue: "HIS361", chain: "A", distance: 2.98 },
    { residue: "THR315", chain: "A", distance: 3.01 },
    { residue: "GLU286", chain: "A", distance: 3.09 },
    { residue: "PHE382", chain: "A", distance: 3.19 },
    { residue: "MET290", chain: "A", distance: 3.26 },
    { residue: "VAL299", chain: "A", distance: 3.28 },
    { residue: "PHE317", chain: "A", distance: 3.33 },
  ],
  source_url: "https://www.rcsb.org/structure/2HYY",
};

/** `get_complex` for metformin: a stand-in structure without hydrogen bonds. */
export const METFORMIN_COMPLEX = {
  status: "found",
  query: "metformin",
  cid: 4091,
  name: "metformin",
  pdb_id: "8ZSQ",
  target: "complex I",
  organism: "Sus scrofa",
  ligand_code: "MF8",
  caption:
    "A proposed binding site in mitochondrial complex I. How metformin lowers blood sugar is still debated.",
  hydrogen_bonds: [],
  contacts: [
    { residue: "HIS98", chain: "S2", distance: 3.23 },
    { residue: "MET77", chain: "S7", distance: 3.39 },
    { residue: "THR195", chain: "S2", distance: 3.45 },
    { residue: "TYR147", chain: "S2", distance: 3.59 },
    { residue: "ALA70", chain: "S7", distance: 3.6 },
    { residue: "GLY68", chain: "S7", distance: 3.63 },
    { residue: "ALA73", chain: "S7", distance: 3.65 },
  ],
  source_url: "https://www.rcsb.org/structure/8ZSQ",
};

/** `get_complex` for a drug without a reviewed complex. */
export const ACETAMINOPHEN_NO_COMPLEX = {
  status: "no_complex",
  query: "acetaminophen",
  cid: 1983,
  name: "acetaminophen",
};

/** `compare_drugs` called with one drug. */
export const ONE_DRUG_COMPARISON = {
  status: "invalid_arguments",
  errors: ["drugs: List should have at least 2 items after validation, not 1"],
};

/** `search_labels` for imatinib's mechanism; two of its five passages, shortened. */
export const IMATINIB_LABELS = {
  status: "found",
  question: "What is the mechanism of action of imatinib?",
  drugs: ["imatinib"],
  drugs_without_label: [],
  unsupported: [],
  passages: [
    {
      id: "211ef2da-2868-4a77-8055-1cb2cd78e24b:mechanism_of_action:0",
      ref: 1,
      text: "12.1 Mechanism of Action Imatinib mesylate is a protein-tyrosine kinase inhibitor that inhibits the BCR-ABL tyrosine kinase, the constitutive abnormal tyrosine ",
      substance: "IMATINIB MESYLATE",
      brand: "Gleevec",
      section: "mechanism_of_action",
      effective_time: "2026-07-13",
      url: "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=211ef2da-2868-4a77-8055-1cb2cd78e24b",
    },
    {
      id: "211ef2da-2868-4a77-8055-1cb2cd78e24b:pharmacokinetics:3",
      ref: 2,
      text: "Unchanged imatinib accounted for 25% of the dose (5% urine, 20% feces), the remainder being metabolites. Following oral administration in healthy volunteers, th",
      substance: "IMATINIB MESYLATE",
      brand: "Gleevec",
      section: "pharmacokinetics",
      effective_time: "2026-07-13",
      url: "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=211ef2da-2868-4a77-8055-1cb2cd78e24b",
    },
  ],
};

const IMATINIB_DROPPED = {
  id: "211ef2da-2868-4a77-8055-1cb2cd78e24b:how_supplied:0",
  text: "Gleevec tablets are supplied as 100 mg and 400 mg film-coated tablets.",
  score: 0.21,
  substance: "IMATINIB MESYLATE",
  brand: "Gleevec",
  section: "how_supplied",
  url: "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=211ef2da-2868-4a77-8055-1cb2cd78e24b",
  in_section_groups: false,
  dense_rank: 3,
  bm25_rank: null,
  kept: false,
};

/** The trace of the search in `IMATINIB_LABELS`, the agent naming Gleevec and pharmacology. Its
 * real run kept every candidate (the app's minimum similarity is 0.00); this one drops one below
 * a minimum of 0.30 to show how a dropped passage looks. */
export const IMATINIB_TRACE: RetrievalTrace = {
  tool_call_id: "call_1",
  question: IMATINIB_LABELS.question,
  translation: [],
  filter: {
    drugs: [
      {
        name: "Gleevec",
        generic: "imatinib",
        set_ids: ["211ef2da-2868-4a77-8055-1cb2cd78e24b"],
        narrowed: false,
      },
    ],
    unsupported: [],
    section_groups: ["pharmacology"],
    ignored_section_groups: [],
    product_type: null,
    extraction_error: null,
  },
  filter_source: "agent",
  widened: [],
  candidates: [
    { ...IMATINIB_LABELS.passages[0], score: 0.71, in_section_groups: true, dense_rank: 1 },
    { ...IMATINIB_LABELS.passages[1], score: 0.52, in_section_groups: true, dense_rank: 2 },
    IMATINIB_DROPPED,
  ].map((candidate) => ({ bm25_rank: null, kept: true, ...candidate })),
  mode: "dense",
  min_score: 0.3,
  section_group_boost: 0.15,
};
