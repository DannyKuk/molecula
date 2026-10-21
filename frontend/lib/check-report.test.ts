import { describe, expect, it } from "vitest";

import type { ChatEvent } from "./chat";
import { applyEvent, startTurn, type Turn } from "./chat-turn";
import { checkReport } from "./check-report";
import { de } from "./messages/de";

const LONG_PASSAGE = `CLINICAL PHARMACOLOGY ${"Ibuprofen possesses analgesic and antipyretic activities. ".repeat(40)}Its mode of action may be related to prostaglandin synthetase inhibition.`;

function turnOf(question: string, events: ChatEvent[]): Turn {
  return events.reduce(applyEvent, startTurn(question));
}

const ANSWERED: ChatEvent[] = [
  { type: "status", message: "Searching the ibuprofen label" },
  { type: "tool_call", id: "call-1", name: "search_labels", args: { query: "ibuprofen" } },
  {
    type: "tool_result",
    id: "call-1",
    name: "search_labels",
    status: null,
    result: { passages: [{ ref: 1, text: LONG_PASSAGE, section: "clinical_pharmacology" }] },
  },
  { type: "token", text: "Ibuprofen is an NSAID [1]. It was first sold in 1969." },
  {
    type: "sources",
    sources: [
      {
        kind: "label",
        name: "Ibuprofen",
        url: "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=x",
        section: "Clinical pharmacology",
        effective_time: null,
        ref: 1,
      },
    ],
    unknown_refs: [],
  },
  {
    type: "source_check",
    checked: true,
    claims: [
      {
        text: "Ibuprofen is an NSAID [1].",
        refs: [1],
        label: "supported",
        decided_by: "model",
        reason: "Source 1 calls it an NSAID.",
        held_by: [],
      },
      {
        text: "It was first sold in 1969.",
        refs: [],
        label: "unsupported",
        decided_by: "model",
        reason: "No source gives a year.",
        held_by: [],
      },
      {
        text: "It lowers fever.",
        refs: [],
        label: "held_elsewhere",
        decided_by: "model",
        reason: "Source 1 says antipyretic.",
        held_by: [1],
      },
    ],
  },
];

describe("checkReport", () => {
  it("has the question, the answer and every claim with its verdict and reason", () => {
    const report = checkReport(turnOf("How does ibuprofen work?", ANSWERED));

    expect(report).toContain("## Question\n\nHow does ibuprofen work?");
    expect(report).toContain("## Answer\n\nIbuprofen is an NSAID [1]. It was first sold in 1969.");
    expect(report).toContain("1. **supported** (refs [1], decided by model)");
    expect(report).toContain("2. **unsupported** (refs none, decided by model)");
    expect(report).toContain("   > It was first sold in 1969.\n   Reason: No source gives a year.");
    expect(report).toContain("3. **held_elsewhere** (refs none, held by [1], decided by model)");
  });

  it("has every tool result in full, with the passage text uncut", () => {
    const report = checkReport(turnOf("How does ibuprofen work?", ANSWERED));

    expect(LONG_PASSAGE.length).toBeGreaterThan(2000);
    expect(report).toContain('### search_labels {"query":"ibuprofen"}');
    expect(report).toContain(JSON.stringify(LONG_PASSAGE));
    expect(report).toContain(
      "- [1] Ibuprofen · Clinical pharmacology (label): https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=x",
    );
  });

  it("says when the check failed", () => {
    const events: ChatEvent[] = [
      ...ANSWERED.slice(0, -1),
      { type: "source_check", checked: false, claims: [] },
    ];

    expect(checkReport(turnOf("How does ibuprofen work?", events))).toContain(
      "## Source check\n\nNot checked: the check failed.",
    );
  });

  it("says when the answer used no tools and has no check", () => {
    const report = checkReport(
      turnOf("Write me a poem.", [{ type: "token", text: "Molecula only answers…" }]),
    );

    expect(report).toContain("## Source check\n\nNo check.");
    expect(report).toContain("## Sources\n\nNone.");
    expect(report).toContain("## Tool calls\n\nNone.");
  });

  it("writes its words in German for a German reader and keeps the verdicts as sent", () => {
    const report = checkReport(turnOf("Wie wirkt Ibuprofen?", ANSWERED), de);

    expect(report).toContain("# Molecula-Antwortbericht");
    expect(report).toContain("## Frage\n\nWie wirkt Ibuprofen?");
    expect(report).toContain("2. **unsupported** (Quellen keine, entschieden durch model)");
    expect(report).toContain("   Begründung: No source gives a year.");
    expect(report).toContain('## Werkzeugaufrufe\n\n### search_labels {"query":"ibuprofen"}');
  });
});
