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
});

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
