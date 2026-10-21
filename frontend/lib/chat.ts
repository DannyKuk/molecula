import { API_URL, type InputCategory } from "./api";
import { MAX_ANSWER_LENGTH, MAX_MESSAGE_LENGTH, MAX_MESSAGES } from "./chat-limits";
import { readServerSentEvents } from "./sse";
import type { RetrievalTrace } from "./tool-cards";
import type { Usage } from "./usage";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

/** Where a fact comes from: a label passage on DailyMed, or a PubChem, ChEMBL or RCSB page, each
 * cited as `[ref]` (`Source` in `backend/src/molecula/schemas/chat.py`). */
export type Source = {
  kind: string;
  name: string;
  url: string;
  section: string | null;
  effective_time: string | null;
  ref: number | null;
};

/** One claim of the answer and the source check's verdict on it (`CheckedClaim` in
 * `backend/src/molecula/schemas/claims.py`). `reason` is empty unless the model decided;
 * `held_by` names the results that hold a `held_elsewhere` claim it doesn't cite. */
export type CheckedClaim = {
  text: string;
  refs: number[];
  label: "supported" | "held_elsewhere" | "unsupported" | "not_a_claim";
  decided_by: "model" | "unknown_refs" | "no_verdict";
  reason: string;
  held_by: number[];
};

/** The source check's verdict on the whole answer; `checked` is false when the check failed. */
export type SourceCheck = { checked: boolean; claims: CheckedClaim[] };

export type ChatEvent =
  | { type: "status"; message: string }
  | { type: "token"; text: string }
  // The guard withdrew the answer so far, because it repeated the system prompt (#203).
  | { type: "replace_answer"; text: string }
  | { type: "tool_call"; id: string; name: string; args: Record<string, unknown> }
  | { type: "tool_result"; id: string; name: string; status: string | null; result: unknown }
  | { type: "sources"; sources: Source[]; unknown_refs: number[] }
  | ({ type: "source_check" } & SourceCheck)
  // `category` is how the input check sorted the question; null from an agent without a guard.
  | { type: "done"; usage: Usage; step_limit_reached: boolean; category?: InputCategory | null }
  | { type: "error"; message: string }
  | ({ type: "retrieval_trace" } & RetrievalTrace);

export const CHAT_UNAVAILABLE = "The chat is currently unavailable. Try again later.";
export const CHAT_FAILED = "Something went wrong while answering. Try again.";

/** A failure the backend explained, with a message written for the user. */
export class ChatError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ChatError";
  }
}

/** Sends the conversation to `POST /chat` and yields the answer's events as they arrive. */
export async function* streamChat(
  messages: ChatMessage[],
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const response = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ messages }),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new ChatError(await failureMessage(response));
  }
  for await (const { data } of readServerSentEvents(response.body)) {
    yield JSON.parse(data) as ChatEvent;
  }
}

async function failureMessage(response: Response): Promise<string> {
  const body = (await response.json().catch(() => null)) as {
    detail?: unknown;
    retry_after?: unknown;
  } | null;
  const detail = typeof body?.detail === "string" ? body.detail : null;
  // A limit (429, or the day's cost limit as 503) says when to try again; any other 503 means
  // the chat is off, and its detail is written for whoever runs the backend.
  if (detail && typeof body?.retry_after === "number") return detail;
  if (response.status === 503) return CHAT_UNAVAILABLE;
  if (response.status === 422 && detail) return detail;
  return CHAT_FAILED;
}

/** The message to show for a failed answer: the backend's own words when it gave any. */
export function failureText(error: unknown): string {
  return error instanceof ChatError ? error.message : CHAT_FAILED;
}

/**
 * The conversation as the backend accepts it: the latest messages, without the empty answer a
 * stopped or failed reply leaves, and with long answers cut to the length the backend takes.
 */
export function requestMessages(conversation: ChatMessage[]): ChatMessage[] {
  return conversation
    .map(({ role, content }) => ({
      role,
      content: role === "assistant" ? content.trim().slice(0, MAX_ANSWER_LENGTH) : content.trim(),
    }))
    .filter((message) => message.content)
    .slice(-MAX_MESSAGES);
}

/** Why a question can't be sent, or null when it can. A blank question is never sent either. */
export function questionProblem(question: string): string | null {
  const length = question.trim().length;
  if (length <= MAX_MESSAGE_LENGTH) return null;
  return (
    `The question is too long: ${length.toLocaleString("en-US")} of at most ` +
    `${MAX_MESSAGE_LENGTH.toLocaleString("en-US")} characters.`
  );
}
