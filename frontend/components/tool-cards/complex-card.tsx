import { useMessages } from "@/lib/messages";
import type { DrugComplex, NoComplex } from "@/lib/tool-cards";

import { ShowMore } from "./show-more";
import { ViewIn3D } from "./view-in-3d";
import { SourceLink } from "./source-link";

const SHOWN_CONTACTS = 8;

/** A drug's reviewed complex: what holds it, the hydrogen bonds and the residues around it. */
export function ComplexCard({ result }: { result: DrugComplex }) {
  const t = useMessages();
  return (
    <>
      {result.caption && (
        // The caption says the structure is a stand-in (a related protein or species, the
        // active form), so it comes before the facts it qualifies.
        <p className="mb-3 rounded-md border border-rule-2 bg-panel px-3 py-2 text-ink">
          {result.caption}
        </p>
      )}
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        <dt className="text-muted-foreground">{t.cards.target}</dt>
        <dd>{result.target ?? "–"}</dd>
        <dt className="text-muted-foreground">{t.cards.organism}</dt>
        <dd>{result.organism ?? "–"}</dd>
        <dt className="text-muted-foreground">{t.cards.structure}</dt>
        <dd>
          <SourceLink href={result.source_url}>PDB {result.pdb_id}</SourceLink>
        </dd>
        <dt className="text-muted-foreground">{t.cards.ligandCode}</dt>
        <dd>
          <code className="font-mono">{result.ligand_code}</code>
        </dd>
      </dl>
      <h4 className="mt-3 font-medium">{t.cards.hydrogenBonds}</h4>
      {result.hydrogen_bonds.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="mt-1 w-full text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr>
                <th className="py-1 text-left font-normal">{t.cards.residue}</th>
                <th className="text-left font-normal">{t.cards.chain}</th>
                <th className="text-left font-normal">{t.cards.atoms}</th>
                <th className="text-right font-normal">{t.cards.distance}</th>
              </tr>
            </thead>
            <tbody>
              {result.hydrogen_bonds.map((bond) => (
                <tr
                  key={`${bond.chain}:${bond.residue}:${bond.residue_atom}:${bond.ligand_atom}`}
                  className="border-t border-rule"
                >
                  <td className="py-1">{bond.residue}</td>
                  <td>{bond.chain}</td>
                  <td className="font-mono text-xs">
                    {bond.residue_atom} – {bond.ligand_atom}
                  </td>
                  <td className="text-right tabular-nums">{bond.distance.toFixed(2)} Å</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-1 text-muted-foreground">{t.cards.noHydrogenBonds}</p>
      )}
      <h4 className="mt-3 font-medium">{t.cards.residuesWithin}</h4>
      <p className="mt-1 flex flex-wrap items-center gap-1">
        <ShowMore
          items={result.contacts}
          shown={SHOWN_CONTACTS}
          render={(contact) => (
            <span
              key={`${contact.chain}:${contact.residue}`}
              className="rounded-full border border-rule bg-card px-2 py-0.5 text-xs"
            >
              {contact.residue}{" "}
              <span className="text-muted-foreground tabular-nums">
                {contact.distance.toFixed(1)} Å
              </span>
            </span>
          )}
        />
      </p>
      <p className="mt-3">
        <ViewIn3D cid={result.cid}>{t.cards.viewIn3d}</ViewIn3D>
      </p>
    </>
  );
}

/** A supported drug without a reviewed complex. */
export function NoComplexCard({ result }: { result: NoComplex }) {
  const t = useMessages();
  return (
    <>
      <p>{t.cards.noComplex(result.name)}</p>
      <p className="mt-3">
        <ViewIn3D cid={result.cid}>{t.cards.viewMoleculeIn3d}</ViewIn3D>
      </p>
    </>
  );
}
