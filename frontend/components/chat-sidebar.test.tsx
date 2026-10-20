import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatHistory } from "@/lib/chat-history";
import { startTurn } from "@/lib/chat-turn";
import { chatFrame, DONE, memoryHistory, stubChatStream, stubPage } from "@/lib/test-fixtures";
import { SIDEBAR_KEY } from "@/lib/use-sidebar-expanded";

import { Chat } from "./chat";

vi.mock("./model-status", () => ({ ModelStatus: () => null }));

const IMATINIB = "How does imatinib work?";
const SILDENAFIL = "What does sildenafil bind to?";

let page: ReturnType<typeof stubPage>;

beforeEach(() => {
  page = stubPage();
  localStorage.clear();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function askQuestion(text: string) {
  const box = screen.getByRole("textbox", { name: "Ask about a medicine" });
  fireEvent.change(box, { target: { value: text } });
  fireEvent.keyDown(box, { key: "Enter" });
}

/** Asks `question` and streams `answer`, then the stream ends as the backend ends it. */
async function askAndAnswer(
  stream: ReturnType<typeof stubChatStream>,
  question: string,
  answer: string,
) {
  askQuestion(question);
  await act(async () => {
    stream.send(chatFrame({ type: "token", text: answer }) + DONE);
    stream.end();
  });
  await screen.findByText(answer);
}

function token(text: string): string {
  return chatFrame({ type: "token", text });
}

const WAITING = "Waiting for the answer in another chat to finish…";

function conversationText(): string {
  return screen.queryByRole("list", { name: "Conversation" })?.textContent ?? "";
}

function rail() {
  return within(screen.getByRole("navigation", { name: "Chats" }));
}

function sidebar() {
  return within(screen.getByRole("complementary", { name: "Chat history" }));
}

function expandSidebar() {
  fireEvent.click(rail().getByRole("button", { name: "Show chats" }));
  return sidebar();
}

/** The titles in the expanded list, top to bottom. */
function listedTitles(): string[] {
  return sidebar()
    .queryAllByRole("listitem")
    .map((row) => row.textContent ?? "");
}

/** The titles in one group of the expanded list, top to bottom. */
function titlesUnder(group: string): string[] {
  const section = sidebar().queryByRole("region", { name: group });
  return section
    ? within(section)
        .getAllByRole("listitem")
        .map((row) => row.textContent ?? "")
    : [];
}

/** The rail's bookmark buttons as "number title", top to bottom. */
function railBookmarks(): string[] {
  const group = rail().queryByRole("group", { name: "Bookmarks" });
  if (!group) return [];
  return within(group)
    .getAllByRole("button")
    .map((button) => `${button.textContent} ${button.getAttribute("aria-label")}`);
}

function collapseSidebar() {
  fireEvent.click(sidebar().getByRole("button", { name: "Hide chats" }));
}

/** A history that already holds a finished chat for each title, the first one newest. */
function historyWith(titles: string[]) {
  const memory = memoryHistory();
  titles.forEach((title, index) => {
    const updatedAt = Date.now() - index * 1000;
    memory.stored.set(`c${index}`, {
      id: `c${index}`,
      title,
      turns: [{ ...startTurn(title), answer: `About ${title}.`, state: "done" }],
      createdAt: updatedAt,
      updatedAt,
    });
  });
  return memory;
}

function bookmarkFromRow(title: string) {
  fireEvent.click(sidebar().getByRole("button", { name: `Bookmark: ${title}` }));
}

async function chooseFromMenu(
  title: string,
  item: "Rename" | "Delete" | "Bookmark" | "Remove bookmark",
) {
  fireEvent.click(sidebar().getByRole("button", { name: `Options: ${title}` }));
  fireEvent.click(await screen.findByRole("menuitem", { name: item }));
}

/** Renders the chat and lets it read the history. */
async function openPage(history: ChatHistory) {
  const page = render(<Chat history={history} />);
  await act(async () => {});
  return page;
}

/** Closes the page once its last change is saved and opens it again on the same history. */
async function reload(page: ReturnType<typeof render>, history: ChatHistory) {
  await act(async () => {});
  page.unmount();
  return openPage(history);
}

describe("Chat history", () => {
  it("saves a conversation and opens it again after a reload", async () => {
    const stream = stubChatStream();
    const { history } = memoryHistory();
    const page = await openPage(history);
    await askAndAnswer(stream, IMATINIB, "Imatinib blocks BCR-ABL.");

    await reload(page, history);
    expect(conversationText()).toBe("");
    expandSidebar();
    expect(listedTitles()).toEqual([IMATINIB]);
    fireEvent.click(sidebar().getByRole("button", { name: IMATINIB }));

    expect(await screen.findByText("Imatinib blocks BCR-ABL.")).toBeDefined();
    expect(sidebar().getByRole("button", { name: IMATINIB }).getAttribute("aria-current")).toBe(
      "page",
    );
  });

  it("sends the opened conversation's earlier turns with the next question", async () => {
    const stream = stubChatStream();
    const { history } = memoryHistory();
    const page = await openPage(history);
    await askAndAnswer(stream, IMATINIB, "Imatinib blocks BCR-ABL.");

    await reload(page, history);
    fireEvent.click(expandSidebar().getByRole("button", { name: IMATINIB }));
    await screen.findByText("Imatinib blocks BCR-ABL.");
    await askAndAnswer(stream, "And its side effects?", "Nausea and swelling.");

    expect(stream.sentMessages()).toEqual([
      { role: "user", content: IMATINIB },
      { role: "assistant", content: "Imatinib blocks BCR-ABL." },
      { role: "user", content: "And its side effects?" },
    ]);
    expect(listedTitles()).toEqual([IMATINIB]);
  });

  it("starts an empty conversation with New chat and keeps the earlier one in the list", async () => {
    const stream = stubChatStream();
    await openPage(memoryHistory().history);
    await askAndAnswer(stream, IMATINIB, "Imatinib blocks BCR-ABL.");

    fireEvent.click(rail().getByRole("button", { name: "New chat" }));
    expect(conversationText()).toBe("");
    await askAndAnswer(stream, SILDENAFIL, "Sildenafil binds PDE5.");

    expect(stream.sentMessages()).toEqual([{ role: "user", content: SILDENAFIL }]);
    expandSidebar();
    expect(listedTitles()).toEqual([SILDENAFIL, IMATINIB]);
  });

  it("renames a conversation with Enter and keeps the new title after a reload", async () => {
    const stream = stubChatStream();
    const { history } = memoryHistory();
    const page = await openPage(history);
    await askAndAnswer(stream, IMATINIB, "Imatinib blocks BCR-ABL.");
    expandSidebar();

    await chooseFromMenu(IMATINIB, "Rename");
    const field = sidebar().getByRole("textbox", { name: "Chat title" });
    expect(document.activeElement).toBe(field);
    fireEvent.change(field, { target: { value: "  Imatinib  " } });
    fireEvent.keyDown(field, { key: "Enter" });

    expect(listedTitles()).toEqual(["Imatinib"]);
    await reload(page, history);
    expect(listedTitles()).toEqual(["Imatinib"]);
  });

  it("keeps the old title when renaming is cancelled with Esc", async () => {
    const stream = stubChatStream();
    await openPage(memoryHistory().history);
    await askAndAnswer(stream, IMATINIB, "Imatinib blocks BCR-ABL.");
    expandSidebar();

    await chooseFromMenu(IMATINIB, "Rename");
    const field = sidebar().getByRole("textbox", { name: "Chat title" });
    fireEvent.change(field, { target: { value: "Imatinib" } });
    fireEvent.keyDown(field, { key: "Escape" });

    expect(listedTitles()).toEqual([IMATINIB]);
  });

  it("deletes a conversation after the confirm in its row, and the open one empties the chat", async () => {
    const stream = stubChatStream();
    const { history, stored } = memoryHistory();
    await openPage(history);
    await askAndAnswer(stream, IMATINIB, "Imatinib blocks BCR-ABL.");
    expandSidebar();

    await chooseFromMenu(IMATINIB, "Delete");
    const confirm = within(sidebar().getByRole("group", { name: "Delete chat" }));
    fireEvent.click(confirm.getByRole("button", { name: "Delete" }));

    expect(sidebar().getByText("No chats yet")).toBeDefined();
    expect(conversationText()).toBe("");
    await waitFor(() => expect(stored.size).toBe(0));
  });

  it("keeps a conversation when its delete is cancelled", async () => {
    const stream = stubChatStream();
    await openPage(memoryHistory().history);
    await askAndAnswer(stream, IMATINIB, "Imatinib blocks BCR-ABL.");
    expandSidebar();

    await chooseFromMenu(IMATINIB, "Delete");
    fireEvent.click(sidebar().getByRole("button", { name: "Cancel" }));

    expect(listedTitles()).toEqual([IMATINIB]);
    expect(conversationText()).toContain("Imatinib blocks BCR-ABL.");
  });

  it("doesn't bring back a conversation deleted while it was answering", async () => {
    const stream = stubChatStream();
    const { history, stored } = memoryHistory();
    await openPage(history);
    askQuestion(IMATINIB);
    await act(async () => stream.send(chatFrame({ type: "token", text: "Imatinib blocks" })));

    expandSidebar();
    await chooseFromMenu(IMATINIB, "Delete");
    const confirm = within(sidebar().getByRole("group", { name: "Delete chat" }));
    fireEvent.click(confirm.getByRole("button", { name: "Delete" }));
    await act(async () => {});

    expect(stored.size).toBe(0);
    expect(sidebar().getByText("No chats yet")).toBeDefined();
    expect(conversationText()).toBe("");
  });

  it("starts a new conversation for a linked question", async () => {
    const stream = stubChatStream();
    const { history, stored } = memoryHistory();
    const page = await openPage(history);
    await askAndAnswer(stream, IMATINIB, "Imatinib blocks BCR-ABL.");
    page.unmount();

    render(<Chat history={history} initialQuestion={SILDENAFIL} />);
    await act(async () => {});
    await act(async () => stream.send(chatFrame({ type: "token", text: "PDE5." }) + DONE));

    expect(conversationText()).not.toContain("Imatinib");
    await waitFor(() => expect(stored.size).toBe(2));
    expect(stream.sentMessages()).toEqual([{ role: "user", content: SILDENAFIL }]);
  });
});

describe("Answers in the background", () => {
  it("keeps an answer coming in while another chat is open, and shows it on going back", async () => {
    const stream = stubChatStream();
    await openPage(historyWith([SILDENAFIL]).history);
    askQuestion(IMATINIB);
    await act(async () => stream.send(token("Imatinib blocks")));

    fireEvent.click(expandSidebar().getByRole("button", { name: SILDENAFIL }));
    expect(await screen.findByText(`About ${SILDENAFIL}.`)).toBeDefined();
    await act(async () => stream.send(token(" BCR-ABL.")));
    expect(conversationText()).not.toContain("Imatinib");
    expect(screen.getByRole("button", { name: "Send" })).toBeDefined();

    fireEvent.click(sidebar().getByRole("button", { name: IMATINIB }));
    expect(await screen.findByText("Imatinib blocks BCR-ABL.")).toBeDefined();
    expect(screen.getByRole("button", { name: "Stop" })).toBeDefined();

    await act(async () => stream.send(DONE));
    expect(screen.getByRole("button", { name: "Send" })).toBeDefined();
    expect(screen.queryByText("Stopped.")).toBeNull();
  });

  it("saves an answer that ends while New chat is open under its own chat only", async () => {
    const stream = stubChatStream();
    const { history, stored } = historyWith([SILDENAFIL]);
    await openPage(history);
    askQuestion(IMATINIB);
    await act(async () => stream.send(token("Imatinib")));

    fireEvent.click(rail().getByRole("button", { name: "New chat" }));
    await act(async () => stream.send(token(" blocks BCR-ABL.") + DONE));

    expect(conversationText()).toBe("");
    await waitFor(() => {
      const answered = [...stored.values()].find((c) => c.title === IMATINIB);
      expect(answered?.turns).toMatchObject([
        { answer: "Imatinib blocks BCR-ABL.", state: "done" },
      ]);
    });
    expect(stored.size).toBe(2);
    expect(stored.get("c0")?.turns).toMatchObject([{ answer: `About ${SILDENAFIL}.` }]);
  });

  it("marks the answering chat in the list and on the rail until its answer ends", async () => {
    const stream = stubChatStream();
    await openPage(memoryHistory().history);
    askQuestion(IMATINIB);
    await act(async () => {});
    expect(
      rail().getByRole("button", { name: "Chat history, an answer is coming in" }),
    ).toBeDefined();

    expect(await expandSidebar().findByRole("img", { name: "Answering" })).toBeDefined();
    bookmarkFromRow(IMATINIB);
    collapseSidebar();
    expect(railBookmarks()).toEqual([`1 ${IMATINIB}, answering`]);
    expect(rail().getByRole("button", { name: "Chat history" })).toBeDefined();

    await act(async () => stream.send(DONE));
    expect(railBookmarks()).toEqual([`1 ${IMATINIB}`]);
    expandSidebar();
    expect(sidebar().queryByRole("img", { name: "Answering" })).toBeNull();
  });

  it("stops an answer with Stop after going back to its chat", async () => {
    const stream = stubChatStream();
    const { history, stored } = historyWith([SILDENAFIL]);
    await openPage(history);
    askQuestion(IMATINIB);
    await act(async () => stream.send(token("Imatinib blocks")));
    fireEvent.click(expandSidebar().getByRole("button", { name: SILDENAFIL }));
    await screen.findByText(`About ${SILDENAFIL}.`);

    fireEvent.click(sidebar().getByRole("button", { name: IMATINIB }));
    fireEvent.click(await screen.findByRole("button", { name: "Stop" }));

    expect(await screen.findByText("Stopped.")).toBeDefined();
    expect(sidebar().queryByRole("img", { name: "Answering" })).toBeNull();
    await waitFor(() => {
      const stopped = [...stored.values()].find((c) => c.title === IMATINIB);
      expect(stopped?.turns).toMatchObject([{ answer: "Imatinib blocks", state: "stopped" }]);
    });
  });

  it("ends the answer of a chat deleted while another chat is open", async () => {
    const stream = stubChatStream();
    const { history, stored } = memoryHistory();
    await openPage(history);
    askQuestion(IMATINIB);
    await act(async () => stream.send(token("Imatinib blocks")));
    fireEvent.click(rail().getByRole("button", { name: "New chat" }));

    expandSidebar();
    await chooseFromMenu(IMATINIB, "Delete");
    const confirm = within(sidebar().getByRole("group", { name: "Delete chat" }));
    fireEvent.click(confirm.getByRole("button", { name: "Delete" }));
    await act(async () => {});

    const request = stream.fetchMock.mock.calls[0][1] as RequestInit;
    expect(request.signal?.aborted).toBe(true);
    expect(stored.size).toBe(0);
    expect(sidebar().getByText("No chats yet")).toBeDefined();
  });

  it("queues a question asked in another chat and answers it once the first answer ends", async () => {
    const stream = stubChatStream();
    const { history, stored } = memoryHistory();
    await openPage(history);
    askQuestion(IMATINIB);
    await act(async () => stream.send(token("Imatinib blocks")));
    fireEvent.click(rail().getByRole("button", { name: "New chat" }));
    askQuestion(SILDENAFIL);
    await act(async () => {});

    expect(screen.getByText(WAITING)).toBeDefined();
    expect(screen.getByRole("button", { name: "Stop" })).toBeDefined();
    expect(stream.fetchMock).toHaveBeenCalledTimes(1);
    expect(
      await expandSidebar().findByRole("img", { name: "Waiting for another answer" }),
    ).toBeDefined();

    await act(async () => stream.send(token(" BCR-ABL.") + DONE));
    await waitFor(() => expect(stream.fetchMock).toHaveBeenCalledTimes(2));
    expect(stream.sentMessages()).toEqual([{ role: "user", content: SILDENAFIL }]);
    await act(async () => stream.send(token("Sildenafil binds PDE5.") + DONE));

    expect(await screen.findByText("Sildenafil binds PDE5.")).toBeDefined();
    expect(conversationText()).not.toContain("Imatinib");
    expect(screen.queryByText(WAITING)).toBeNull();
    await waitFor(() =>
      expect([...stored.values()].map((c) => [c.title, c.turns.map((t) => t.answer)])).toEqual(
        expect.arrayContaining([
          [IMATINIB, ["Imatinib blocks BCR-ABL."]],
          [SILDENAFIL, ["Sildenafil binds PDE5."]],
        ]),
      ),
    );
  });

  it("sends a queued question with the earlier turns of its chat", async () => {
    const stream = stubChatStream();
    await openPage(historyWith([SILDENAFIL]).history);
    askQuestion(IMATINIB);
    await act(async () => stream.send(token("Imatinib blocks")));
    fireEvent.click(expandSidebar().getByRole("button", { name: SILDENAFIL }));
    await screen.findByText(`About ${SILDENAFIL}.`);
    askQuestion("And its side effects?");

    await act(async () => stream.send(DONE));
    await waitFor(() => expect(stream.fetchMock).toHaveBeenCalledTimes(2));

    expect(stream.sentMessages()).toEqual([
      { role: "user", content: SILDENAFIL },
      { role: "assistant", content: `About ${SILDENAFIL}.` },
      { role: "user", content: "And its side effects?" },
    ]);
  });

  it("takes a queued question out of the line on Stop", async () => {
    const stream = stubChatStream();
    const { history, stored } = memoryHistory();
    await openPage(history);
    askQuestion(IMATINIB);
    await act(async () => {});
    fireEvent.click(rail().getByRole("button", { name: "New chat" }));
    askQuestion(SILDENAFIL);
    await screen.findByText(WAITING);

    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    expect(await screen.findByText("Stopped.")).toBeDefined();
    expect(screen.getByRole("button", { name: "Send" })).toBeDefined();
    await act(async () => stream.send(DONE));

    expect(stream.fetchMock).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      const left = [...stored.values()].find((c) => c.title === SILDENAFIL);
      expect(left?.turns).toMatchObject([{ answer: "", state: "stopped" }]);
    });
  });

  it("takes a deleted chat's queued question out of the line", async () => {
    const stream = stubChatStream();
    const { history, stored } = memoryHistory();
    await openPage(history);
    askQuestion(IMATINIB);
    await act(async () => {});
    fireEvent.click(rail().getByRole("button", { name: "New chat" }));
    askQuestion(SILDENAFIL);
    await screen.findByText(WAITING);

    expandSidebar();
    await chooseFromMenu(SILDENAFIL, "Delete");
    const confirm = within(sidebar().getByRole("group", { name: "Delete chat" }));
    fireEvent.click(confirm.getByRole("button", { name: "Delete" }));
    await act(async () => stream.send(DONE));

    expect(conversationText()).toBe("");
    expect(stream.fetchMock).toHaveBeenCalledTimes(1);
    await waitFor(() => expect([...stored.values()].map((c) => c.title)).toEqual([IMATINIB]));
  });

  it("doesn't move the chat for answers coming in to chats that aren't shown", async () => {
    const stream = stubChatStream();
    await openPage(historyWith([SILDENAFIL]).history);
    askQuestion(IMATINIB);
    await act(async () => {});
    fireEvent.click(rail().getByRole("button", { name: "New chat" }));
    askQuestion("What is ibuprofen?");
    fireEvent.click(expandSidebar().getByRole("button", { name: SILDENAFIL }));
    await screen.findByText(`About ${SILDENAFIL}.`);
    const scrolls = page.scrollTo.mock.calls.length;

    await act(async () => stream.send(token("Imatinib blocks BCR-ABL.") + DONE));
    await waitFor(() => expect(stream.fetchMock).toHaveBeenCalledTimes(2));
    await act(async () => stream.send(token("Ibuprofen is an NSAID.") + DONE));

    expect(page.scrollTo).toHaveBeenCalledTimes(scrolls);
  });
});

describe("Chat history that the browser doesn't keep", () => {
  it("says history is off and keeps answering when the storage fails", async () => {
    const stream = stubChatStream();
    await openPage(memoryHistory({ failing: true }).history);

    await askAndAnswer(stream, IMATINIB, "Imatinib blocks BCR-ABL.");

    expect(
      screen.getByText("History is off in this browser, so this chat isn't saved."),
    ).toBeDefined();
    expect(expandSidebar().getByText("History is off in this browser")).toBeDefined();
    expect(listedTitles()).toEqual([]);
  });

  it("says history is off and keeps answering without IndexedDB", async () => {
    const stream = stubChatStream();
    render(<Chat />);

    await askAndAnswer(stream, IMATINIB, "Imatinib blocks BCR-ABL.");

    expect(
      await screen.findByText("History is off in this browser, so this chat isn't saved."),
    ).toBeDefined();
  });
});

describe("Chat sidebar", () => {
  it("starts as a rail and keeps the list expanded or collapsed across reloads", async () => {
    const { history } = memoryHistory();
    const page = await openPage(history);
    expect(rail().getByRole("button", { name: "Chat history" })).toBeDefined();

    expandSidebar();
    expect(localStorage.getItem(SIDEBAR_KEY)).toBe("expanded");
    const reloaded = await reload(page, history);
    expect(sidebar().getByRole("button", { name: "New chat" })).toBeDefined();

    fireEvent.click(sidebar().getByRole("button", { name: "Hide chats" }));
    await reload(reloaded, history);
    expect(screen.queryByRole("complementary", { name: "Chat history" })).toBeNull();
    expect(rail().getByRole("button", { name: "Show chats" })).toBeDefined();
  });

  it("opens the list as a drawer on a phone and closes it when a chat is picked", async () => {
    const stream = stubChatStream();
    await openPage(memoryHistory().history);
    await askAndAnswer(stream, IMATINIB, "Imatinib blocks BCR-ABL.");
    fireEvent.click(rail().getByRole("button", { name: "New chat" }));

    fireEvent.click(screen.getByRole("button", { name: "Open chats" }));
    const drawer = within(await screen.findByRole("dialog", { name: "Chats" }));
    fireEvent.click(drawer.getByRole("button", { name: IMATINIB }));

    expect(await screen.findByText("Imatinib blocks BCR-ABL.")).toBeDefined();
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("opens the saved chat a link from another page names", async () => {
    render(<Chat history={historyWith(["Imatinib", "Sildenafil"]).history} initialChatId="c1" />);

    expect(await screen.findByText("About Sildenafil.")).toBeDefined();
  });

  it("links to the benchmarks from the rail, the list and the phone drawer", async () => {
    await openPage(memoryHistory().history);
    const benchmarks = { name: "Benchmarks" };
    expect(rail().getByRole("link", benchmarks).getAttribute("href")).toBe("/benchmarks");

    fireEvent.click(screen.getByRole("button", { name: "Open chats" }));
    const drawer = within(await screen.findByRole("dialog", { name: "Chats" }));
    expect(drawer.getByRole("link", benchmarks).getAttribute("href")).toBe("/benchmarks");
    fireEvent.click(drawer.getByRole("button", { name: "Close chats" }));

    expect(expandSidebar().getByRole("link", benchmarks).getAttribute("href")).toBe("/benchmarks");
  });
});

describe("Chat bookmarks", () => {
  const CHATS = [
    "Imatinib",
    "Sildenafil",
    "Warfarin",
    "Metformin",
    "Aspirin",
    "Ibuprofen",
    "Digoxin",
  ];

  it("moves a bookmarked chat into the Bookmarked group and the rail, and opens it from there", async () => {
    await openPage(historyWith(["Imatinib", "Sildenafil"]).history);
    expandSidebar();

    bookmarkFromRow("Sildenafil");

    expect(titlesUnder("Bookmarked")).toEqual(["Sildenafil"]);
    expect(titlesUnder("Today")).toEqual(["Imatinib"]);
    collapseSidebar();
    expect(railBookmarks()).toEqual(["1 Sildenafil"]);
    fireEvent.click(rail().getByRole("button", { name: "Sildenafil" }));
    expect(await screen.findByText("About Sildenafil.")).toBeDefined();
    expect(rail().getByRole("button", { name: "Sildenafil" }).getAttribute("aria-current")).toBe(
      "page",
    );
  });

  it("shows only the rail's icons without bookmarks", async () => {
    await openPage(historyWith(["Imatinib"]).history);

    expect(railBookmarks()).toEqual([]);
  });

  it("shows the Bookmarked group on top in the phone drawer", async () => {
    await openPage(historyWith(["Imatinib", "Sildenafil"]).history);
    expandSidebar();
    bookmarkFromRow("Sildenafil");

    fireEvent.click(screen.getByRole("button", { name: "Open chats" }));
    const drawer = within(await screen.findByRole("dialog", { name: "Chats" }));

    expect(drawer.getAllByRole("region").map((group) => group.getAttribute("aria-label"))).toEqual([
      "Bookmarked",
      "Today",
    ]);
  });

  it("removes a bookmark from the ⋯ menu, and Undo puts it back in its place", async () => {
    const { history, bookmarks } = historyWith(["Imatinib", "Sildenafil", "Warfarin"]);
    await openPage(history);
    expandSidebar();
    for (const title of ["Warfarin", "Imatinib", "Sildenafil"]) {
      await chooseFromMenu(title, "Bookmark");
    }

    await chooseFromMenu("Imatinib", "Remove bookmark");

    expect(titlesUnder("Bookmarked")).toEqual(["Warfarin", "Sildenafil"]);
    expect(titlesUnder("Today")).toEqual(["Imatinib"]);
    const undoBar = sidebar().getByRole("status");
    expect(undoBar.textContent).toContain("Removed 'Imatinib' from bookmarks");
    fireEvent.click(within(undoBar).getByRole("button", { name: "Undo" }));

    expect(titlesUnder("Bookmarked")).toEqual(["Warfarin", "Imatinib", "Sildenafil"]);
    expect(sidebar().queryByRole("status")).toBeNull();
    await waitFor(() => expect(bookmarks.ids).toEqual(["c2", "c0", "c1"]));
  });

  it("hides the Undo after about six seconds", async () => {
    vi.useFakeTimers();
    await openPage(historyWith(["Imatinib"]).history);
    expandSidebar();
    bookmarkFromRow("Imatinib");

    fireEvent.click(sidebar().getByRole("button", { name: "Remove bookmark: Imatinib" }));
    expect(sidebar().getByRole("status")).toBeDefined();
    act(() => vi.advanceTimersByTime(6000));

    expect(sidebar().queryByRole("status")).toBeNull();
    expect(titlesUnder("Bookmarked")).toEqual([]);
  });

  it("numbers the first five bookmarks in the rail and puts the rest behind +N", async () => {
    await openPage(historyWith(CHATS).history);
    expandSidebar();
    CHATS.forEach(bookmarkFromRow);
    collapseSidebar();

    expect(railBookmarks()).toEqual([
      "1 Imatinib",
      "2 Sildenafil",
      "3 Warfarin",
      "4 Metformin",
      "5 Aspirin",
      "+2 All 7 bookmarks",
    ]);
  });

  it("lists every bookmark in the +N flyout and opens one from it", async () => {
    await openPage(historyWith(CHATS).history);
    expandSidebar();
    CHATS.forEach(bookmarkFromRow);
    collapseSidebar();

    fireEvent.click(rail().getByRole("button", { name: "All 7 bookmarks" }));
    const items = await screen.findAllByRole("menuitem");
    expect(items.map((item) => item.textContent)).toEqual(
      CHATS.map((title, index) => `${index + 1}${title}`),
    );
    fireEvent.click(screen.getByRole("menuitem", { name: "Digoxin" }));

    expect(await screen.findByText("About Digoxin.")).toBeDefined();
  });

  it("drops the bookmark of a deleted chat", async () => {
    const { history, bookmarks } = historyWith(["Imatinib", "Sildenafil"]);
    await openPage(history);
    expandSidebar();
    bookmarkFromRow("Imatinib");

    await chooseFromMenu("Imatinib", "Delete");
    const confirm = within(sidebar().getByRole("group", { name: "Delete chat" }));
    fireEvent.click(confirm.getByRole("button", { name: "Delete" }));

    expect(sidebar().queryByRole("region", { name: "Bookmarked" })).toBeNull();
    await waitFor(() => expect(bookmarks.ids).toEqual([]));
    collapseSidebar();
    expect(railBookmarks()).toEqual([]);
  });

  it("keeps the bookmarks and their order across a reload", async () => {
    const { history } = historyWith(["Imatinib", "Sildenafil", "Warfarin"]);
    const page = await openPage(history);
    expandSidebar();
    bookmarkFromRow("Warfarin");
    bookmarkFromRow("Imatinib");
    collapseSidebar();

    await reload(page, history);

    expect(railBookmarks()).toEqual(["1 Warfarin", "2 Imatinib"]);
  });
});
