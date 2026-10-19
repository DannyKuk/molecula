import {
  CHAT_FAILED,
  type ChatEvent,
  type ChatMessage,
  type Source,
  type SourceCheck,
} from "./chat";
import type { Passage } from "./citations";
import type { Step } from "./tool-cards";
import type { Usage } from "./usage";

/**
 * One question and the answer to it, with the steps Molecula took on the way and what their
 * tools returned. `sources` is null until the answer's `sources` event arrives, after its last
 * token; `passages` are the label passages the label search returned, by the number the answer
 * cites them with. `sourceCheck` is the source check's verdict, which arrives after `sources`; a
 * fixed answer and a stopped one have none. A question asked while another chat's answer comes in
 * is `queued` until that answer ends. `askedAt` and `answeredAt` are epoch milliseconds; turns
 * saved before they existed have neither. `usage` is what the answer's model calls used, from its
 * `done` event.
 */
export type Turn = {
  question: string;
  answer: string;
  steps: Step[];
  state: "queued" | "answering" | "done" | "stopped" | "failed";
  error?: string;
  sources: Source[] | null;
  passages: Record<number, Passage>;
  sourceCheck: SourceCheck | null;
  askedAt?: number;
  answeredAt?: number;
  usage?: Usage;
};

export function startTurn(question: string): Turn {
  return {
    question,
    answer: "",
    steps: [],
    state: "answering",
    sources: null,
    passages: {},
    sourceCheck: null,
  };
}

export function queueTurn(question: string): Turn {
  return { ...startTurn(question), state: "queued" };
}

export function applyEvent(turn: Turn, event: ChatEvent): Turn {
  switch (event.type) {
    case "status":
      return { ...turn, steps: [...turn.steps, { text: event.message }] };
    case "tool_call":
      return { ...turn, steps: withCall(turn.steps, event) };
    case "token":
      return { ...turn, answer: turn.answer + event.text };
    case "tool_result": {
      const steps = withResult(turn.steps, event.id, event.result);
      return event.name === "search_labels"
        ? { ...turn, steps, passages: { ...turn.passages, ...passagesOf(event.result) } }
        : { ...turn, steps };
    }
    case "sources":
      return { ...turn, sources: event.sources };
    case "source_check":
      return { ...turn, sourceCheck: { checked: event.checked, claims: event.claims } };
    case "done":
      return { ...turn, state: "done", usage: event.usage };
    case "error":
      return failTurn(turn, event.message);
    default:
      return turn;
  }
}

/** The backend sends each tool call right after the step that announces it. */
function withCall(
  steps: Step[],
  call: { id: string; name: string; args: Record<string, unknown> },
): Step[] {
  const last = steps.at(-1);
  if (!last || last.tool) return steps;
  return [
    ...steps.slice(0, -1),
    { ...last, tool: { id: call.id, name: call.name, args: call.args } },
  ];
}

function withResult(steps: Step[], id: string, result: unknown): Step[] {
  return steps.map((step) =>
    step.tool?.id === id ? { ...step, tool: { ...step.tool, result } } : step,
  );
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

/** The turn once its stream was aborted or its question left the line; a finished one stays. */
export function stopTurn(turn: Turn): Turn {
  return turn.state === "answering" || turn.state === "queued"
    ? { ...turn, state: "stopped" }
    : turn;
}

/** Whether the turn's answer is still to come, so its chat takes no other question yet. */
export function pending(turn: Turn | undefined): boolean {
  return turn?.state === "answering" || turn?.state === "queued";
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
