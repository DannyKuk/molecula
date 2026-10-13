import { vi } from "vitest";

import type { Resolution, Suggestion } from "@/lib/api";
import type { ChatMessage, Source } from "@/lib/chat";
import type { Passage } from "@/lib/citations";

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

const GLEEVEC_URL =
  "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=211ef2da-2868-4a77-8055-1cb2cd78e24b";

function gleevecPassage(ref: number, section: string): Source {
  return {
    kind: "dailymed",
    name: "Gleevec",
    url: GLEEVEC_URL,
    section,
    effective_time: "2026-07-13",
    ref,
  };
}

/** Imatinib's label passages and its PubChem page, as a `sources` event lists them. */
export const IMATINIB_SOURCES: Source[] = [
  gleevecPassage(1, "mechanism_of_action"),
  gleevecPassage(2, "pharmacokinetics"),
  gleevecPassage(3, "pharmacokinetics"),
  {
    kind: "pubchem",
    name: "imatinib",
    url: "https://pubchem.ncbi.nlm.nih.gov/compound/5291",
    section: null,
    effective_time: null,
    ref: null,
  },
];

export const IMATINIB_PASSAGES: Record<number, Passage> = {
  1: {
    ref: 1,
    text: "12.1 Mechanism of Action Imatinib mesylate is a protein-tyrosine kinase inhibitor that inhibits the BCR-ABL tyrosine kinase.",
  },
  2: { ref: 2, text: "Unchanged imatinib accounted for 25% of the dose (5% urine, 20% feces)." },
  3: { ref: 3, text: "12.3 Pharmacokinetics The pharmacokinetics of Gleevec have been evaluated." },
};

/** The `search_labels` tool result with imatinib's passages, shortened to what the chat reads. */
export const IMATINIB_LABEL_SEARCH = chatFrame({
  type: "tool_result",
  id: "call_1",
  name: "search_labels",
  status: "found",
  result: { status: "found", passages: Object.values(IMATINIB_PASSAGES) },
});

export const IMATINIB_SOURCES_EVENT = chatFrame({
  type: "sources",
  sources: IMATINIB_SOURCES,
  unknown_refs: [],
});
