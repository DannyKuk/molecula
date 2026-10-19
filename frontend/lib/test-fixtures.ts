import { vi } from "vitest";

import type { Resolution, Suggestion } from "@/lib/api";
import type { ChatMessage, Source } from "@/lib/chat";
import { type ChatHistory, type Conversation, summaryOf } from "@/lib/chat-history";
import type { Passage } from "@/lib/citations";
import type { Usage } from "@/lib/usage";

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

/** The end of an answer whose model calls used `usage`. */
export function doneFrame(usage: Partial<Usage> = {}): string {
  return chatFrame({
    type: "done",
    usage: { input_tokens: 0, output_tokens: 0, total_tokens: 0, cost_usd: 0, ...usage },
    step_limit_reached: false,
  });
}

export const DONE = doneFrame();

/**
 * Replaces `fetch` with a chat backend whose latest stream the test writes one chunk at a time.
 * Like a real fetch, aborting the request breaks its stream. Each stream starts with `opening`,
 * which reaches the chat as soon as the request is made.
 */
export function stubChatStream(opening = "") {
  const encoder = new TextEncoder();
  const streams: ReadableStreamDefaultController<Uint8Array>[] = [];
  const fetchMock = vi.fn(async (_url: string, init: RequestInit) => {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        streams.push(controller);
        if (opening) controller.enqueue(encoder.encode(opening));
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

/** Matches a question in the conversation, not the printed title that repeats the first one. */
export const IN_CONVERSATION = { selector: "[data-turn] > p" };

const WINDOW_HEIGHT = 800;

/**
 * Gives jsdom, which has no layout, a page to scroll: its height, the window's and the scroll
 * position. `window.scrollTo` moves it, and resize observers hear when the page grows.
 */
export function stubPage() {
  const page = { height: 2000, top: 2000 - WINDOW_HEIGHT };
  const observers = new Set<() => void>();
  const scrollTo = vi.fn(({ top }: ScrollToOptions) => {
    page.top = Math.min(top ?? page.top, page.height - WINDOW_HEIGHT);
  });
  Object.defineProperty(document.documentElement, "scrollHeight", {
    configurable: true,
    get: () => page.height,
  });
  Object.defineProperty(window, "innerHeight", { configurable: true, value: WINDOW_HEIGHT });
  Object.defineProperty(window, "scrollY", { configurable: true, get: () => page.top });
  vi.stubGlobal("scrollTo", scrollTo);
  vi.stubGlobal(
    "ResizeObserver",
    class {
      private readonly notify: () => void;
      constructor(callback: () => void) {
        this.notify = callback;
      }
      observe() {
        observers.add(this.notify);
      }
      disconnect() {
        observers.delete(this.notify);
      }
    },
  );
  return {
    scrollTo,
    /** The reader scrolls the page by `pixels`, up when negative. */
    scrollBy(pixels: number) {
      page.top = Math.max(0, Math.min(page.top + pixels, page.height - WINDOW_HEIGHT));
      window.dispatchEvent(new Event("scroll"));
    },
    /** The page gets `pixels` taller, before its resize observers hear of it. */
    lengthen(pixels: number) {
      page.height += pixels;
    },
    /** The page gets `pixels` taller and its resize observers hear of it. */
    grow(pixels = 300) {
      page.height += pixels;
      observers.forEach((notify) => notify());
    },
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
    ref: 4,
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

/**
 * A `ChatHistory` kept in memory, which copies what it stores as IndexedDB does. A test renders
 * the chat again with the same one to reload the page. With `failing`, every call rejects, as in a
 * browser that refuses storage.
 */
export function memoryHistory({ failing = false } = {}) {
  const stored = new Map<string, Conversation>();
  const bookmarks = { ids: [] as string[] };
  const answer = async <T>(result: () => T): Promise<T> => {
    if (failing) throw new DOMException("The storage is blocked.", "SecurityError");
    return structuredClone(result());
  };
  const history: ChatHistory = {
    list: () => answer(() => [...stored.values()].map(summaryOf)),
    get: (id) => answer(() => stored.get(id)),
    put: (conversation) =>
      answer(() => void stored.set(conversation.id, structuredClone(conversation))),
    delete: (id) => answer(() => void stored.delete(id)),
    bookmarks: () => answer(() => bookmarks.ids),
    putBookmarks: (ids) => answer(() => void (bookmarks.ids = [...ids])),
  };
  return { history, stored, bookmarks };
}
