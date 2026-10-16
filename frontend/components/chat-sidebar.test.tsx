import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatHistory } from "@/lib/chat-history";
import { startTurn } from "@/lib/chat-turn";
import { chatFrame, DONE, memoryHistory, stubChatStream, stubPage } from "@/lib/test-fixtures";
import { SIDEBAR_KEY } from "@/lib/use-sidebar-expanded";

import { Chat } from "./chat";

const IMATINIB = "How does imatinib work?";
const SILDENAFIL = "What does sildenafil bind to?";

beforeEach(() => {
  stubPage();
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

  it("saves an answer left for another chat as stopped, with what had streamed", async () => {
    const stream = stubChatStream();
    const { history, stored } = memoryHistory();
    await openPage(history);
    await askAndAnswer(stream, IMATINIB, "Imatinib blocks BCR-ABL.");
    fireEvent.click(rail().getByRole("button", { name: "New chat" }));
    askQuestion(SILDENAFIL);
    await act(async () => stream.send(chatFrame({ type: "token", text: "Sildenafil binds" })));

    fireEvent.click(expandSidebar().getByRole("button", { name: IMATINIB }));

    expect(await screen.findByText("Imatinib blocks BCR-ABL.")).toBeDefined();
    expect(conversationText()).not.toContain("Sildenafil");
    await waitFor(() => {
      const left = [...stored.values()].find((c) => c.title === SILDENAFIL);
      expect(left?.turns).toMatchObject([{ answer: "Sildenafil binds", state: "stopped" }]);
    });
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
