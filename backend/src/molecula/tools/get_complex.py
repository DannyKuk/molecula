from typing import Any

from langchain_core.tools import StructuredTool

from molecula.schemas.complexes import Complex, Residue
from molecula.schemas.tools import (
    DrugArgs,
    DrugComplex,
    DrugNotSupported,
    HydrogenBond,
    NoComplex,
    ResidueContact,
)
from molecula.services.complexes import ComplexService
from molecula.services.compounds import CompoundService
from molecula.tools.base import build_tool, not_supported


def get_complex_tool(compounds: CompoundService, complexes: ComplexService) -> StructuredTool:
    def get_complex(drug: str) -> DrugComplex | NoComplex | DrugNotSupported:
        """Look up the reviewed 3D structure of a supported drug bound to its target, the one
        Molecula's 3D view shows: which protein holds the drug and which of its residues touch
        it.

        `drug` can be a generic name, a brand, a non-US or German name or a salt name; it is
        resolved to the stored drug first.

        Returns `status: "found"` with the drug's CID and generic `name`; `pdb_id`, the Protein
        Data Bank entry; `target`, the target's gene symbol, sometimes with a short note
        (call `get_targets` for its full name and the mechanism); `organism`, the species the
        protein comes from; `ligand_code`, the drug's code in that entry; `caption`, set when
        the structure is a stand-in (a related protein or species, a second target) and saying
        what it shows: pass it on;
        `hydrogen_bonds`, each with the residue (three-letter name and number), its chain, the
        two atoms and the distance in Å; `contacts`, every residue within 4 Å of the drug with
        its closest distance, closest first; `source_url`, the entry's RCSB page; and `ref`,
        the number to cite the structure with in square brackets, like `[2]`.
        Describe only these contacts; don't add binding details from memory. Returns
        `status: "no_complex"` when Molecula has no reviewed structure of this drug bound to
        its target: the 3D view shows the molecule alone. Returns `status: "not_supported"`
        with `suggestions` when the drug isn't in Molecula's data: say so and offer the
        suggestions, never pick one yourself.
        """
        resolution = compounds.resolve(drug)
        match = resolution.match
        if match is None:
            return not_supported(resolution)
        compound = match.compound
        found = complexes.get_complex(compound.cid)
        if found is None:
            return NoComplex(query=resolution.query, cid=compound.cid, name=compound.name)
        return summary(found, resolution.query, compound.cid, compound.name)

    return build_tool(get_complex, DrugArgs, finding_complex)


def summary(complex_: Complex, query: str, cid: int, name: str) -> DrugComplex:
    ligand_atoms = complex_.ligand.atoms
    return DrugComplex(
        query=query,
        cid=cid,
        name=name,
        pdb_id=complex_.pdb_id,
        target=complex_.target,
        organism=complex_.organism,
        ligand_code=complex_.ligand.code,
        caption=complex_.caption,
        hydrogen_bonds=[
            HydrogenBond(
                residue=label(contact.residue),
                chain=contact.residue.chain,
                residue_atom=contact.residue_atom,
                ligand_atom=ligand_atoms[contact.ligand_atom].name,
                distance=contact.distance,
            )
            for contact in complex_.contacts
            if contact.kind == "hbond"
        ],
        contacts=sorted(
            (
                ResidueContact(
                    residue=label(contact.residue),
                    chain=contact.residue.chain,
                    distance=contact.distance,
                )
                for contact in complex_.contacts
                if contact.kind == "contact"
            ),
            key=lambda contact: contact.distance,
        ),
        source_url=complex_.source_url,
    )


def label(residue: Residue) -> str:
    return f"{residue.name}{residue.number}{residue.ins_code}"


def finding_complex(args: dict[str, Any]) -> str:
    return f"Looking up the 3D complex of {args.get('drug', 'the drug')}"
