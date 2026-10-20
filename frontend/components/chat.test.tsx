import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CHAT_FAILED, CHAT_UNAVAILABLE } from "@/lib/chat";
import { MAX_MESSAGE_LENGTH } from "@/lib/chat-limits";
import {
  chatFrame,
  chatScrollArea,
  DONE,
  doneFrame,
  IMATINIB_LABEL_SEARCH,
  IMATINIB_SOURCES_EVENT,
  IN_CONVERSATION,
  stubChatStream,
  stubPage,
} from "@/lib/test-fixtures";
import {
  IBUPROFEN_PROPERTIES,
  IMATINIB_COMPLEX,
  NAPROXEN_PROPERTIES,
  TYLENOLL_NOT_SUPPORTED,
} from "@/lib/test-tool-results";
import type { StructureTarget } from "@/lib/tool-cards";

import { Chat } from "./chat";

// jsdom has no WebGL; the 3D view only needs to be on the page.
vi.mock("./model-status", () => ({ ModelStatus: () => null }));

vi.mock("./structure/structure-panel", () => ({
  StructurePanel: ({ target }: { target: StructureTarget }) => <p>3D view of {target.name}</p>,
}));

let page: ReturnType<typeof stubPage>;

beforeEach(() => {
  page = stubPage();
});

afterEach(() => {
  // Unmounted first: a render that lands after the globals are gone can't find `matchMedia`.
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

function questionBox(): HTMLTextAreaElement {
  return screen.getByRole("textbox", { name: "Ask about a medicine" });
}

function type(text: string) {
  fireEvent.change(questionBox(), { target: { value: text } });
}

function pressEnter(options: { shiftKey?: boolean } = {}) {
  fireEvent.keyDown(questionBox(), { key: "Enter", ...options });
}

function askQuestion(text: string) {
  type(text);
  pressEnter();
}

function conversationText(): string {
  return document.querySelector('ol[aria-label="Conversation"]')?.textContent ?? "";
}

function conversation(): HTMLElement {
  return screen.getByRole("list", { name: "Conversation" });
}

function evidence(): HTMLElement {
  return screen.getByRole("complementary", { name: "Evidence" });
}

/** The evidence panel's open tab, with its count: "Sources4". */
function selectedTab(): string | null {
  return within(evidence()).getByRole("tab", { selected: true }).textContent;
}

function panelHeading(): string | null {
  return within(evidence()).getByRole("heading", { level: 2 }).textContent;
}

function liveAnswerButton(): HTMLElement | null {
  return within(evidence()).queryByRole("button", { name: "Live answer" });
}

/** The question of the turn the chat marks as being read. */
function readTurnInChat(): string | null | undefined {
  return conversation().querySelector("[data-turn][aria-current] h2")?.textContent;
}

/** Puts the conversation's turns this far down the chat, so the reader can scroll to them. */
function stubTurnTops(tops: number[]) {
  const rect = HTMLElement.prototype.getBoundingClientRect;
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (
    this: HTMLElement,
  ) {
    if (!this.hasAttribute("data-turn")) return rect.call(this);
    const index = Array.from(this.parentElement?.children ?? []).indexOf(this);
    return { top: tops[index] - chatScrollArea().scrollTop } as DOMRect;
  });
}

async function streamed(send: () => void) {
  await act(async () => send());
}

/** Asks about Gleevec and then metformin, each answered after one step. */
async function answerTwice(stream: ReturnType<typeof stubChatStream>) {
  askQuestion("How does Gleevec work?");
  await streamed(() => stream.send(status("Looking up Gleevec") + token("It blocks BCR-ABL.")));
  await streamed(() => stream.send(DONE));
  askQuestion("What is metformin for?");
  await streamed(() => stream.send(status("Looking up metformin") + token("It lowers sugar.")));
  await streamed(() => stream.send(DONE));
}

function token(text: string): string {
  return chatFrame({ type: "token", text });
}

function status(message: string): string {
  return chatFrame({ type: "status", message });
}

const IMATINIB_IN_3D =
  status("Getting the complex of imatinib") +
  chatFrame({ type: "tool_call", id: "call_1", name: "get_complex", args: { drug: "imatinib" } }) +
  chatFrame({
    type: "tool_result",
    id: "call_1",
    name: "get_complex",
    status: "found",
    result: IMATINIB_COMPLEX,
  });

const TYLENOLL_LOOKUP =
  status("Looking up Tylenoll") +
  chatFrame({ type: "tool_call", id: "call_1", name: "resolve_drug", args: { name: "Tylenoll" } }) +
  chatFrame({
    type: "tool_result",
    id: "call_1",
    name: "resolve_drug",
    status: "not_supported",
    result: TYLENOLL_NOT_SUPPORTED,
  });

const DID_YOU_MEAN_TYLENOL = "Did you mean Tylenol (acetaminophen)?";

describe("Chat", () => {
  it("streams the answer's tokens into the conversation as they arrive", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(token("Imatinib ")));
    expect(await screen.findByText("Imatinib")).toBeDefined();

    await streamed(() => stream.send(token("blocks BCR-ABL [1].")));
    await streamed(() => stream.send(DONE));

    expect(await screen.findByText("Imatinib blocks BCR-ABL [1].")).toBeDefined();
    expect(screen.getByText("How does Gleevec work?", IN_CONVERSATION)).toBeDefined();
    expect(stream.sentMessages()).toEqual([{ role: "user", content: "How does Gleevec work?" }]);
  });

  it("shows the current step under the question and every step live in the panel", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    expect(within(conversation()).getByText("Thinking…")).toBeDefined();
    await streamed(() => stream.send(status("Looking up Gleevec")));
    await streamed(() => stream.send(status("Searching the imatinib label")));

    expect(within(conversation()).getByText("Searching the imatinib label…")).toBeDefined();
    const progress = within(evidence()).getByRole("list", { name: "Progress" });
    expect(
      within(progress)
        .getAllByRole("listitem")
        .map((item) => item.textContent),
    ).toEqual(["Looking up Gleevec", "Searching the imatinib label"]);
    expect(within(conversation()).queryByRole("list", { name: "Progress" })).toBeNull();

    await streamed(() => stream.send(token("Imatinib blocks BCR-ABL.") + DONE));

    expect(within(conversation()).queryByText(/Searching the imatinib label/)).toBeNull();
    expect(within(conversation()).getByRole("button", { name: "2 steps" })).toBeDefined();
    expect(within(conversation()).getByText("no 3D")).toBeDefined();
  });

  it("shows the newest answer in the panel and an earlier one from its pills", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("Show imatinib bound to its target in 3D.");
    await streamed(() => stream.send(IMATINIB_IN_3D + token("It sits in the ATP pocket.") + DONE));
    await screen.findByText("It sits in the ATP pocket.");
    askQuestion("What is metformin for?");
    await streamed(() => stream.send(status("Looking up metformin")));

    expect(within(evidence()).getByRole("heading", { level: 2 }).textContent).toBe("Answer 2 of 2");
    expect(selectedTab()).toBe("Steps1");

    await streamed(() => stream.send(token("It lowers blood sugar.") + DONE));
    fireEvent.click(within(conversation()).getByRole("button", { name: "3D · 2HYY" }));

    expect(within(evidence()).getByRole("heading", { level: 2 }).textContent).toBe("Answer 1 of 2");
    expect(within(evidence()).getByText("3D view of imatinib")).toBeDefined();

    fireEvent.click(within(evidence()).getByRole("button", { name: "Next answer" }));
    expect(selectedTab()).toBe("Sources");
  });

  it("opens the sources a citation chip cites in the panel, highlighted", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does imatinib work?");
    await streamed(() =>
      stream.send(IMATINIB_LABEL_SEARCH + token("It blocks BCR-ABL [2].") + IMATINIB_SOURCES_EVENT),
    );
    await streamed(() => stream.send(DONE));
    fireEvent.click(screen.getByRole("button", { name: "Sources: Gleevec · Pharmacokinetics" }));

    expect(selectedTab()).toBe("Sources4");
    const cards = within(evidence()).getAllByRole("listitem");
    expect(cards.map((card) => card.hasAttribute("data-highlighted"))).toEqual([
      false,
      true,
      false,
      false,
    ]);
  });

  it("follows the turn the reader scrolls to and marks it in the chat", async () => {
    const stream = stubChatStream();
    render(<Chat />);
    await answerTwice(stream);
    stubTurnTops([100, 1300]);

    act(() => page.scrollBy(-700));
    expect(panelHeading()).toBe("Answer 1 of 2");
    expect(readTurnInChat()).toBe("How does Gleevec work?");

    act(() => page.scrollBy(500));
    expect(panelHeading()).toBe("Answer 2 of 2");
    expect(readTurnInChat()).toBe("What is metformin for?");
  });

  it("scrolls the chat to the answer the panel steps to", async () => {
    const stream = stubChatStream();
    render(<Chat />);
    await answerTwice(stream);
    stubTurnTops([100, 1300]);
    page.scrollTo.mockClear();

    await act(async () =>
      fireEvent.click(within(evidence()).getByRole("button", { name: "Previous answer" })),
    );

    expect(page.scrollTo).toHaveBeenCalledExactlyOnceWith({ top: 84 });
    expect(panelHeading()).toBe("Answer 1 of 2");
    expect(readTurnInChat()).toBe("How does Gleevec work?");

    fireEvent.click(within(evidence()).getByRole("tab", { name: /Steps/ }));
    expect(page.scrollTo).toHaveBeenCalledOnce();
  });

  it("stays on the answer the reader is on while the chat follows the live one", async () => {
    const stream = stubChatStream();
    render(<Chat />);
    await answerTwice(stream);
    stubTurnTops([100, 1300, 1900]);
    askQuestion("What does sildenafil bind to?");
    await streamed(() => stream.send(status("Looking up sildenafil")));

    act(() => page.scrollBy(-1000));
    expect(panelHeading()).toBe("Answer 1 of 3");
    act(() => page.scrollBy(1000));
    expect(panelHeading()).toBe("Answer 3 of 3");
    expect(liveAnswerButton()).toBeNull();

    fireEvent.click(within(conversation()).getAllByRole("button", { name: "1 step" })[1]);
    page.grow();
    await streamed(() => stream.send(token("It blocks PDE5.")));
    expect(panelHeading()).toBe("Answer 2 of 3");

    page.scrollTo.mockClear();
    fireEvent.click(within(evidence()).getByRole("button", { name: "Live answer" }));
    expect(panelHeading()).toBe("Answer 3 of 3");
    expect(selectedTab()).toBe("Steps1");
    expect(page.scrollTo).toHaveBeenCalledExactlyOnceWith({
      top: chatScrollArea().scrollHeight,
    });
    expect(liveAnswerButton()).toBeNull();
  });

  it("opens the 3D tab once, marked new, when the live answer's structure arrives", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("Show imatinib bound to its target in 3D.");
    await streamed(() => stream.send(IMATINIB_IN_3D));
    expect(selectedTab()).toBe("3D, new");
    expect(within(evidence()).getByText("3D view of imatinib")).toBeDefined();

    fireEvent.click(within(evidence()).getByRole("tab", { name: /Steps/ }));
    await streamed(() => stream.send(token("It sits in the ATP pocket.")));
    expect(selectedTab()).toBe("Steps1");
  });

  it("opens the 3D tab when the reader comes back to a live answer whose structure arrived", async () => {
    const stream = stubChatStream();
    render(<Chat />);
    await answerTwice(stream);

    askQuestion("Show imatinib bound to its target in 3D.");
    await streamed(() => stream.send(status("Looking up imatinib")));
    fireEvent.click(within(conversation()).getAllByRole("button", { name: "1 step" })[0]);
    await streamed(() => stream.send(IMATINIB_IN_3D));
    expect(panelHeading()).toBe("Answer 1 of 3");
    expect(selectedTab()).toBe("Steps1");

    fireEvent.click(within(evidence()).getByRole("button", { name: "Live answer" }));
    expect(panelHeading()).toBe("Answer 3 of 3");
    expect(selectedTab()).toBe("3D, new");
  });

  it("opens the panel as a sheet from the pills on a phone", async () => {
    page = stubPage({ phone: true });
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(status("Looking up Gleevec") + token("It blocks BCR-ABL.")));
    await streamed(() => stream.send(DONE));
    expect(screen.queryByRole("complementary", { name: "Evidence" })).toBeNull();
    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "1 step" }));

    const sheet = await screen.findByRole("dialog", { name: "Evidence" });
    expect(within(sheet).getByText("Looking up Gleevec")).toBeDefined();
    fireEvent.click(within(sheet).getByRole("button", { name: "Close" }));
    expect(screen.queryByText("Looking up Gleevec")).toBeNull();
  });

  describe("question navigator", () => {
    function questions(): HTMLElement {
      return screen.getByRole("navigation", { name: "Questions in this chat" });
    }

    /** The question the navigator marks as being read. */
    function readDash(): string | null | undefined {
      return questions().querySelector("button[aria-current]")?.getAttribute("aria-label");
    }

    it("has a dash per question once there are two, and marks the one being read", async () => {
      const stream = stubChatStream();
      render(<Chat />);
      askQuestion("How does Gleevec work?");
      await streamed(() => stream.send(token("It blocks BCR-ABL.") + DONE));
      expect(screen.queryByRole("navigation", { name: "Questions in this chat" })).toBeNull();

      askQuestion("What is metformin for?");
      await streamed(() => stream.send(token("It lowers sugar.") + DONE));
      expect(
        within(questions())
          .getAllByRole("button")
          .map((dash) => dash.ariaLabel),
      ).toEqual(["Question 1: How does Gleevec work?", "Question 2: What is metformin for?"]);
      expect(readDash()).toBe("Question 2: What is metformin for?");

      stubTurnTops([100, 1300]);
      act(() => page.scrollBy(-700));
      expect(readDash()).toBe("Question 1: How does Gleevec work?");
    });

    it("jumps to a question from its dash and opens its answer", async () => {
      const stream = stubChatStream();
      render(<Chat />);
      await answerTwice(stream);
      stubTurnTops([100, 1300]);
      page.scrollTo.mockClear();

      fireEvent.click(within(questions()).getByRole("button", { name: /^Question 1:/ }));

      expect(page.scrollTo).toHaveBeenCalledExactlyOnceWith({ top: 84 });
      expect(panelHeading()).toBe("Answer 1 of 2");
      expect(readTurnInChat()).toBe("How does Gleevec work?");
      expect(readDash()).toBe("Question 1: How does Gleevec work?");
    });

    it("jumps to a question from the list of questions", async () => {
      const stream = stubChatStream();
      render(<Chat />);
      await answerTwice(stream);
      stubTurnTops([100, 1300]);

      fireEvent.click(within(questions()).getByText("How does Gleevec work?"));

      expect(panelHeading()).toBe("Answer 1 of 2");
    });

    it("keeps the tab the reader picked when jumping to the answer the panel shows", async () => {
      const stream = stubChatStream();
      render(<Chat />);
      await answerTwice(stream);
      stubTurnTops([100, 1300]);
      fireEvent.click(within(evidence()).getByRole("tab", { name: /Steps/ }));
      page.scrollTo.mockClear();

      fireEvent.click(within(questions()).getByRole("button", { name: /^Question 2:/ }));

      expect(page.scrollTo).toHaveBeenCalledOnce();
      expect(selectedTab()).toBe("Steps1");
    });

    it("marks the dash of the answer coming in", async () => {
      const stream = stubChatStream();
      render(<Chat />);
      await answerTwice(stream);

      askQuestion("What does sildenafil bind to?");
      await streamed(() => stream.send(status("Looking up sildenafil")));
      const live = () => questions().querySelector("button[data-live]")?.ariaLabel;
      expect(live()).toBe("Question 3: What does sildenafil bind to?");

      await streamed(() => stream.send(DONE));
      expect(live()).toBeUndefined();
    });

    it("follows the reader on a phone too, where the chat no longer shares the page's scroll", async () => {
      page = stubPage({ phone: true });
      const stream = stubChatStream();
      render(<Chat />);
      await answerTwice(stream);
      stubTurnTops([100, 1300]);

      act(() => page.scrollBy(-700));

      expect(readDash()).toBe("Question 1: How does Gleevec work?");
      expect(screen.queryByRole("dialog")).toBeNull();
    });
  });

  it("opens a step into what its tool returned, and merges property lookups when done", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("Compare ibuprofen and naproxen");
    for (const [id, drug, result] of [
      ["call_1", "ibuprofen", IBUPROFEN_PROPERTIES],
      ["call_2", "naproxen", NAPROXEN_PROPERTIES],
    ] as const) {
      await streamed(() =>
        stream.send(
          status(`Getting the properties of ${drug}`) +
            chatFrame({ type: "tool_call", id, name: "get_properties", args: { drug } }) +
            chatFrame({ type: "tool_result", id, name: "get_properties", status: "found", result }),
        ),
      );
    }

    const live = await screen.findByRole("list", { name: "Progress" });
    expect(
      within(live)
        .getAllByRole("button")
        .map((card) => card.textContent),
    ).toEqual([
      "Getting the properties of ibuprofenC13H18O2 · 206.28 g/mol",
      "Getting the properties of naproxenC14H14O3 · 230.26 g/mol",
    ]);

    await streamed(() => stream.send(token("Both are NSAIDs.") + DONE));
    fireEvent.click(await screen.findByRole("button", { name: "1 step" }));
    const card = screen.getByRole("button", {
      name: /Getting the properties of ibuprofen, naproxen/,
    });
    fireEvent.click(card);

    expect(
      within(card.parentElement!)
        .getAllByRole("columnheader")
        .map((header) => header.textContent),
    ).toEqual(["ibuprofen", "naproxen"]);
  });

  it("parses the events it doesn't show yet without breaking the answer", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    await streamed(() =>
      stream.send(
        chatFrame({ type: "retrieval_trace", tool_call_id: "1", question: "x", candidates: [] }) +
          token("Imatinib.") +
          chatFrame({ type: "sources", sources: [], unknown_refs: [] }) +
          DONE,
      ),
    );

    expect(await screen.findByText("Imatinib.")).toBeDefined();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows an error event with a retry that asks the same question again", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(token("Imatinib")));
    await streamed(() =>
      stream.send(chatFrame({ type: "error", message: "The chat model timed out. Try again." })),
    );

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("The chat model timed out. Try again.");
    expect(screen.getByText("Imatinib")).toBeDefined();

    fireEvent.click(within(alert).getByRole("button", { name: "Try again" }));
    await streamed(() => stream.send(token("Imatinib blocks BCR-ABL.") + DONE));

    expect(await screen.findByText("Imatinib blocks BCR-ABL.")).toBeDefined();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getAllByText("How does Gleevec work?", IN_CONVERSATION)).toHaveLength(1);
    expect(stream.sentMessages()).toEqual([{ role: "user", content: "How does Gleevec work?" }]);
  });

  it("shows a readable message with a retry when the backend can't be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<Chat />);

    askQuestion("How does Gleevec work?");

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(CHAT_FAILED);
    expect(within(alert).getByRole("button", { name: "Try again" })).toBeDefined();
  });

  it("says the chat is unavailable when the backend answers 503", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 503 })));
    render(<Chat />);

    askQuestion("How does Gleevec work?");

    expect((await screen.findByRole("alert")).textContent).toContain(CHAT_UNAVAILABLE);
  });

  it("shows how long to wait when the backend answers 429", async () => {
    const detail =
      "You've asked 10 questions in the last minute, the most Molecula takes. " +
      "Try again in 42 seconds.";
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          Response.json(
            { detail, retry_after: 42 },
            { status: 429, headers: { "Retry-After": "42" } },
          ),
        ),
    );
    render(<Chat />);

    askQuestion("How does Gleevec work?");

    expect((await screen.findByRole("alert")).textContent).toContain("Try again in 42 seconds.");
  });

  it("treats a stream that breaks off before it is done as a failure", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(token("Imatinib")));
    await streamed(() => stream.end());

    expect((await screen.findByRole("alert")).textContent).toContain(CHAT_FAILED);
  });

  it("stops the answer on Stop and keeps what arrived", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(token("Imatinib blocks")));
    await screen.findByText("Imatinib blocks");
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));

    expect(await screen.findByText("Stopped.")).toBeDefined();
    expect(screen.getByText("Imatinib blocks")).toBeDefined();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("button", { name: "Send" })).toBeDefined();
  });

  it("shows what each answer used, and the chat's total in the header", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    const first = doneFrame({ total_tokens: 3210, cost_usd: 0.0021 });
    await streamed(() => stream.send(token("It blocks BCR-ABL.") + first));
    await screen.findByText("3,210 tokens · $0.0021");
    askQuestion("What else does it bind?");
    const second = doneFrame({ total_tokens: 1790, cost_usd: 0.0009 });
    await streamed(() => stream.send(token("Also KIT.") + second));

    expect(await screen.findByText("1,790 tokens · $0.0009")).toBeDefined();
    expect(screen.getByText("This chat: 5,000 tokens · $0.003")).toBeDefined();
  });

  it("sends the earlier turns with the next question", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(token("It blocks BCR-ABL.") + DONE));
    await screen.findByText("It blocks BCR-ABL.");
    askQuestion("What else does it bind?");

    expect(stream.fetchMock).toHaveBeenCalledTimes(2);
    expect(stream.sentMessages()).toEqual([
      { role: "user", content: "How does Gleevec work?" },
      { role: "assistant", content: "It blocks BCR-ABL." },
      { role: "user", content: "What else does it bind?" },
    ]);
  });

  it("does not send an empty question", () => {
    const stream = stubChatStream();
    render(<Chat />);

    pressEnter();
    type("   ");
    pressEnter();

    expect(stream.fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole<HTMLButtonElement>("button", { name: "Send" }).disabled).toBe(true);
  });

  it("does not send a question over the length limit and says why", () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("a".repeat(MAX_MESSAGE_LENGTH + 1));

    expect(stream.fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toBe(
      "The question is too long: 4,001 of at most 4,000 characters.",
    );
    expect(screen.getByRole<HTMLButtonElement>("button", { name: "Send" }).disabled).toBe(true);
    expect(questionBox().getAttribute("aria-invalid")).toBe("true");
  });

  it("starts a new line on Shift+Enter instead of sending", () => {
    const stream = stubChatStream();
    render(<Chat />);

    type("How does Gleevec work?");
    pressEnter({ shiftKey: true });

    expect(stream.fetchMock).not.toHaveBeenCalled();
  });

  it("asks the question it was opened with once", async () => {
    const stream = stubChatStream();
    render(<Chat initialQuestion="How does imatinib work?" />);

    expect(await screen.findByText("How does imatinib work?", IN_CONVERSATION)).toBeDefined();
    expect(stream.fetchMock).toHaveBeenCalledTimes(1);
    expect(stream.sentMessages()).toEqual([{ role: "user", content: "How does imatinib work?" }]);
  });

  it("keeps answering the question it was opened with when React runs effects twice", async () => {
    const stream = stubChatStream();
    render(
      <StrictMode>
        <Chat initialQuestion="How does imatinib work?" />
      </StrictMode>,
    );

    await act(async () => {});
    expect(screen.getByRole("button", { name: "Stop" })).toBeDefined();
    expect(screen.queryByText("Stopped.")).toBeNull();
    await streamed(() => stream.send(token("Imatinib blocks BCR-ABL.") + DONE));

    expect(await screen.findByText("Imatinib blocks BCR-ABL.")).toBeDefined();
    expect(screen.getAllByText("How does imatinib work?", IN_CONVERSATION)).toHaveLength(1);
    expect(screen.queryByText("Stopped.")).toBeNull();
  });

  it("keeps the disclaimer in view and shows example questions on the empty chat", () => {
    render(<Chat />);

    expect(screen.getByText(/It is not medical advice/)).toBeDefined();
    expect(screen.getByRole("button", { name: "How does imatinib work?" })).toBeDefined();
  });

  it("sends an example question from the empty chat when it is clicked", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    fireEvent.click(screen.getByRole("button", { name: "How does imatinib work?" }));

    expect(stream.sentMessages()).toEqual([{ role: "user", content: "How does imatinib work?" }]);
    expect(await screen.findByRole("list", { name: "Conversation" })).toBeDefined();
  });

  it("turns the answer's citations into source chips once its sources arrive", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does imatinib work?");
    await streamed(() => stream.send(IMATINIB_LABEL_SEARCH + token("It blocks BCR-ABL [1][2].")));
    expect(await screen.findByText("It blocks BCR-ABL [1][2].")).toBeDefined();
    expect(screen.queryByText(/Data provided by the U.S. Food and Drug Administration/)).toBeNull();

    await streamed(() => stream.send(IMATINIB_SOURCES_EVENT + DONE));

    expect(
      await screen.findByRole("button", {
        name: "Sources: Gleevec · Mechanism of action, Gleevec · Pharmacokinetics",
      }),
    ).toBeDefined();
    expect(screen.queryByText(/\[1\]\[2\]/)).toBeNull();
    expect(screen.getByRole("link", { name: "openFDA" })).toBeDefined();
  });

  it("underlines what the sources don't back once the source check arrives", async () => {
    const stream = stubChatStream();
    const { container } = render(<Chat />);

    askQuestion("How does imatinib work?");
    await streamed(() =>
      stream.send(
        IMATINIB_LABEL_SEARCH +
          token("It blocks BCR-ABL [1]. It was approved in 2001.") +
          IMATINIB_SOURCES_EVENT +
          status("Checking the answer against the sources"),
      ),
    );
    expect(container.querySelector("mark")).toBeNull();
    expect(screen.getByRole("status").textContent).toBe("Checking the answer against the sources…");

    await streamed(() =>
      stream.send(
        chatFrame({
          type: "source_check",
          checked: true,
          claims: [
            {
              text: "It blocks BCR-ABL [1].",
              refs: [1],
              label: "supported",
              decided_by: "model",
              reason: "",
            },
            {
              text: "It was approved in 2001.",
              refs: [],
              label: "unsupported",
              decided_by: "model",
              reason: "Uncited.",
            },
          ],
        }) + DONE,
      ),
    );

    expect(container.querySelector("mark")?.textContent).toBe("It was approved in 2001.");
    expect(screen.getByRole("status").textContent).toMatch(/1 of 2 facts backed/);
  });

  it("opens the help guide from the ? button and sends an example asked from it", async () => {
    const stream = stubChatStream();
    render(<Chat />);
    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(token("It blocks BCR-ABL.") + DONE));
    await screen.findByText("It blocks BCR-ABL.");

    fireEvent.click(screen.getByRole("button", { name: "Help" }));
    const guide = screen.getByRole("dialog", { name: "How to use Molecula" });
    fireEvent.click(within(guide).getByRole("button", { name: "What does sildenafil bind to?" }));

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(stream.sentMessages().at(-1)).toEqual({
      role: "user",
      content: "What does sildenafil bind to?",
    });
  });

  it("scrolls to the end of the chat once the sent question is on it, each time one is sent", async () => {
    const stream = stubChatStream();
    const conversationWhenScrolled: string[] = [];
    page.scrollTo.mockImplementation(() => {
      conversationWhenScrolled.push(conversationText());
    });
    render(<Chat />);
    expect(page.scrollTo).not.toHaveBeenCalled();

    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(token("It blocks BCR-ABL.") + DONE));
    await screen.findByText("It blocks BCR-ABL.");
    fireEvent.click(screen.getByRole("button", { name: "Help" }));
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "What does sildenafil bind to?",
      }),
    );

    expect(conversationWhenScrolled).toHaveLength(3);
    expect(conversationWhenScrolled[0]).toContain("How does Gleevec work?");
    expect(conversationWhenScrolled[1]).toContain("It blocks BCR-ABL.");
    expect(conversationWhenScrolled[2]).toContain("What does sildenafil bind to?");
    expect(page.scrollTo).toHaveBeenLastCalledWith({ top: chatScrollArea().scrollHeight });
  });

  it("scrolls to the end of the chat again on Retry", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(chatFrame({ type: "error", message: "Timed out." })));
    const retry = within(await screen.findByRole("alert")).getByRole("button", {
      name: "Try again",
    });
    page.scrollTo.mockClear();
    fireEvent.click(retry);

    expect(page.scrollTo).toHaveBeenCalledOnce();
  });

  it("scrolls to the question it was opened with", async () => {
    stubChatStream();
    render(<Chat initialQuestion="How does imatinib work?" />);

    await screen.findByText("How does imatinib work?", IN_CONVERSATION);
    expect(page.scrollTo).toHaveBeenCalledTimes(1);
  });

  it("doesn't scroll for a question it ignores while answering", async () => {
    stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    await screen.findByRole("button", { name: "Stop" });
    fireEvent.click(screen.getByRole("button", { name: "Help" }));
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "What does sildenafil bind to?",
      }),
    );

    expect(conversationText()).not.toContain("What does sildenafil bind to?");
    expect(page.scrollTo).toHaveBeenCalledTimes(1);
  });

  it("follows the answer to the end of the chat while it streams in", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(token("Imatinib blocks")));
    page.scrollTo.mockClear();
    page.grow(300);

    expect(page.scrollTo).toHaveBeenCalledExactlyOnceWith({ top: 2300 });
  });

  it("stops following when the reader scrolls up, and follows again back at the end", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(token("Imatinib blocks")));
    page.scrollTo.mockClear();
    page.scrollBy(-200);
    page.grow();
    expect(page.scrollTo).not.toHaveBeenCalled();

    page.scrollBy(1000);
    page.grow();
    expect(page.scrollTo).toHaveBeenCalledOnce();
  });

  it("stops following when the reader scrolls up just after the chat followed", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(token("Imatinib blocks")));
    page.grow();
    page.scrollTo.mockClear();
    page.scrollBy(-100);
    page.grow();

    expect(page.scrollTo).not.toHaveBeenCalled();
  });

  it("keeps following when a scroll event lands just after the chat grew", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(token("Imatinib blocks")));
    page.scrollTo.mockClear();
    page.lengthen(500);
    page.scrollBy(0);
    page.grow();

    expect(page.scrollTo).toHaveBeenCalledOnce();
  });

  it("keeps following an answer that looked up a 3D view, which shows in the panel", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("Show imatinib bound to its target in 3D.");
    await streamed(() => stream.send(IMATINIB_IN_3D + token("Imatinib sits in the ATP pocket.")));
    page.scrollTo.mockClear();
    page.grow();

    expect(page.scrollTo).toHaveBeenCalledOnce();
  });

  it("scrolls to the end once more when the answer is done, so its sources are in view", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(token("It blocks BCR-ABL.")));
    page.scrollTo.mockClear();
    await streamed(() => stream.send(DONE));

    expect(page.scrollTo).toHaveBeenCalledOnce();
  });

  it("doesn't scroll at the end of the answer when the reader scrolled up", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(token("It blocks BCR-ABL.")));
    page.scrollBy(-200);
    page.scrollTo.mockClear();
    await streamed(() => stream.send(DONE));

    expect(page.scrollTo).not.toHaveBeenCalled();
  });

  it("doesn't follow once the answer is done or stopped", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(token("It blocks BCR-ABL.") + DONE));
    await screen.findByText("It blocks BCR-ABL.");
    page.scrollTo.mockClear();
    page.grow();
    expect(page.scrollTo).not.toHaveBeenCalled();

    askQuestion("What else does it bind?");
    await streamed(() => stream.send(token("KIT")));
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    await screen.findByText("Stopped.");
    page.scrollTo.mockClear();
    page.grow();
    expect(page.scrollTo).not.toHaveBeenCalled();
  });

  it("asks again with a suggested name from a button under the answer", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does tylenoll work, and is Tylenoll safe?");
    await streamed(() => stream.send(TYLENOLL_LOOKUP + token("I couldn't find Tylenoll.") + DONE));
    fireEvent.click(await screen.findByRole("button", { name: DID_YOU_MEAN_TYLENOL }));

    expect(stream.fetchMock).toHaveBeenCalledTimes(2);
    expect(stream.sentMessages().at(-1)).toEqual({
      role: "user",
      content: "How does Tylenol work, and is Tylenol safe?",
    });
  });

  it("shows no suggestion button while answering, nor under an answer without suggestions", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Tylenoll work?");
    await streamed(() => stream.send(TYLENOLL_LOOKUP + token("I couldn't")));
    expect(screen.queryByRole("button", { name: /Did you mean/ })).toBeNull();

    await streamed(() => stream.send(DONE));
    await screen.findByRole("button", { name: DID_YOU_MEAN_TYLENOL });

    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(token("It blocks BCR-ABL.") + DONE));
    await screen.findByText("It blocks BCR-ABL.");
    expect(screen.getAllByRole("button", { name: /Did you mean/ })).toHaveLength(1);
  });

  it("disables the suggestion buttons of earlier answers while a new answer comes in", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Tylenoll work?");
    await streamed(() => stream.send(TYLENOLL_LOOKUP + DONE));
    const button = await screen.findByRole("button", { name: DID_YOU_MEAN_TYLENOL });
    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(token("It blocks")));

    expect((button as HTMLButtonElement).disabled).toBe(true);
    await streamed(() => stream.send(DONE));
    expect((button as HTMLButtonElement).disabled).toBe(false);
  });
});

describe("Chat export", () => {
  function exportButton(): HTMLButtonElement {
    return screen.getByRole("button", { name: "Export chat" });
  }

  /** Catches the files the chat hands the browser to save, instead of saving them. */
  function stubDownloads() {
    const files: { name: string; blob: Blob }[] = [];
    let latest: Blob | undefined;
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: (blob: Blob) => {
        latest = blob;
        return "blob:export";
      },
      revokeObjectURL: () => {},
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      files.push({ name: this.download, blob: latest! });
    });
    return files;
  }

  async function answerGleevec() {
    const stream = stubChatStream();
    render(<Chat />);
    expect(screen.queryByRole("button", { name: "Export chat" })).toBeNull();

    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(IMATINIB_LABEL_SEARCH + token("It blocks BCR-ABL [1].")));
    expect(exportButton().disabled).toBe(true);
    await streamed(() => stream.send(IMATINIB_SOURCES_EVENT + DONE));
    expect(exportButton().disabled).toBe(false);
  }

  async function pick(item: string) {
    fireEvent.click(exportButton());
    fireEvent.click(await screen.findByRole("menuitem", { name: item }));
  }

  it("saves the answered conversation as CSV with the answer's sources", async () => {
    const files = stubDownloads();
    await answerGleevec();

    await pick("CSV, one row per message");

    expect(files).toHaveLength(1);
    expect(files[0].name).toMatch(/^molecula-\d{4}-\d{2}-\d{2}-how-does-gleevec-work\.csv$/);
    const csv = await files[0].blob.text();
    expect(csv).toContain("user,How does Gleevec work?,");
    expect(csv).toContain(
      'assistant,It blocks BCR-ABL [1].,"[1] Gleevec – Mechanism of action – https://',
    );
  });

  it("saves the answered conversation as JSON with what the label search returned", async () => {
    const files = stubDownloads();
    await answerGleevec();

    await pick("JSON, with sources and tools");

    const json = JSON.parse(await files[0].blob.text());
    expect(json.title).toBe("How does Gleevec work?");
    expect(json.turns[0].answer).toBe("It blocks BCR-ABL [1].");
    expect(json.turns[0].passages[1].text).toContain("BCR-ABL tyrosine kinase");
    expect(json.turns[0].sources[0].name).toBe("Gleevec");
  });

  it("opens the print dialog to print the conversation or save it as PDF", async () => {
    const print = vi.fn();
    vi.stubGlobal("print", print);
    await answerGleevec();

    await pick("Print or save as PDF");

    expect(print).toHaveBeenCalledOnce();
  });

  it("prints how many questions there are and the day above the conversation, on paper only", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 9, 17, 12));
    await answerGleevec();

    const printed = screen.getByRole("region", { name: "Printed conversation" });
    expect(printed.className).toContain("hidden");
    expect(printed.className).toContain("print:block");
    expect(within(printed).getByText("1 question · Printed on October 17, 2026")).toBeDefined();
  });

  it("prints when each question was asked beside its number", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 9, 17, 9, 30));
    await answerGleevec();

    const label = screen.getByText(/^Q-01 · Query/);
    const asked = within(label).getByText("Oct 17, 2026, 09:30");
    expect(asked.className).toContain("hidden");
    expect(asked.className).toContain("print:inline");
  });

  it("ends the printed conversation with the disclaimer and the openFDA credit", async () => {
    await answerGleevec();

    const end = screen.getByRole("region", { name: "End of the printed conversation" });
    expect(end.className).toContain("print:block");
    expect(within(end).getByText(/Molecula is an AI assistant/)).toBeDefined();
    expect(within(end).getByText(/^Data provided by the U\.S\. Food/)).toBeDefined();
  });
});
