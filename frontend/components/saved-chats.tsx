"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import type { ChatHistory } from "@/lib/chat-history";
import { browserHistory } from "@/lib/chat-history-indexeddb";
import { savedChatLink } from "@/lib/chat-link";
import { useChatHistory } from "@/lib/use-chat-history";

import type { ChatListProps } from "./chat-sidebar";

/**
 * The saved chats for the sidebar of a page other than the chat: picking one opens it in the chat,
 * and New chat opens an empty one there.
 */
export function useSavedChats(history: ChatHistory = browserHistory): ChatListProps {
  const router = useRouter();
  const saved = useChatHistory(history);
  const { removedBookmark, unbookmark } = useBookmarkUndo(saved);
  return {
    available: saved.available,
    conversations: saved.conversations,
    bookmarks: saved.bookmarks,
    activeId: null,
    answeringId: null,
    queuedIds: [],
    removedBookmark,
    onOpen: (id) => router.push(savedChatLink(id)),
    onNew: () => router.push("/"),
    onRename: saved.rename,
    onDelete: saved.remove,
    onBookmark: saved.bookmark,
    onUnbookmark: unbookmark,
  };
}

const UNDO_SHOWN_MS = 6000;

/**
 * Removes bookmarks and keeps the last one removed for a few seconds, so Undo can put it back in
 * its place. It lives outside the list because the sidebar and the drawer share it.
 */
export function useBookmarkUndo(saved: ReturnType<typeof useChatHistory>) {
  const [removed, setRemoved] = useState<{ id: string; at: number } | null>(null);

  useEffect(() => {
    if (!removed) return;
    const timer = setTimeout(() => setRemoved(null), UNDO_SHOWN_MS);
    return () => clearTimeout(timer);
  }, [removed]);

  const unbookmark = (id: string) => {
    setRemoved({ id, at: saved.bookmarks.indexOf(id) });
    saved.unbookmark(id);
  };
  const title = saved.conversations.find((c) => c.id === removed?.id)?.title;
  const removedBookmark =
    removed && title !== undefined
      ? {
          title,
          onUndo: () => {
            setRemoved(null);
            saved.bookmark(removed.id, removed.at);
          },
        }
      : null;

  return { removedBookmark, unbookmark };
}
