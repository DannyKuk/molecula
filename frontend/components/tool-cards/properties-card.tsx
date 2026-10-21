import { type Messages, useMessages } from "@/lib/messages";
import type { Compound, DrugNotSupported, DrugProperties } from "@/lib/tool-cards";

import { suggestionName } from "./problem-cards";
import { SourceLink } from "./source-link";

type Property = {
  key: keyof Messages["cards"]["properties"];
  value: (compound: Compound) => string;
};

const PROPERTIES: Property[] = [
  { key: "formula", value: (c) => c.formula },
  { key: "weight", value: (c) => `${c.molecular_weight} g/mol` },
  { key: "xlogp", value: (c) => (c.xlogp === null ? "–" : String(c.xlogp)) },
  { key: "tpsa", value: (c) => (c.tpsa === null ? "–" : `${c.tpsa} Å²`) },
  { key: "hbonds", value: (c) => `${c.hbond_donors} / ${c.hbond_acceptors}` },
  { key: "rotatable", value: (c) => String(c.rotatable_bonds) },
  { key: "heavy", value: (c) => String(c.heavy_atoms) },
];

/** PubChem's properties of one drug, or of several side by side; a drug outside the supported
 * drugs keeps its column, marked as not supported. */
export function PropertiesCard({ drugs }: { drugs: (DrugProperties | DrugNotSupported)[] }) {
  const t = useMessages();
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
              <tr key={property.key} className="border-t border-rule">
                <PropertyName text={t.cards.properties[property.key]} />
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

function PropertyName({ text }: { text: { label: string; hint?: string } }) {
  return (
    <th scope="row" className="px-2 py-1 text-left align-top font-normal">
      {text.label}
      {text.hint && <span className="block text-xs text-muted-foreground">{text.hint}</span>}
    </th>
  );
}

function Unsupported({ drug }: { drug: DrugNotSupported }) {
  const t = useMessages();
  return (
    <>
      <s>{drug.query}</s> <span className="text-xs font-normal">{t.cards.unsupported}</span>
      {drug.suggestions.length > 0 && (
        <span className="block text-xs font-normal text-muted-foreground">
          {t.cards.closest(drug.suggestions.map(suggestionName).join(", "))}
        </span>
      )}
    </>
  );
}
