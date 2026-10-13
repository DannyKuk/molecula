import { CHAT_FAILED, type ChatEvent, type ChatMessage, type Source } from "./chat";
import type { Passage } from "./citations";

/**
 * One question and the answer to it, with the steps Molecula took on the way. `sources` is
 * null until the answer's `sources` event arrives, after its last token; `passages` are the
 * label passages the label search returned, by the number the answer cites them with.
 */
export type Turn = {
  question: string;
  answer: string;
  steps: string[];
  state: "answering" | "done" | "stopped" | "failed";
  error?: string;
  sources: Source[] | null;
  disclaimer: string | null;
  passages: Record<number, Passage>;
};

export function startTurn(question: string): Turn {
  return {
    question,
    answer: "",
    steps: [],
    state: "answering",
    sources: null,
    disclaimer: null,
    passages: {},
  };
}

export function applyEvent(turn: Turn, event: ChatEvent): Turn {
  switch (event.type) {
    case "status":
      return { ...turn, steps: [...turn.steps, event.message] };
    case "token":
      return { ...turn, answer: turn.answer + event.text };
    case "tool_result":
      return event.name === "search_labels"
        ? { ...turn, passages: { ...turn.passages, ...passagesOf(event.result) } }
        : turn;
    case "sources":
      return { ...turn, sources: event.sources, disclaimer: event.disclaimer };
    case "done":
      return { ...turn, state: "done" };
    case "error":
      return failTurn(turn, event.message);
    default:
      return turn;
  }
}

function passagesOf(result: unknown): Record<number, Passage> {
  const passages = (result as { passages?: unknown } | null)?.passages;
  if (!Array.isArray(passages)) return {};
  return Object.fromEntries(
    passages
      .filter(
        (passage): passage is Passage =>
          typeof passage?.ref === "number" && typeof passage?.text === "string",
      )
      .map(({ ref, text }) => [ref, { ref, text }]),
  );
}

/** The turn once its stream has ended; a stream that ends without `done` or `error` broke off. */
export function endTurn(turn: Turn): Turn {
  return turn.state === "answering" ? failTurn(turn, CHAT_FAILED) : turn;
}

export function failTurn(turn: Turn, error: string): Turn {
  return { ...turn, state: "failed", error };
}

export function stopTurn(turn: Turn): Turn {
  return { ...turn, state: "stopped" };
}

/** The earlier turns and a new question as the messages of a chat request. */
export function conversationWith(turns: Turn[], question: string): ChatMessage[] {
  return [
    ...turns.flatMap((turn): ChatMessage[] => [
      { role: "user", content: turn.question },
      { role: "assistant", content: turn.answer },
    ]),
    { role: "user", content: question },
  ];
}
