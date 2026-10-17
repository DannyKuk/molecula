import { describe, expect, it } from "vitest";

import { startTurn, type Turn } from "./chat-turn";
import {
  conversationCsv,
  conversationJson,
  exportedConversation,
  exportFileName,
} from "./conversation-export";
import { IMATINIB_PASSAGES, IMATINIB_SOURCES } from "./test-fixtures";
import { GLEEVEC_FOUND } from "./test-tool-results";

const ASKED_AT = Date.UTC(2026, 9, 17, 9, 30);
const ANSWERED_AT = Date.UTC(2026, 9, 17, 9, 31);
const EXPORTED_AT = new Date(Date.UTC(2026, 9, 17, 10, 0));

function answeredTurn(question: string, answer: string, changes: Partial<Turn> = {}): Turn {
  return {
    ...startTurn(question),
    answer,
    state: "done",
    askedAt: ASKED_AT,
    answeredAt: ANSWERED_AT,
    ...changes,
  };
}

const IMATINIB_TURN = answeredTurn(
  "How does Gleevec work?",
  "Imatinib inhibits the BCR-ABL tyrosine kinase [1].",
  {
    steps: [
      {
        text: "Looking up Gleevec",
        tool: {
          id: "call_1",
          name: "resolve_drug",
          args: { name: "Gleevec" },
          result: GLEEVEC_FOUND,
        },
      },
    ],
    sources: IMATINIB_SOURCES,
    passages: IMATINIB_PASSAGES,
  },
);

function exported(...turns: Turn[]) {
  return exportedConversation("How does Gleevec work?", turns, EXPORTED_AT);
}

/** Reads CSV the way a spreadsheet does: quoted fields may hold commas, quotes and line breaks. */
function parseCsv(csv: string): string[][] {
  const rows: string[][] = [[]];
  let field = "";
  let quoted = false;
  const endField = () => {
    rows.at(-1)!.push(field);
    field = "";
  };
  for (let i = 0; i < csv.length; i++) {
    const char = csv[i];
    if (quoted && char === '"' && csv[i + 1] === '"') {
      field += '"';
      i++;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (!quoted && char === ",") {
      endField();
    } else if (!quoted && char === "\r" && csv[i + 1] === "\n") {
      endField();
      rows.push([]);
      i++;
    } else {
      field += char;
    }
  }
  endField();
  return rows;
}

describe("conversationJson", () => {
  it("keeps every answer's sources, passages and tool results", () => {
    const json = JSON.parse(conversationJson(exported(IMATINIB_TURN)));

    expect(json.title).toBe("How does Gleevec work?");
    expect(json.exportedAt).toBe("2026-10-17T10:00:00.000Z");
    expect(json.turns[0].sources).toEqual(IMATINIB_SOURCES);
    expect(json.turns[0].passages).toEqual(IMATINIB_PASSAGES);
    expect(json.turns[0].steps[0].tool.result).toEqual(GLEEVEC_FOUND);
    expect(json.turns[0].askedAt).toBe(ASKED_AT);
  });
});

describe("conversationCsv", () => {
  it("writes the question and the answer as rows, with the answer's sources one per line", () => {
    const rows = parseCsv(conversationCsv(exported(IMATINIB_TURN)).slice(1));

    expect(rows).toEqual([
      ["time", "role", "text", "sources"],
      ["2026-10-17T09:30:00.000Z", "user", "How does Gleevec work?", ""],
      [
        "2026-10-17T09:31:00.000Z",
        "assistant",
        "Imatinib inhibits the BCR-ABL tyrosine kinase [1].",
        [
          `[1] Gleevec – Mechanism of action – ${IMATINIB_SOURCES[0].url}`,
          `[2, 3] Gleevec – Pharmacokinetics – ${IMATINIB_SOURCES[1].url}`,
          "[4] PubChem – imatinib – https://pubchem.ncbi.nlm.nih.gov/compound/5291",
        ].join("\n"),
      ],
    ]);
  });

  it("quotes commas, quotes and line breaks in an answer so they stay in one field", () => {
    const answer = 'Take it with food, "as directed".\nSee the label,\r\nsection 2.';

    const csv = conversationCsv(exported(answeredTurn("Food?", answer)));

    expect(csv).toContain('"Take it with food, ""as directed"".\nSee the label,\r\nsection 2."');
    expect(parseCsv(csv.slice(1))[2][2]).toBe(answer);
  });

  it("starts with a byte order mark and ends its rows with CRLF, as spreadsheets expect", () => {
    const csv = conversationCsv(exported(answeredTurn("Hi?", "Hello.")));

    expect(csv.startsWith("\uFEFFtime,role,text,sources\r\n")).toBe(true);
  });

  it("keeps a cell that looks like a formula from running in a spreadsheet", () => {
    const csv = conversationCsv(exported(answeredTurn("=1+1", '=HYPERLINK("http://x")')));

    const [, question, answer] = parseCsv(csv.slice(1));
    expect(question[2]).toBe("'=1+1");
    expect(answer[2]).toBe(`'=HYPERLINK("http://x")`);
  });

  it("leaves the time empty for a turn saved before turns had one, and gives a failed turn's error", () => {
    const failed: Turn = {
      ...startTurn("How does Gleevec work?"),
      state: "failed",
      error: "Something went wrong while answering. Try again.",
    };

    const [, question, answer] = parseCsv(conversationCsv(exported(failed)).slice(1));

    expect(question[0]).toBe("");
    expect(answer).toEqual([
      "",
      "assistant",
      "Something went wrong while answering. Try again.",
      "",
    ]);
  });
});

describe("exportFileName", () => {
  it("names the file after the export day and the title", () => {
    expect(exportFileName(exported(), "csv")).toBe("molecula-2026-10-17-how-does-gleevec-work.csv");
  });

  it("drops accents and keeps a long title short", () => {
    const conversation = exportedConversation(
      "Wie lange wirkt Ibuprofen bei Kopfschmerzen und darf man es mit Kaffee nehmen?",
      [],
      EXPORTED_AT,
    );

    expect(exportFileName(conversation, "json")).toBe(
      "molecula-2026-10-17-wie-lange-wirkt-ibuprofen-bei-kopfschmerzen-und-da.json",
    );
    expect(
      exportFileName(exportedConversation("Wirkt Aleve über Nacht?", [], EXPORTED_AT), "csv"),
    ).toBe("molecula-2026-10-17-wirkt-aleve-uber-nacht.csv");
  });
});
