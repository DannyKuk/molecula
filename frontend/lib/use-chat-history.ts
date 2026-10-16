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
 * The saved conversations and the changes to them. `available` is null until the history has
 * loaded and false once the storage has failed; the chat keeps working either way. Changes run one
 * after another, so a save can't overwrite a rename or bring back a deleted conversation.
 */
export function useChatHistory(history: ChatHistory) {
  const [available, setAvailable] = useState<boolean | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const deleted = useRef(new Set<string>());

  useEffect(() => {
    let current = true;
    history.list().then(
      (list) => {
        if (!current) return;
        setConversations(list);
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

  const remove = useCallback(
    (id: string) => {
      deleted.current.add(id);
      setConversations((list) => list.filter((c) => c.id !== id));
      return enqueue(() => history.delete(id));
    },
    [history, enqueue],
  );

  return { available, conversations, save, load, rename, remove };
}
