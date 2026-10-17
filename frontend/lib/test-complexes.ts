import type { Complex } from "./api";

/**
 * A hand-made complex in the shape of `GET /drugs/{cid}/complex`: three trace residues (a helix
 * residue, a pocket residue and a nucleotide), a second pocket residue with an insertion code that
 * isn't on the trace, a three-atom drug, and contacts including a hydrogen bond to an atom the
 * pocket doesn't have.
 */
export const SMALL_COMPLEX: Complex = {
  pdb_id: "1ABC",
  ligand: {
    code: "LIG",
    chain: "A",
    number: 900,
    atoms: [
      { name: "N1", element: "N", xyz: [10, 0, 0] },
      { name: "C2", element: "C", xyz: [11, 0, 0] },
      { name: "O3", element: "O", xyz: [12, 0, 0] },
    ],
    bonds: [
      { atoms: [0, 1], order: "aromatic" },
      { atoms: [1, 2], order: "double" },
    ],
  },
  trace: [
    { chain: "A", number: 1, ins_code: "", name: "ALA", sse: "helix", xyz: [0, 0, 0] },
    { chain: "A", number: 2, ins_code: "", name: "GLU", sse: "sheet", xyz: [3.8, 0, 0] },
    { chain: "B", number: 5, ins_code: "", name: "DA", sse: null, xyz: [0, 6, 0] },
  ],
  pocket: [
    {
      chain: "A",
      number: 2,
      ins_code: "",
      name: "GLU",
      atoms: [
        { name: "CA", element: "C", xyz: [3.8, 0, 0] },
        { name: "OE2", element: "O", xyz: [8, 0, 0] },
      ],
    },
    {
      chain: "A",
      number: 7,
      ins_code: "A",
      name: "THR",
      atoms: [{ name: "OG1", element: "O", xyz: [12, 3, 0] }],
    },
  ],
  metals: [],
  cofactors: [],
  contacts: [
    {
      kind: "hbond",
      residue: { chain: "A", number: 2, ins_code: "", name: "GLU" },
      residue_atom: "OE2",
      ligand_atom: 0,
      distance: 2.9,
    },
    {
      kind: "hbond",
      residue: { chain: "A", number: 7, ins_code: "A", name: "THR" },
      residue_atom: "OG1",
      ligand_atom: 2,
      distance: 3.0,
    },
    {
      kind: "hbond",
      residue: { chain: "A", number: 2, ins_code: "", name: "GLU" },
      residue_atom: "OE1",
      ligand_atom: 0,
      distance: 3.1,
    },
    {
      kind: "contact",
      residue: { chain: "A", number: 2, ins_code: "", name: "GLU" },
      residue_atom: "OE2",
      ligand_atom: 0,
      distance: 2.9,
    },
  ],
  target: "ABL1 (BCR-ABL)",
  organism: "Homo sapiens",
  caption: null,
  showcase: false,
  source_url: "https://www.rcsb.org/structure/1ABC",
};
