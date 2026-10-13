import { describe, expect, it } from "vitest";

import { cardOf, cardSteps, structuresOf, type Step } from "./tool-cards";
import {
  ACETAMINOPHEN_NO_COMPLEX,
  COMPARISON_WITH_UNSUPPORTED,
  GLEEVEC_FOUND,
  IBUPROFEN_PROPERTIES,
  IMATINIB_COMPLEX,
  IMATINIB_LABELS,
  NAPROXEN_PROPERTIES,
  ONE_DRUG_COMPARISON,
  TYLENOLL_NOT_SUPPORTED,
} from "./test-tool-results";

function run(name: string, result?: unknown, args: Record<string, unknown> = {}) {
  return { id: "call_1", name, args, result };
}

describe("cardOf", () => {
  it("has no card for a step without a tool, and a pending one until the tool returns", () => {
    expect(cardOf(undefined)).toBeNull();
    expect(cardOf(run("resolve_drug"))).toEqual({ kind: "pending" });
  });

  it("turns each tool's result into its card", () => {
    expect(cardOf(run("resolve_drug", GLEEVEC_FOUND))?.kind).toBe("drug");
    expect(cardOf(run("get_properties", IBUPROFEN_PROPERTIES))).toEqual({
      kind: "properties",
      drugs: [IBUPROFEN_PROPERTIES],
    });
    expect(cardOf(run("compare_drugs", COMPARISON_WITH_UNSUPPORTED))).toEqual({
      kind: "properties",
      drugs: COMPARISON_WITH_UNSUPPORTED.drugs,
    });
    expect(cardOf(run("get_complex", ACETAMINOPHEN_NO_COMPLEX))?.kind).toBe("no_complex");
  });

  it("keeps the drug and section a label search was limited to", () => {
    const card = cardOf(
      run("search_labels", IMATINIB_LABELS, { drug: "imatinib", section: "pharmacology" }),
    );

    expect(card).toMatchObject({ kind: "labels", drug: "imatinib", section: "pharmacology" });
    expect(cardOf(run("search_labels", IMATINIB_LABELS, { question: "x" }))).toMatchObject({
      drug: null,
      section: null,
    });
  });

  it("shows a name outside the store as not supported, for any tool", () => {
    for (const name of ["resolve_drug", "get_properties", "get_targets", "get_complex"]) {
      expect(cardOf(run(name, TYLENOLL_NOT_SUPPORTED))).toEqual({
        kind: "not_supported",
        drugs: [TYLENOLL_NOT_SUPPORTED],
      });
    }
    expect(
      cardOf(run("search_labels", { status: "not_supported", drugs: [TYLENOLL_NOT_SUPPORTED] })),
    ).toEqual({ kind: "not_supported", drugs: [TYLENOLL_NOT_SUPPORTED] });
  });

  it("shows a rejected call with its problems", () => {
    expect(cardOf(run("compare_drugs", ONE_DRUG_COMPARISON))).toEqual({
      kind: "invalid",
      errors: ONE_DRUG_COMPARISON.errors,
    });
  });

  it("has no card for an unknown tool or a result that isn't an object", () => {
    expect(cardOf(run("draw_molecule", GLEEVEC_FOUND))).toBeNull();
    expect(cardOf(run("resolve_drug", "Error: tool failed"))).toBeNull();
    expect(cardOf(run("resolve_drug", null))).toBeNull();
  });
});

describe("cardSteps", () => {
  const properties = (drug: string, result: unknown): Step => ({
    text: `Getting the properties of ${drug}`,
    tool: run("get_properties", result, { drug }),
  });
  const steps: Step[] = [
    { text: "Checking the question" },
    properties("ibuprofen", IBUPROFEN_PROPERTIES),
    properties("naproxen", NAPROXEN_PROPERTIES),
    { text: "Searching the ibuprofen label", tool: run("search_labels", IMATINIB_LABELS) },
  ];

  it("merges properties looked up drug by drug into one table at the first lookup", () => {
    const shown = cardSteps(steps, true);

    expect(shown.map((step) => step.text)).toEqual([
      "Checking the question",
      "Getting the properties of ibuprofen, naproxen",
      "Searching the ibuprofen label",
    ]);
    expect(shown[1].card).toEqual({
      kind: "properties",
      drugs: [IBUPROFEN_PROPERTIES, NAPROXEN_PROPERTIES],
    });
  });

  it("leaves the steps apart when asked to, or when there is one drug to show", () => {
    expect(cardSteps(steps, false)).toHaveLength(4);
    expect(cardSteps([steps[1], steps[3]], true)).toHaveLength(2);
  });

  it("merges neither a name outside the store nor a comparison", () => {
    const shown = cardSteps(
      [
        properties("ibuprofen", IBUPROFEN_PROPERTIES),
        properties("Tylenoll", TYLENOLL_NOT_SUPPORTED),
        { text: "Comparing", tool: run("compare_drugs", COMPARISON_WITH_UNSUPPORTED) },
      ],
      true,
    );

    expect(shown.map((step) => step.card?.kind)).toEqual([
      "properties",
      "not_supported",
      "properties",
    ]);
  });
});

describe("structuresOf", () => {
  const step = (name: string, result?: unknown): Step => ({
    text: "Step",
    tool: run(name, result),
  });

  it("lists each drug whose structure was looked up once, with its complex if it has one", () => {
    const steps = [
      step("get_complex", IMATINIB_COMPLEX),
      step("get_properties", IBUPROFEN_PROPERTIES),
      step("get_complex", ACETAMINOPHEN_NO_COMPLEX),
      step("get_complex", IMATINIB_COMPLEX),
    ];

    expect(structuresOf(steps)).toEqual([
      { cid: 5291, name: "imatinib", complex: IMATINIB_COMPLEX },
      { cid: 1983, name: "acetaminophen", complex: null },
    ]);
  });

  it("shows nothing for a lookup still running, an unsupported drug or a step without a tool", () => {
    const steps = [
      step("get_complex"),
      step("get_complex", TYLENOLL_NOT_SUPPORTED),
      { text: "Checked the question" },
    ];

    expect(structuresOf(steps)).toEqual([]);
  });
});
