import { IDBFactory } from "fake-indexeddb";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { type Conversation, summaryOf } from "./chat-history";
import { indexedDbHistory } from "./chat-history-indexeddb";
import { startTurn } from "./chat-turn";

function conversation(id: string, title: string): Conversation {
  return {
    id,
    title,
    turns: [{ ...startTurn(title), answer: "An answer.", state: "done" }],
    createdAt: 1000,
    updatedAt: 2000,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("indexedDbHistory", () => {
  beforeEach(() => {
    vi.stubGlobal("indexedDB", new IDBFactory());
  });

  it("keeps a conversation with its turns and lists it without them", async () => {
    const history = indexedDbHistory();
    const imatinib = conversation("c1", "How does imatinib work?");

    await history.put(imatinib);

    expect(await history.get("c1")).toEqual(imatinib);
    expect(await history.list()).toEqual([summaryOf(imatinib)]);
  });

  it("replaces a conversation saved again under its id", async () => {
    const history = indexedDbHistory();
    await history.put(conversation("c1", "How does imatinib work?"));

    await history.put(conversation("c1", "Imatinib"));

    expect((await history.list()).map((c) => c.title)).toEqual(["Imatinib"]);
  });

  it("still has the conversations when the page opens the database again", async () => {
    await indexedDbHistory().put(conversation("c1", "How does imatinib work?"));

    expect(await indexedDbHistory().get("c1")).toEqual(
      conversation("c1", "How does imatinib work?"),
    );
  });

  it("deletes a conversation", async () => {
    const history = indexedDbHistory();
    await history.put(conversation("c1", "How does imatinib work?"));
    await history.put(conversation("c2", "What does sildenafil bind to?"));

    await history.delete("c1");

    expect(await history.get("c1")).toBeUndefined();
    expect((await history.list()).map((c) => c.id)).toEqual(["c2"]);
  });

  it("has no bookmarks at first and keeps them in order when the page opens it again", async () => {
    expect(await indexedDbHistory().bookmarks()).toEqual([]);

    await indexedDbHistory().putBookmarks(["c2", "c1"]);

    expect(await indexedDbHistory().bookmarks()).toEqual(["c2", "c1"]);
  });

  it("keeps the conversations of a database from before bookmarks", async () => {
    await createVersion1Database([conversation("c1", "How does imatinib work?")]);

    const history = indexedDbHistory();

    expect(await history.get("c1")).toEqual(conversation("c1", "How does imatinib work?"));
    expect(await history.bookmarks()).toEqual([]);
    await history.putBookmarks(["c1"]);
    expect(await history.bookmarks()).toEqual(["c1"]);
  });
});

/** The database as #243 made it: version 1, with only the conversations. */
function createVersion1Database(conversations: Conversation[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const opening = indexedDB.open("molecula", 1);
    opening.onupgradeneeded = () =>
      opening.result.createObjectStore("conversations", { keyPath: "id" });
    opening.onsuccess = () => {
      const db = opening.result;
      const transaction = db.transaction("conversations", "readwrite");
      conversations.forEach((saved) => transaction.objectStore("conversations").put(saved));
      transaction.oncomplete = () => {
        db.close();
        resolve();
      };
      transaction.onerror = () => reject(transaction.error);
    };
    opening.onerror = () => reject(opening.error);
  });
}

describe("indexedDbHistory without IndexedDB", () => {
  it("rejects every call instead of throwing", async () => {
    vi.stubGlobal("indexedDB", undefined);
    const history = indexedDbHistory();

    await expect(history.list()).rejects.toThrow();
    await expect(history.put(conversation("c1", "How does imatinib work?"))).rejects.toThrow();
  });

  it("rejects every call when the browser refuses to open the database", async () => {
    const refusing = new IDBFactory();
    vi.spyOn(refusing, "open").mockImplementation(() => {
      throw new DOMException("The user denied permission.", "SecurityError");
    });
    vi.stubGlobal("indexedDB", refusing);

    await expect(indexedDbHistory().list()).rejects.toThrow("The user denied permission.");
  });
});
