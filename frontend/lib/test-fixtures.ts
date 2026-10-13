import { vi } from "vitest";

import type { Resolution, Suggestion } from "@/lib/api";
import type { ChatMessage } from "@/lib/chat";

/** The backend's answer for a name outside the supported drugs. */
export function notSupported(query: string, suggestions: Suggestion[] = []): Resolution {
  return {
    query,
    status: "not_supported",
    compound: null,
    matched_alias: null,
    match_kind: null,
    suggestions,
  };
}

/** One server-sent event as `POST /chat` frames it. */
export function chatFrame(event: { type: string } & Record<string, unknown>): string {
  return `event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`;
}

export const DONE = chatFrame({
  type: "done",
  usage: { input_tokens: 0, output_tokens: 0, total_tokens: 0 },
  step_limit_reached: false,
});

/**
 * Replaces `fetch` with a chat backend whose latest stream the test writes one chunk at a time.
 * Like a real fetch, aborting the request breaks its stream.
 */
export function stubChatStream() {
  const encoder = new TextEncoder();
  const streams: ReadableStreamDefaultController<Uint8Array>[] = [];
  const fetchMock = vi.fn(async (_url: string, init: RequestInit) => {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        streams.push(controller);
        init.signal?.addEventListener("abort", () =>
          controller.error(new DOMException("The request was aborted.", "AbortError")),
        );
      },
    });
    return new Response(body, { headers: { "Content-Type": "text/event-stream" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  const latest = () => streams[streams.length - 1];
  return {
    fetchMock,
    send: (chunk: string) => latest().enqueue(encoder.encode(chunk)),
    end: () => latest().close(),
    /** The messages of the latest request. */
    sentMessages: (): ChatMessage[] =>
      JSON.parse(fetchMock.mock.calls[fetchMock.mock.calls.length - 1][1].body as string).messages,
  };
}
