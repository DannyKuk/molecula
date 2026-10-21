import { describe, expect, it } from "vitest";

import type { Turn } from "./chat-turn";
import { de } from "./messages/de";
import { stepLine } from "./step-line";
import { cardSteps, type Step } from "./tool-cards";
import { IBUPROFEN_PROPERTIES, NAPROXEN_PROPERTIES } from "./test-tool-results";

function toolStep(text: string, name: string, args: Record<string, unknown>): Step {
  return { text, tool: { id: `call_${name}`, name, args } };
}

// Each line as the backend writes it, copied from its status function: `resolving` in
// `backend/src/molecula/tools/resolve_drug.py`, `getting_properties` in `get_properties.py`,
// `finding_targets` in `get_targets.py`, `finding_complex` in `get_complex.py`, `comparing` in
// `compare_drugs.py`, `searching_labels` in `search_labels.py`, and `CHECKING` and
// `CHECKING_ANSWER` in `backend/src/molecula/guard/chat.py`.
const BACKEND_STEPS: Step[] = [
  { text: "Checking the question" },
  toolStep("Looking up Gleevec", "resolve_drug", { name: "Gleevec" }),
  toolStep("Getting the properties of metformin", "get_properties", { drug: "metformin" }),
  toolStep("Finding the targets of imatinib", "get_targets", { drug: "imatinib" }),
  toolStep("Looking up the 3D complex of imatinib", "get_complex", { drug: "imatinib" }),
  toolStep("Comparing ibuprofen, naproxen", "compare_drugs", { drugs: ["ibuprofen", "naproxen"] }),
  toolStep("Searching the Gleevec label", "search_labels", {
    question: "How does it work?",
    drug: "Gleevec",
    section: "pharmacology",
  }),
  toolStep("Searching the drug labels", "search_labels", {
    question: "Do ibuprofen and warfarin interact?",
    drug: null,
  }),
  { text: "Checking the answer against the sources" },
];

describe("stepLine", () => {
  it("writes every English line word for word as the backend sends it", () => {
    for (const step of BACKEND_STEPS) {
      expect(stepLine(step)).toBe(step.text);
    }
  });

  it("writes every line in German for a German reader", () => {
    expect(BACKEND_STEPS.map((step) => stepLine(step, de))).toEqual([
      "Prüfe die Frage",
      "Schlage Gleevec nach",
      "Rufe die Eigenschaften von metformin ab",
      "Suche die Zielproteine von imatinib",
      "Schlage den 3D-Komplex von imatinib nach",
      "Vergleiche ibuprofen, naproxen",
      "Durchsuche die Fachinformation von Gleevec",
      "Durchsuche die Fachinformationen",
      "Prüfe die Antwort anhand der Quellen",
    ]);
  });

  it("writes the lines of a chat saved before the change, from its tool names and arguments", () => {
    const saved: Turn = JSON.parse(`{
      "question": "How does Gleevec work?",
      "answer": "Imatinib blocks BCR-ABL [1].",
      "state": "done",
      "sources": [],
      "passages": {},
      "sourceCheck": null,
      "steps": [
        { "text": "Checking the question" },
        {
          "text": "Searching the Gleevec label",
          "tool": { "id": "call_1", "name": "search_labels", "args": { "question": "How does it work?", "drug": "Gleevec" }, "result": { "status": "found", "passages": [] } }
        }
      ]
    }`);
    expect(saved.steps.map((step) => stepLine(step, de))).toEqual([
      "Prüfe die Frage",
      "Durchsuche die Fachinformation von Gleevec",
    ]);
  });

  it("shows a line it doesn't know as the backend sent it", () => {
    expect(stepLine({ text: "Thinking it over" }, de)).toBe("Thinking it over");
    expect(stepLine(toolStep("Running lookup_dose", "lookup_dose", { drug: "x" }), de)).toBe(
      "Running lookup_dose",
    );
  });

  it("keeps the backend's line when the arguments don't fit it", () => {
    expect(stepLine(toolStep("Looking up the drug", "resolve_drug", {}), de)).toBe(
      "Looking up the drug",
    );
    expect(stepLine(toolStep("Comparing ", "compare_drugs", { drugs: "ibuprofen" }), de)).toBe(
      "Comparing ",
    );
  });

  it("writes the line before the tool call arrives as the backend sent it", () => {
    expect(stepLine({ text: "Looking up Gleevec" }, de)).toBe("Looking up Gleevec");
  });
});

describe("cardSteps", () => {
  it("writes the merged properties line in the reader's language", () => {
    const steps = [IBUPROFEN_PROPERTIES, NAPROXEN_PROPERTIES].map((result) => ({
      text: `Getting the properties of ${result.query}`,
      tool: { id: result.query, name: "get_properties", args: { drug: result.query }, result },
    }));
    expect(cardSteps(steps, true, de).map((step) => step.text)).toEqual([
      "Rufe die Eigenschaften von ibuprofen, naproxen ab",
    ]);
    expect(cardSteps(steps, false, de).map((step) => step.text)).toEqual([
      "Rufe die Eigenschaften von ibuprofen ab",
      "Rufe die Eigenschaften von naproxen ab",
    ]);
  });
});
