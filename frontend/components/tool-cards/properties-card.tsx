import type { Compound, DrugNotSupported, DrugProperties } from "@/lib/tool-cards";

import { suggestionName } from "./problem-cards";
import { SourceLink } from "./source-link";

type Property = { label: string; hint?: string; value: (compound: Compound) => string };

const PROPERTIES: Property[] = [
  { label: "Formula", value: (c) => c.formula },
  { label: "Molecular weight", value: (c) => `${c.molecular_weight} g/mol` },
  {
    label: "XLogP",
    hint: "higher = dissolves better in fat than in water",
    value: (c) => (c.xlogp === null ? "–" : String(c.xlogp)),
  },
  {
    label: "Polar surface (TPSA)",
    hint: "lower = crosses cell membranes more easily",
    value: (c) => (c.tpsa === null ? "–" : `${c.tpsa} Å²`),
  },
  { label: "H-bond donors / acceptors", value: (c) => `${c.hbond_donors} / ${c.hbond_acceptors}` },
  {
    label: "Rotatable bonds",
    hint: "how flexible the molecule is",
    value: (c) => String(c.rotatable_bonds),
  },
  { label: "Heavy atoms", hint: "atoms other than hydrogen", value: (c) => String(c.heavy_atoms) },
];

/** PubChem's properties of one drug, or of several side by side; a drug outside the supported
 * drugs keeps its column, marked as not supported. */
export function PropertiesCard({ drugs }: { drugs: (DrugProperties | DrugNotSupported)[] }) {
  const several = drugs.length > 1;
  const found = drugs.filter((drug): drug is DrugProperties => drug.status === "found");
  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          {several && (
            <thead>
              <tr>
                <td />
                {drugs.map((drug) => (
                  <th key={drug.query} scope="col" className="px-2 py-1 text-left font-medium">
                    {drug.status === "found" ? drug.compound.name : <Unsupported drug={drug} />}
                  </th>
                ))}
              </tr>
            </thead>
          )}
          <tbody>
            {PROPERTIES.map((property) => (
              <tr key={property.label} className="border-t border-rule">
                <th scope="row" className="px-2 py-1 text-left align-top font-normal">
                  {property.label}
                  {property.hint && (
                    <span className="block text-xs text-muted-foreground">{property.hint}</span>
                  )}
                </th>
                {drugs.map((drug) => (
                  <td key={drug.query} className="px-2 py-1 align-top tabular-nums">
                    {drug.status === "found" ? property.value(drug.compound) : "–"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {found.length > 0 && (
        <p className="mt-2 flex flex-wrap gap-x-3">
          {found.map((drug) => (
            <SourceLink key={drug.compound.cid} href={drug.compound.source_url}>
              {several ? `PubChem: ${drug.compound.name}` : "PubChem"}
            </SourceLink>
          ))}
        </p>
      )}
    </>
  );
}

function Unsupported({ drug }: { drug: DrugNotSupported }) {
  return (
    <>
      <s>{drug.query}</s> <span className="text-xs font-normal">not supported</span>
      {drug.suggestions.length > 0 && (
        <span className="block text-xs font-normal text-muted-foreground">
          closest: {drug.suggestions.map(suggestionName).join(", ")}
        </span>
      )}
    </>
  );
}
