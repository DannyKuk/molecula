import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CHAT_FAILED, CHAT_UNAVAILABLE } from "@/lib/chat";
import { MAX_MESSAGE_LENGTH } from "@/lib/chat-limits";
import {
  chatFrame,
  DONE,
  IMATINIB_LABEL_SEARCH,
  IMATINIB_SOURCES_EVENT,
  OPENFDA_DISCLAIMER,
  stubChatStream,
  stubPage,
} from "@/lib/test-fixtures";
import {
  IBUPROFEN_PROPERTIES,
  IMATINIB_COMPLEX,
  NAPROXEN_PROPERTIES,
} from "@/lib/test-tool-results";
import type { StructureTarget } from "@/lib/tool-cards";

import { Chat } from "./chat";

// jsdom has no WebGL; the 3D view only needs to be on the page.
vi.mock("./structure/structure-panel", () => ({
  StructurePanel: ({ target }: { target: StructureTarget }) => <p>3D view of {target.name}</p>,
}));

let page: ReturnType<typeof stubPage>;

beforeEach(() => {
  page = stubPage();
});

afterEach(() => {
  vi.unstubAllGlobals();
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

async function streamed(send: () => void) {
  await act(async () => send());
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
    expect(screen.getByText("How does Gleevec work?")).toBeDefined();
    expect(stream.sentMessages()).toEqual([{ role: "user", content: "How does Gleevec work?" }]);
  });

  it("shows the steps live while answering and folds them away when done", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    expect(await screen.findByText("Thinking…")).toBeDefined();
    await streamed(() => stream.send(status("Looking up Gleevec")));
    await streamed(() => stream.send(status("Searching the imatinib label")));

    const progress = await screen.findByRole("list", { name: "Progress" });
    expect(
      within(progress)
        .getAllByRole("listitem")
        .map((item) => item.textContent),
    ).toEqual(["Looking up Gleevec", "Searching the imatinib label"]);
    expect(screen.queryByText("Thinking…")).toBeNull();

    await streamed(() => stream.send(token("Imatinib blocks BCR-ABL.")));
    await streamed(() => stream.send(DONE));

    const toggle = await screen.findByRole("button", { name: "2 steps" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("Looking up Gleevec")).toBeNull();

    fireEvent.click(toggle);
    expect(screen.getByText("Looking up Gleevec")).toBeDefined();
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
      "Getting the properties of ibuprofen· C13H18O2 · 206.28 g/mol",
      "Getting the properties of naproxen· C14H14O3 · 230.26 g/mol",
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
    expect(screen.getAllByText("How does Gleevec work?")).toHaveLength(1);
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

    expect(await screen.findByText("How does imatinib work?")).toBeDefined();
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
    expect(screen.getAllByText("How does imatinib work?")).toHaveLength(1);
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
    expect(screen.queryByText(OPENFDA_DISCLAIMER)).toBeNull();

    await streamed(() => stream.send(IMATINIB_SOURCES_EVENT + DONE));

    expect(
      await screen.findByRole("button", {
        name: "Sources: Gleevec · Mechanism of action, Gleevec · Pharmacokinetics",
      }),
    ).toBeDefined();
    expect(screen.queryByText(/\[1\]/)).toBeNull();
    expect(screen.getByText(OPENFDA_DISCLAIMER)).toBeDefined();
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

  it("scrolls to the end of the page once the sent question is on it, each time one is sent", async () => {
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

    expect(conversationWhenScrolled).toHaveLength(2);
    expect(conversationWhenScrolled[0]).toContain("How does Gleevec work?");
    expect(conversationWhenScrolled[1]).toContain("What does sildenafil bind to?");
    expect(page.scrollTo).toHaveBeenLastCalledWith({ top: document.documentElement.scrollHeight });
  });

  it("scrolls to the end of the page again on Retry", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("How does Gleevec work?");
    await streamed(() => stream.send(chatFrame({ type: "error", message: "Timed out." })));
    expect(page.scrollTo).toHaveBeenCalledTimes(1);
    fireEvent.click(
      within(await screen.findByRole("alert")).getByRole("button", { name: "Try again" }),
    );

    expect(page.scrollTo).toHaveBeenCalledTimes(2);
  });

  it("scrolls to the question it was opened with", async () => {
    stubChatStream();
    render(<Chat initialQuestion="How does imatinib work?" />);

    await screen.findByText("How does imatinib work?");
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

  it("follows the answer to the end of the page while it streams in", async () => {
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

  it("keeps following when a scroll event lands just after the page grew", async () => {
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

  it("stops following once the answer shows a 3D view", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("Show imatinib bound to its target in 3D.");
    await streamed(() => stream.send(IMATINIB_IN_3D));
    expect(await screen.findByText("3D view of imatinib")).toBeDefined();
    page.scrollTo.mockClear();
    await streamed(() => stream.send(token("Imatinib sits in the ATP pocket.")));
    page.grow();

    expect(page.scrollTo).not.toHaveBeenCalled();
  });

  it("follows a new answer after an earlier one showed a 3D view", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    askQuestion("Show imatinib bound to its target in 3D.");
    await streamed(() => stream.send(IMATINIB_IN_3D + token("It sits in the ATP pocket.") + DONE));
    await screen.findByText("It sits in the ATP pocket.");
    askQuestion("What else does it bind?");
    await streamed(() => stream.send(token("KIT and PDGFR.")));
    page.scrollTo.mockClear();
    page.grow();

    expect(screen.getByText("3D view of imatinib")).toBeDefined();
    expect(page.scrollTo).toHaveBeenCalledOnce();
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
});
