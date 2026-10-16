import { useCallback, useEffect, useRef, useState } from "react";

import {
  type ChatHistory,
  type Conversation,
  type ConversationSummary,
  summaryOf,
  withTurns,
} from "./chat-history";
import type { Turn } from "./chat-turn";

/**
 * The saved conversations, the bookmarks and the changes to them. `available` is null until the
 * history has loaded and false once the storage has failed; the chat keeps working either way.
 * Changes run one after another, so a save can't overwrite a rename or bring back a deleted
 * conversation, and the last bookmark list written is the latest.
 */
export function useChatHistory(history: ChatHistory) {
  const [available, setAvailable] = useState<boolean | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [bookmarks, setBookmarks] = useState<string[]>([]);
  const bookmarksRef = useRef<string[]>([]);
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const deleted = useRef(new Set<string>());

  useEffect(() => {
    let current = true;
    Promise.all([history.list(), history.bookmarks()]).then(
      ([list, ids]) => {
        if (!current) return;
        setConversations(list);
        bookmarksRef.current = ids;
        setBookmarks(ids);
        setAvailable(true);
      },
      () => current && setAvailable(false),
    );
    return () => {
      current = false;
    };
  }, [history]);

  const enqueue = useCallback(<T>(change: () => Promise<T>): Promise<T | undefined> => {
    const done = queue.current.then(change);
    queue.current = done.catch(() => setAvailable(false));
    return done.catch(() => undefined);
  }, []);

  const save = useCallback(
    (id: string, turns: Turn[]) =>
      enqueue(async () => {
        if (deleted.current.has(id)) return;
        const saved = withTurns(await history.get(id), id, turns, Date.now());
        await history.put(saved);
        setConversations((list) => [summaryOf(saved), ...list.filter((c) => c.id !== id)]);
      }),
    [history, enqueue],
  );

  const load = useCallback(
    (id: string): Promise<Conversation | undefined> => enqueue(() => history.get(id)),
    [history, enqueue],
  );

  const rename = useCallback(
    (id: string, title: string) => {
      setConversations((list) => list.map((c) => (c.id === id ? { ...c, title } : c)));
      return enqueue(async () => {
        const saved = await history.get(id);
        if (saved) await history.put({ ...saved, title });
      });
    },
    [history, enqueue],
  );

  const changeBookmarks = useCallback(
    (change: (ids: string[]) => string[]) => {
      const ids = change(bookmarksRef.current);
      bookmarksRef.current = ids;
      setBookmarks(ids);
      return enqueue(() => history.putBookmarks(ids));
    },
    [history, enqueue],
  );

  /** Bookmarks the conversation at the end, or at `at` to put a removed bookmark back. */
  const bookmark = useCallback(
    (id: string, at?: number) => {
      if (deleted.current.has(id) || bookmarksRef.current.includes(id)) return;
      return changeBookmarks((ids) => {
        const index = at ?? ids.length;
        return [...ids.slice(0, index), id, ...ids.slice(index)];
      });
    },
    [changeBookmarks],
  );

  const unbookmark = useCallback(
    (id: string) => changeBookmarks((ids) => ids.filter((bookmarked) => bookmarked !== id)),
    [changeBookmarks],
  );

  const remove = useCallback(
    (id: string) => {
      deleted.current.add(id);
      setConversations((list) => list.filter((c) => c.id !== id));
      if (bookmarksRef.current.includes(id)) unbookmark(id);
      return enqueue(() => history.delete(id));
    },
    [history, enqueue, unbookmark],
  );

  return {
    available,
    conversations,
    bookmarks,
    save,
    load,
    rename,
    remove,
    bookmark,
    unbookmark,
  };
}
