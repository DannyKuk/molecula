import { CHAT_FAILED, type ChatEvent, type ChatMessage } from "./chat";

/** One question and the answer to it, with the steps Molecula took on the way. */
export type Turn = {
  question: string;
  answer: string;
  steps: string[];
  state: "answering" | "done" | "stopped" | "failed";
  error?: string;
};

export function startTurn(question: string): Turn {
  return { question, answer: "", steps: [], state: "answering" };
}

export function applyEvent(turn: Turn, event: ChatEvent): Turn {
  switch (event.type) {
    case "status":
      return { ...turn, steps: [...turn.steps, event.message] };
    case "token":
      return { ...turn, answer: turn.answer + event.text };
    case "done":
      return { ...turn, state: "done" };
    case "error":
      return failTurn(turn, event.message);
    default:
      return turn;
  }
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
