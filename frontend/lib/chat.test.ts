import { afterEach, describe, expect, it, vi } from "vitest";

import { API_URL } from "./api";
import {
  CHAT_FAILED,
  CHAT_UNAVAILABLE,
  type ChatEvent,
  type ChatMessage,
  failureText,
  questionProblem,
  requestMessages,
  streamChat,
} from "./chat";
import { MAX_ANSWER_LENGTH, MAX_MESSAGE_LENGTH, MAX_MESSAGES } from "./chat-limits";
import { de } from "./messages/de";
import { chatFrame, DONE } from "./test-fixtures";

const QUESTION: ChatMessage[] = [{ role: "user", content: "How does imatinib work?" }];

function stubFetch(response: Response) {
  const fetchMock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function collect(messages: ChatMessage[]): Promise<ChatEvent[]> {
  const events: ChatEvent[] = [];
  for await (const event of streamChat(messages)) events.push(event);
  return events;
}

async function failureOf(response: Response): Promise<string> {
  stubFetch(response);
  return failureText(await collect(QUESTION).catch((error: unknown) => error));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("streamChat", () => {
  it("names the model the user picked", async () => {
    const fetchMock = stubFetch(new Response(DONE));

    for await (const event of streamChat(QUESTION, undefined, "google/gemma-4-31b")) void event;

    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string)).toEqual({
      messages: QUESTION,
      model: "google/gemma-4-31b",
    });
  });

  it("names the checker the user picked next to the model", async () => {
    const fetchMock = stubFetch(new Response(DONE));

    for await (const event of streamChat(QUESTION, undefined, "google/gemma-4-31b", "answer")) {
      void event;
    }

    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string)).toEqual({
      messages: QUESTION,
      model: "google/gemma-4-31b",
      checker: "answer",
    });
  });

  it("names a picked checker with the default model too", async () => {
    const fetchMock = stubFetch(new Response(DONE));

    for await (const event of streamChat(QUESTION, undefined, null, "local")) void event;

    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string)).toEqual({
      messages: QUESTION,
      checker: "local",
    });
  });

  it("posts the conversation and yields the events of the stream", async () => {
    const fetchMock = stubFetch(
      new Response(
        chatFrame({ type: "status", message: "Looking up imatinib" }) +
          chatFrame({ type: "tool_call", id: "1", name: "resolve_drug", args: {} }) +
          chatFrame({ type: "token", text: "Imatinib" }) +
          DONE,
      ),
    );

    const events = await collect(QUESTION);

    expect(events.map((event) => event.type)).toEqual(["status", "tool_call", "token", "done"]);
    expect(events[2]).toEqual({ type: "token", text: "Imatinib" });
    expect(fetchMock).toHaveBeenCalledWith(`${API_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ messages: QUESTION }),
      signal: undefined,
    });
  });

  it("says the chat is unavailable when the backend answers 503", async () => {
    const response = Response.json({ detail: "Chat is off: no chat model" }, { status: 503 });

    expect(await failureOf(response)).toBe(CHAT_UNAVAILABLE);
  });

  it("says when to try again when a limit turns the question away", async () => {
    const tooMany =
      "You've asked 10 questions in the last minute, the most Molecula takes. " +
      "Try again in 42 seconds.";
    const budget =
      "Molecula has used up today's budget for the language model. Try again after " +
      "midnight UTC, in 5 hours.";
    const limited = (detail: string, status: number) =>
      Response.json({ detail, retry_after: 42 }, { status, headers: { "Retry-After": "42" } });

    expect(await failureOf(limited(tooMany, 429))).toBe(tooMany);
    expect(await failureOf(limited(budget, 503))).toBe(budget);
  });

  it("shows the backend's reason when a 422 gives one", async () => {
    const detail = "Molecula can't answer questions about doses for you.";

    expect(await failureOf(Response.json({ detail }, { status: 422 }))).toBe(detail);
  });

  it("shows a fixed message for a 422 with validation details", async () => {
    const detail = [{ loc: ["body", "messages"], msg: "too long", type: "value_error" }];

    expect(await failureOf(Response.json({ detail }, { status: 422 }))).toBe(CHAT_FAILED);
  });

  it("shows a fixed message for a server error or a body that isn't JSON", async () => {
    expect(await failureOf(new Response("Internal Server Error", { status: 500 }))).toBe(
      CHAT_FAILED,
    );
    expect(await failureOf(new Response("Bad gateway", { status: 422 }))).toBe(CHAT_FAILED);
  });

  it("shows a fixed message when the backend can't be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    const error = await collect(QUESTION).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(TypeError);
    expect(failureText(error)).toBe(CHAT_FAILED);
  });
});

describe("requestMessages", () => {
  it("keeps the latest messages, ending with the question", () => {
    const conversation: ChatMessage[] = Array.from({ length: 13 }, (_, index) => ({
      role: index % 2 === 0 ? "user" : "assistant",
      content: `message ${index}`,
    }));

    const messages = requestMessages(conversation);

    expect(messages).toHaveLength(MAX_MESSAGES);
    expect(messages[0].content).toBe("message 3");
    expect(messages.at(-1)).toEqual({ role: "user", content: "message 12" });
  });

  it("leaves out the empty answer of a stopped or failed reply", () => {
    const messages = requestMessages([
      { role: "user", content: "How does imatinib work?" },
      { role: "assistant", content: "  " },
      { role: "user", content: "What does it bind to?" },
    ]);

    expect(messages.map((message) => message.role)).toEqual(["user", "user"]);
  });

  it("cuts an answer to the length the backend accepts and trims the text", () => {
    const messages = requestMessages([
      { role: "user", content: " Tell me everything. " },
      { role: "assistant", content: "a".repeat(MAX_ANSWER_LENGTH + 10) },
      { role: "user", content: "Shorter, please." },
    ]);

    expect(messages[0].content).toBe("Tell me everything.");
    expect(messages[1].content).toHaveLength(MAX_ANSWER_LENGTH);
  });
});

describe("questionProblem", () => {
  it("accepts a question up to the length limit, not counting surrounding spaces", () => {
    expect(questionProblem(`  ${"a".repeat(MAX_MESSAGE_LENGTH)}  `)).toBeNull();
  });

  it("says by how much a question is too long", () => {
    expect(questionProblem("a".repeat(MAX_MESSAGE_LENGTH + 1))).toBe(
      "The question is too long: 4,001 of at most 4,000 characters.",
    );
  });

  it("says it in German for a German reader", () => {
    expect(questionProblem("a".repeat(MAX_MESSAGE_LENGTH + 1), de)).toBe(
      "Die Frage ist zu lang: 4.001 von höchstens 4.000 Zeichen.",
    );
  });
});
