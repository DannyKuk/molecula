import { describe, expect, it } from "vitest";

import { CHAT_FAILED } from "./chat";
import { startTurn, type Turn } from "./chat-turn";
import { de } from "./messages/de";
import { CHECKING_ANSWER } from "./source-check";
import {
  ACETAMINOPHEN_NO_COMPLEX,
  COMPARISON_WITH_UNSUPPORTED,
  GLEEVEC_FOUND,
  IMATINIB_COMPLEX,
  IMATINIB_LABELS,
  IMATINIB_TRACE,
  METFORMIN_PROPERTIES,
  METFORMIN_TARGETS,
  TYLENOLL_NOT_SUPPORTED,
} from "./test-tool-results";
import type { RetrievalTrace, Step, ToolRun } from "./tool-cards";
import { callText, type TurnFlowPart, type TurnStep, turnFlow } from "./turn-flow";

const CHECKING = { text: "Checking the question" };
const CHECKED = { text: CHECKING_ANSWER };
const BACKED = { checked: true, claims: [] };

function search(changes: Partial<ToolRun> = {}): Step {
  return {
    text: "Searching the Gleevec label",
    tool: {
      id: "call_1",
      name: "search_labels",
      args: { question: IMATINIB_LABELS.question, drug: "Gleevec", section: "pharmacology" },
      result: IMATINIB_LABELS,
      trace: IMATINIB_TRACE,
      ...changes,
    },
  };
}

function targets(): Step {
  return {
    text: "Finding the targets of metformin",
    tool: {
      id: "call_2",
      name: "get_targets",
      args: { drug: "metformin" },
      result: METFORMIN_TARGETS,
    },
  };
}

function tool(name: string, result: unknown): Step {
  return { text: `Running ${name}`, tool: { id: `call_${name}`, name, args: {}, result } };
}

function answered(steps: Step[], changes: Partial<Turn> = {}): Turn {
  return {
    ...startTurn("How does imatinib work?"),
    state: "done",
    answer: "Imatinib blocks BCR-ABL [1].",
    steps: [CHECKING, ...steps, CHECKED],
    sourceCheck: BACKED,
    category: "ok",
    ...changes,
  };
}

function all(parts: TurnFlowPart[]): TurnStep[] {
  return parts.flatMap((part) => part.steps);
}

/** The first step named `name` by its key: `check`, `decide`, `extract`, `narrow`, `score`,
 * `boost`, `lookup`, `3d`, `write`, `watch` or `check-sources`. */
function step(parts: TurnFlowPart[], name: string): TurnStep {
  const found = all(parts).find(({ key }) => key === name || key.endsWith(`:${name}`));
  if (!found) throw new Error(`No step ${name}`);
  return found;
}

function states(parts: TurnFlowPart[]): string[] {
  return all(parts).map((candidate) => `${candidate.number} ${candidate.state}`);
}

describe("turnFlow", () => {
  it("follows a label search through the guide's steps, each tagged by who did it", () => {
    const flow = turnFlow(answered([search()]));

    expect(flow.map((part) => part.title)).toEqual([null, "Searching the Gleevec label", null]);
    expect(all(flow).map(({ number, who, guide, state }) => [number, who, guide, state])).toEqual([
      ["1", "model", "check-the-question", "done"],
      ["2", "model", "decide-what-to-look-up", "done"],
      ["3", "code", "narrow-to-the-drug", "done"],
      ["4", "embedder", "score-by-meaning", "done"],
      ["5", "code", "boost-and-keep-five", "done"],
      ["6", "model", "write-the-answer", "done"],
      ["7", "code", "watch-for-a-leak", "done"],
      ["8", "model", "check-the-sources", "done"],
    ]);
  });

  it("says the input check may be Jev or the chat model, since no event names it", () => {
    const check = step(turnFlow(answered([search()])), "check");

    expect(check.whoLabel).toBe("Jev or chat model");
    expect(check.outcome).toBe("Sorted as a medicine question, so it went on.");
  });

  it("shows the search's call, filter, similarities and bonus from its events", () => {
    const flow = turnFlow(answered([search()]));

    expect(step(flow, "decide").call).toBe('search_labels(drug="Gleevec", section="pharmacology")');
    expect(step(flow, "narrow").outcome).toBe("Searched “Gleevec” as imatinib: 1 label.");
    expect(step(flow, "score").outcome).toBe(
      `Searched with “${IMATINIB_LABELS.question}”. The 3 closest passages have a similarity of 0.21 to 0.71.`,
    );
    const boost = step(flow, "boost");
    expect(boost.title).toBe("Add the +0.15 and keep the top 2");
    expect(boost.outcome).toBe(
      "2 passages got +0.15; the order stayed the same. 1 passage below the minimum similarity of 0.30 was dropped.",
    );
    expect(boost.ranking?.boost).toBe(0.15);
    expect(
      boost.ranking?.passages.map(({ section, score, after }) => [section, score, after]),
    ).toEqual([
      ["Mechanism of action", 0.71 + 0.15, 1],
      ["Pharmacokinetics", 0.52 + 0.15, 2],
    ]);
  });

  it("shows the answer's citations and the source check's verdict", () => {
    const flow = turnFlow(answered([search()]));

    expect(step(flow, "write").outcome).toBe("Wrote the answer, citing [1].");
    expect(step(flow, "watch").outcome).toBe("The marker never showed up.");
    expect(step(flow, "check-sources").outcome).toBe("The answer states no facts to check.");
  });

  it("moves a passage in the guessed section up by the trace's bonus", () => {
    const trace: RetrievalTrace = {
      ...IMATINIB_TRACE,
      candidates: [
        { ...IMATINIB_TRACE.candidates[0], score: 0.7, in_section_groups: false },
        { ...IMATINIB_TRACE.candidates[1], score: 0.6, in_section_groups: true },
      ],
      section_group_boost: 0.2,
    };

    const boost = step(turnFlow(answered([search({ trace })])), "boost");

    expect(boost.title).toBe("Add the +0.20 and keep the top 2");
    expect(boost.outcome).toBe("1 passage got +0.20; 2 passages changed place.");
    expect(
      boost.ranking?.passages.map(({ section, before, after }) => [section, before, after]),
    ).toEqual([
      ["Pharmacokinetics", 2, 1],
      ["Mechanism of action", 1, 2],
    ]);
  });

  it("keeps the top passages by similarity when the setup gives no section bonus", () => {
    const trace: RetrievalTrace = { ...IMATINIB_TRACE, section_group_boost: 0 };

    const boost = step(turnFlow(answered([search({ trace })])), "boost");

    expect(boost.title).toBe("Keep the top 2");
    expect(boost.line).toBe(
      "This setup gives no section bonus, so the passages stay in order of similarity and code keeps the top 5. No AI is asked.",
    );
    expect(boost.outcome).toBe(
      "Kept 2 passages. 1 passage below the minimum similarity of 0.30 was dropped.",
    );
    expect(boost.ranking?.boost).toBe(0);
    expect(
      boost.ranking?.passages.map(({ section, score, before, after }) => [
        section,
        score,
        before,
        after,
      ]),
    ).toEqual([
      ["Mechanism of action", 0.71, 1, 1],
      ["Pharmacokinetics", 0.52, 2, 2],
    ]);
  });

  it("says nothing of a bonus in a hybrid search when the setup gives none", () => {
    const trace: RetrievalTrace = { ...IMATINIB_TRACE, mode: "hybrid", section_group_boost: 0 };

    const boost = step(turnFlow(answered([search({ trace })])), "boost");

    expect(boost.outcome).toBe(
      "Kept 2 passages. 1 passage below the minimum similarity of 0.30 was dropped.",
    );
  });

  it("marks the lookup steps skipped when the chat model looked nothing up", () => {
    const flow = turnFlow(answered([], { answer: "Hello! Ask me about a medicine." }));

    expect(states(flow)).toEqual([
      "1 done",
      "2 skipped",
      "3 skipped",
      "4 skipped",
      "5 skipped",
      "6 done",
      "7 done",
      "8 done",
    ]);
    expect(step(flow, "decide").outcome).toBe(
      "The chat model answered without looking anything up.",
    );
  });

  it("shows another tool as the call and one store lookup done by code", () => {
    const flow = turnFlow(answered([targets()]));

    expect(flow[1].title).toBe("Finding the targets of metformin");
    expect(flow[1].steps.map(({ number, who, guide }) => [number, who, guide])).toEqual([
      ["2", "model", "decide-what-to-look-up"],
      ["3", "code", null],
    ]);
    expect(step(flow, "decide").call).toBe('get_targets(drug="metformin")');
    expect(step(flow, "lookup").title).toBe("Look it up in the store");
    expect(step(flow, "lookup").outcome).toBe(
      "2 targets: Mitochondrial complex I (NADH dehydrogenase), Glycerol-3-phosphate dehydrogenase, mitochondrial.",
    );
  });

  it("says what each store lookup found", () => {
    const lookup = (name: string, result: unknown) =>
      step(turnFlow(answered([tool(name, result)])), "lookup").outcome;

    expect(lookup("resolve_drug", GLEEVEC_FOUND)).toBe("“Gleevec” is imatinib in the store.");
    expect(lookup("resolve_drug", TYLENOLL_NOT_SUPPORTED)).toBe("Not in the store: Tylenoll.");
    expect(lookup("get_properties", METFORMIN_PROPERTIES)).toBe(
      "metformin: C4H11N5, 129.16 g/mol.",
    );
    expect(lookup("compare_drugs", COMPARISON_WITH_UNSUPPORTED)).toMatch(
      /^The properties of .+, side by side\. Not in the store: /,
    );
  });

  it("adds the 3D view after a structure lookup, drawn by code from the store", () => {
    const flow = turnFlow(answered([tool("get_complex", IMATINIB_COMPLEX)]));

    expect(flow[1].steps.map(({ number, who, guide }) => [number, who, guide])).toEqual([
      ["2", "model", "decide-what-to-look-up"],
      ["3", "code", null],
      ["4", "code", null],
    ]);
    expect(step(flow, "lookup").outcome).toMatch(
      /^A reviewed structure: Imatinib in ABL1 \(BCR-ABL\), PDB 2HYY · Homo sapiens · \d+ hydrogen bonds\.$/,
    );
    expect(step(flow, "3d").title).toBe("Show it in 3D");
    expect(step(flow, "3d").outcome).toBe("The 3D tab shows Imatinib in ABL1 (BCR-ABL).");
  });

  it("shows the molecule alone in 3D when the drug has no reviewed structure", () => {
    const flow = turnFlow(answered([tool("get_complex", ACETAMINOPHEN_NO_COMPLEX)]));

    expect(step(flow, "lookup").outcome).toBe(
      "No reviewed structure of acetaminophen with its target.",
    );
    expect(step(flow, "3d").outcome).toBe(
      "The 3D tab shows the molecule alone, from its stored 3D shape.",
    );
  });

  it("adds no 3D view for a structure lookup that found no drug", () => {
    const flow = turnFlow(answered([tool("get_complex", TYLENOLL_NOT_SUPPORTED)]));

    expect(flow[1].steps.map(({ title }) => title)).toEqual([
      "Decide what to look up",
      "Look it up in the store",
    ]);
  });

  it("numbers the steps in the order this answer ran them, not by the guide", () => {
    const flow = turnFlow(answered([tool("get_complex", IMATINIB_COMPLEX)]));

    expect(all(flow).map(({ number, title }) => `${number} ${title}`)).toEqual([
      "1 Check the question",
      "2 Decide what to look up",
      "3 Look it up in the store",
      "4 Show it in 3D",
      "5 Write the answer",
      "6 Watch for a leaked system prompt",
      "7 Check the answer against the sources",
    ]);
  });

  it("numbers two label searches", () => {
    const second = search({ id: "call_3", args: { question: IMATINIB_LABELS.question } });
    const flow = turnFlow(
      answered([search(), targets(), { ...second, text: "Searching the drug labels" }]),
    );

    expect(flow.map((part) => part.title)).toEqual([
      null,
      "Search 1 of 2 · Searching the Gleevec label",
      "Finding the targets of metformin",
      "Search 2 of 2 · Searching the drug labels",
      null,
    ]);
    expect(new Set(all(flow).map((candidate) => candidate.key)).size).toBe(all(flow).length);
    expect(flow[3].steps.map(({ number }) => number)).toEqual(["8", "9", "10", "11"]);
  });

  it("says a hybrid search merged its rankings by place instead of adding the bonus", () => {
    const flow = turnFlow(answered([search({ trace: { ...IMATINIB_TRACE, mode: "hybrid" } })]));

    const boost = step(flow, "boost");
    expect(boost.title).toBe("Merge the rankings and keep the top 2");
    expect(boost.ranking).toBeUndefined();
    expect(boost.outcome).toContain("the +0.15 only changed the order of the embedding ranking");
    expect(step(flow, "score").outcome).toContain(
      "A keyword search (BM25) ranked the passages as well.",
    );
  });

  it("scores a keyword-only search by code", () => {
    const score = step(
      turnFlow(answered([search({ trace: { ...IMATINIB_TRACE, mode: "bm25" } })])),
      "score",
    );

    expect(score.who).toBe("code");
    expect(score.title).toBe("Score the passages by keywords");
  });

  it("says a search saved before the trace was kept has no details", () => {
    const flow = turnFlow(answered([search({ trace: undefined })]));

    expect(step(flow, "narrow").outcome).toContain("Not recorded");
    expect(step(flow, "score").outcome).toContain("Not recorded");
    expect(step(flow, "boost").outcome).toBe("Kept 2 passages, numbered [1] to [2].");
    expect(step(flow, "boost").ranking).toBeUndefined();
  });

  it("adds the extra call that read the drugs when the chat model named none", () => {
    const trace: RetrievalTrace = { ...IMATINIB_TRACE, filter_source: "model" };
    const flow = turnFlow(
      answered([search({ args: { question: "How does Gleevec work?" }, trace })]),
    );

    const extracted = step(flow, "extract");
    expect(step(flow, "decide").call).toBe('search_labels(question="How does Gleevec work?")');
    expect(extracted.whoLabel).toBe("Jev or chat model");
    expect(extracted.guide).toBe("decide-what-to-look-up");
    expect(extracted.outcome).toBe("Drugs: imatinib. Sections: pharmacology.");
  });

  it("says a search for two drugs searched each on its own", () => {
    const [gleevec] = IMATINIB_TRACE.filter!.drugs;
    const trace: RetrievalTrace = {
      ...IMATINIB_TRACE,
      filter_source: "model",
      filter: {
        ...IMATINIB_TRACE.filter!,
        drugs: [
          { ...gleevec, name: "imatinib" },
          { name: "nilotinib", generic: "nilotinib", set_ids: ["a", "b"], narrowed: false },
        ],
      },
    };
    const flow = turnFlow(answered([search({ args: { section: "pharmacology" }, trace })]));

    expect(step(flow, "narrow").title).toBe("Narrow the search to the drugs");
    expect(step(flow, "narrow").outcome).toBe("Searched imatinib and nilotinib: 3 labels.");
    expect(step(flow, "boost").line).toContain("keeps each drug's top 5");
  });

  it("says a search the tool rejected never ran", () => {
    const rejected = { status: "invalid_arguments", errors: ["section: not a label section"] };
    const flow = turnFlow(answered([search({ result: rejected, trace: undefined })]));

    expect(step(flow, "narrow").outcome).toBe(
      "Rejected and sent back to the chat model as an error, so nothing was searched: section: not a label section",
    );
    expect(step(flow, "score").state).toBe("skipped");
    expect(step(flow, "boost").state).toBe("skipped");
  });

  it("says a search for names Molecula doesn't know found nothing to search", () => {
    const unknown = {
      status: "not_supported",
      drugs: [{ status: "not_supported", query: "Tylenoll", suggestions: [] }],
    };
    const flow = turnFlow(answered([search({ result: unknown })]));

    expect(step(flow, "narrow").outcome).toBe(
      "None of the names is in the store (Tylenoll), so nothing was searched.",
    );
    expect(step(flow, "score").state).toBe("skipped");
  });

  it("shows that the canary fired and the withdrawn answer went unchecked", () => {
    const flow = turnFlow(
      answered([search()], {
        steps: [CHECKING, search()],
        answer: "Molecula stopped this answer.",
        replaced: true,
        sources: [],
        sourceCheck: null,
      }),
    );

    expect(step(flow, "watch").outcome).toBe(
      "The marker showed up, so the answer was replaced with a fixed one before the marker reached you.",
    );
    expect(step(flow, "check-sources").state).toBe("skipped");
    expect(step(flow, "check-sources").outcome).toBe("A withdrawn answer isn't checked.");
  });

  it("shows a fixed answer as the end of the flow", () => {
    const refused = answered([], {
      steps: [CHECKING],
      answer: "Molecula only answers questions about medicines.",
      sources: [],
      sourceCheck: null,
      category: "off_topic",
    });

    const flow = turnFlow(refused);

    expect(step(flow, "check").outcome).toBe(
      "Sorted as off topic, so Molecula gave a fixed answer and nothing else ran.",
    );
    expect(
      states(flow)
        .slice(1)
        .every((line) => line.endsWith("skipped")),
    ).toBe(true);
    expect(step(flow, "decide").outcome).toBeUndefined();
  });

  it("recognises a fixed answer saved before the category was kept", () => {
    const saved = answered([], {
      steps: [CHECKING],
      answer: "Molecula only answers questions about medicines.",
      sources: [],
      sourceCheck: null,
      category: undefined,
    });

    expect(step(turnFlow(saved), "check").outcome).toBe(
      "Molecula gave a fixed answer, so nothing else ran.",
    );
  });

  it("says a possible overdose answer starts with emergency help", () => {
    const flow = turnFlow(answered([search()], { category: "overdose_emergency" }));

    expect(step(flow, "check").outcome).toBe(
      "Sorted as a possible overdose, so the answer starts with emergency help.",
    );
    expect(step(flow, "write").state).toBe("done");
  });

  it("says the source check failed when it gave no verdict", () => {
    const check = step(
      turnFlow(answered([search()], { sourceCheck: { checked: false, claims: [] } })),
      "check-sources",
    );

    expect(check.state).toBe("failed");
    expect(check.outcome).toBe("The check failed, so the answer is shown unchecked.");
  });

  it("counts the facts the source check backed", () => {
    const claim = {
      text: "Imatinib blocks BCR-ABL [1].",
      refs: [1],
      decided_by: "model" as const,
      reason: "",
      held_by: [],
    };
    const sourceCheck = {
      checked: true,
      claims: [
        { ...claim, label: "supported" as const },
        { ...claim, label: "unsupported" as const },
      ],
    };

    expect(step(turnFlow(answered([search()], { sourceCheck })), "check-sources").outcome).toBe(
      "1 of 2 facts backed · 1 sentence isn't in Molecula's sources (underlined).",
    );
  });

  it("marks where a live answer is and what is still to come", () => {
    const live: Turn = {
      ...startTurn("How does imatinib work?"),
      steps: [CHECKING, search({ result: undefined, trace: undefined })],
    };

    expect(states(turnFlow(live))).toEqual([
      "1 done",
      "2 done",
      "3 running",
      "4 waiting",
      "5 waiting",
      "6 waiting",
      "7 waiting",
      "8 waiting",
    ]);
  });

  it("is running the input check before anything else has come", () => {
    const flow = turnFlow({ ...startTurn("How does imatinib work?"), steps: [CHECKING] });

    expect(states(flow)).toEqual(["1 running", "2 waiting", "3 waiting", "4 waiting", "5 waiting"]);
  });

  it("marks where a stopped answer stopped and what it never reached", () => {
    const stopped: Turn = {
      ...startTurn("How does imatinib work?"),
      state: "stopped",
      steps: [CHECKING, search()],
      answer: "Imatinib blocks",
    };

    expect(states(turnFlow(stopped)).slice(-3)).toEqual([
      "6 stopped",
      "7 not_reached",
      "8 not_reached",
    ]);
  });

  it("gives a failed answer's error to the step it failed at", () => {
    const failed: Turn = {
      ...startTurn("How does imatinib work?"),
      state: "failed",
      error: "Molecula couldn't check this question, so it didn't answer it. Try again.",
      steps: [CHECKING],
    };

    const flow = turnFlow(failed);

    expect(step(flow, "check").state).toBe("failed");
    expect(step(flow, "check").outcome).toBe(failed.error);
    expect(step(flow, "check-sources").state).toBe("not_reached");
  });

  it("keeps the lookup undecided while a live answer has only its emergency line", () => {
    const live: Turn = {
      ...startTurn("I took 20 ibuprofen, what happens?"),
      steps: [CHECKING],
      answer: "If you or someone else may have taken too much, call 911 now.\n\n",
    };

    expect(states(turnFlow(live))).toEqual([
      "1 done",
      "2 running",
      "3 waiting",
      "4 waiting",
      "5 waiting",
    ]);
  });
});

describe("callText", () => {
  it("writes the call as the chat model made it", () => {
    expect(
      callText({ id: "1", name: "compare_drugs", args: { drugs: ["ibuprofen", "naproxen"] } }),
    ).toBe('compare_drugs(drugs=["ibuprofen","naproxen"])');
  });

  it("leaves out the arguments the chat model left empty", () => {
    expect(
      callText({
        id: "1",
        name: "search_labels",
        args: { question: "Is imatinib safe in pregnancy?", drug: "imatinib", section: null },
      }),
    ).toBe('search_labels(drug="imatinib")');
  });
});

describe("turnFlow in German", () => {
  it("writes the guide's steps, the tags and the lookups' titles in German", () => {
    const flow = turnFlow(answered([search(), targets()]), de);

    expect(flow.map((part) => part.title)).toEqual([
      null,
      "Durchsuche die Fachinformation von Gleevec",
      "Suche die Zielproteine von metformin",
      null,
    ]);
    const check = step(flow, "check");
    expect([check.title, check.whoLabel, check.outcome]).toEqual([
      "Die Frage prüfen",
      "Jev oder Chatmodell",
      "Als Medikamentenfrage eingeordnet, deshalb ging es weiter.",
    ]);
    expect(step(flow, "lookup").title).toBe("Im Datenbestand nachschlagen");
    expect(step(flow, "write").outcome).toBe("Hat die Antwort geschrieben und [1] zitiert.");
  });

  it("says in German what a label search did, keeping the label's section names", () => {
    const flow = turnFlow(answered([search()]), de);

    expect(step(flow, "narrow").outcome).toBe(
      "Durchsucht: „Gleevec“ als imatinib, 1 Fachinformation.",
    );
    expect(step(flow, "score").outcome).toBe(
      `Gesucht mit „${IMATINIB_LABELS.question}“. Die 3 nächsten Textstellen haben eine Ähnlichkeit von 0.21 bis 0.71.`,
    );
    const boost = step(flow, "boost");
    expect(boost.title).toBe("+0.15 addieren und die besten 2 behalten");
    expect(boost.outcome).toBe(
      "2 Textstellen bekamen +0.15; die Reihenfolge blieb gleich. 1 Textstelle unter der Mindestähnlichkeit von 0.30 wurde verworfen.",
    );
    expect(boost.ranking?.passages.map(({ section }) => section)).toEqual([
      "Mechanism of action",
      "Pharmacokinetics",
    ]);
  });

  it("says in German that a setup without a section bonus keeps the top passages", () => {
    const trace: RetrievalTrace = { ...IMATINIB_TRACE, section_group_boost: 0 };

    const boost = step(turnFlow(answered([search({ trace })]), de), "boost");

    expect(boost.title).toBe("Die besten 2 behalten");
    expect(boost.line).toContain("Diese Instanz vergibt keinen Abschnittsbonus");
  });

  it("names why a question got a fixed answer in German", () => {
    const refused = answered([], {
      steps: [CHECKING],
      answer: "Molecula beantwortet nur Fragen zu Medikamenten.",
      sources: [],
      sourceCheck: null,
      category: "off_topic",
    });

    expect(step(turnFlow(refused, de), "check").outcome).toBe(
      "Als Frage außerhalb des Themas eingeordnet, deshalb gab Molecula eine feste Antwort und sonst lief nichts.",
    );
  });

  it("gives the app's own error in German and the backend's as it came", () => {
    const failed = (error: string): Turn => ({
      ...startTurn("Wie wirkt Imatinib?"),
      state: "failed",
      error,
      steps: [CHECKING],
    });

    expect(step(turnFlow(failed(CHAT_FAILED), de), "check").outcome).toBe(de.chat.failed);
    expect(step(turnFlow(failed("Rate limit reached."), de), "check").outcome).toBe(
      "Rate limit reached.",
    );
  });
});
