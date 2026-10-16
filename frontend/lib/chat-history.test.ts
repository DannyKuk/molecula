import { describe, expect, it } from "vitest";

import { type ConversationSummary, groupByDay, reopenedTurns, withTurns } from "./chat-history";
import { startTurn, type Turn } from "./chat-turn";

function doneTurn(question: string, answer: string): Turn {
  return { ...startTurn(question), answer, state: "done" };
}

function summary(id: string, updatedAt: Date): ConversationSummary {
  return { id, title: id, createdAt: updatedAt.getTime(), updatedAt: updatedAt.getTime() };
}

describe("withTurns", () => {
  it("titles a new conversation by its first question", () => {
    const turns = [doneTurn("How does imatinib work?", "It blocks BCR-ABL.")];

    expect(withTurns(undefined, "c1", turns, 1000)).toEqual({
      id: "c1",
      title: "How does imatinib work?",
      turns,
      createdAt: 1000,
      updatedAt: 1000,
    });
  });

  it("keeps a saved conversation's title and start time and moves its last change", () => {
    const saved = withTurns(undefined, "c1", [doneTurn("How does imatinib work?", "")], 1000);
    const renamed = { ...saved, title: "Imatinib" };
    const turns = [...saved.turns, doneTurn("And its side effects?", "Nausea.")];

    expect(withTurns(renamed, "c1", turns, 2000)).toMatchObject({
      title: "Imatinib",
      turns,
      createdAt: 1000,
      updatedAt: 2000,
    });
  });
});

describe("reopenedTurns", () => {
  it("reopens an answer that was streaming when the page closed as stopped", () => {
    const streaming = { ...startTurn("And its side effects?"), answer: "Naus" };
    const done = doneTurn("How does imatinib work?", "It blocks BCR-ABL.");

    expect(reopenedTurns([done, streaming])).toEqual([done, { ...streaming, state: "stopped" }]);
  });
});

describe("groupByDay", () => {
  const now = new Date(2026, 9, 16, 9, 30);

  it("puts the conversations under Today, Yesterday and Earlier, newest first", () => {
    const conversations = [
      summary("last week", new Date(2026, 9, 9, 12, 0)),
      summary("this morning", new Date(2026, 9, 16, 8, 0)),
      summary("just after midnight", new Date(2026, 9, 16, 0, 5)),
      summary("yesterday evening", new Date(2026, 9, 15, 23, 50)),
      summary("two days ago", new Date(2026, 9, 14, 23, 59)),
    ];

    expect(
      groupByDay(conversations, now).map(({ label, conversations }) => [
        label,
        conversations.map((c) => c.id),
      ]),
    ).toEqual([
      ["Today", ["this morning", "just after midnight"]],
      ["Yesterday", ["yesterday evening"]],
      ["Earlier", ["two days ago", "last week"]],
    ]);
  });

  it("leaves out a day without conversations", () => {
    const groups = groupByDay([summary("last week", new Date(2026, 9, 9))], now);

    expect(groups.map((group) => group.label)).toEqual(["Earlier"]);
  });
});
