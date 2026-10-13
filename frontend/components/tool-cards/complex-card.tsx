import type { DrugComplex, NoComplex } from "@/lib/tool-cards";

import { ShowMore } from "./show-more";
import { SourceLink } from "./source-link";

const SHOWN_CONTACTS = 8;

/** A drug's reviewed complex: what holds it, the hydrogen bonds and the residues around it. */
export function ComplexCard({ result }: { result: DrugComplex }) {
  return (
    <>
      {result.caption && (
        // The caption says the structure is a stand-in (a related protein or species, the
        // active form), so it comes before the facts it qualifies.
        <p className="mb-3 rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sky-900 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-200">
          {result.caption}
        </p>
      )}
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        <dt className="text-muted-foreground">Target</dt>
        <dd>{result.target ?? "–"}</dd>
        <dt className="text-muted-foreground">Organism</dt>
        <dd>{result.organism ?? "–"}</dd>
        <dt className="text-muted-foreground">Structure</dt>
        <dd>
          <SourceLink href={result.source_url}>PDB {result.pdb_id}</SourceLink>
        </dd>
        <dt className="text-muted-foreground">Drug&apos;s code in the entry</dt>
        <dd>
          <code className="font-mono">{result.ligand_code}</code>
        </dd>
      </dl>
      <h4 className="mt-3 font-medium">Hydrogen bonds</h4>
      {result.hydrogen_bonds.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="mt-1 w-full text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr>
                <th className="py-1 text-left font-normal">Residue</th>
                <th className="text-left font-normal">Chain</th>
                <th className="text-left font-normal">Atoms (protein – drug)</th>
                <th className="text-right font-normal">Distance</th>
              </tr>
            </thead>
            <tbody>
              {result.hydrogen_bonds.map((bond) => (
                <tr
                  key={`${bond.chain}:${bond.residue}:${bond.residue_atom}:${bond.ligand_atom}`}
                  className="border-t border-zinc-200 dark:border-zinc-800"
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
        <p className="mt-1 text-muted-foreground">No hydrogen bonds in this structure.</p>
      )}
      <h4 className="mt-3 font-medium">Residues within 4 Å, closest first</h4>
      <p className="mt-1 flex flex-wrap items-center gap-1">
        <ShowMore
          items={result.contacts}
          shown={SHOWN_CONTACTS}
          render={(contact) => (
            <span
              key={`${contact.chain}:${contact.residue}`}
              className="rounded-full border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-xs dark:border-zinc-800 dark:bg-zinc-900"
            >
              {contact.residue}{" "}
              <span className="text-muted-foreground tabular-nums">
                {contact.distance.toFixed(1)} Å
              </span>
            </span>
          )}
        />
      </p>
      <p className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled
          className="cursor-not-allowed rounded-md border border-zinc-300 px-3 py-1 opacity-50 dark:border-zinc-700"
        >
          View in 3D
        </button>
        <span className="text-xs text-muted-foreground">comes with the 3D viewer</span>
      </p>
    </>
  );
}

/** A supported drug without a reviewed complex. */
export function NoComplexCard({ result }: { result: NoComplex }) {
  return (
    <p>
      Molecula has no reviewed structure of {result.name} bound to its target. The 3D view shows the
      molecule alone.
    </p>
  );
}
