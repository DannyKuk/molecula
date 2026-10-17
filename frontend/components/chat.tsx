"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { type ChatHistory, reopenedTurns } from "@/lib/chat-history";
import { indexedDbHistory } from "@/lib/chat-history-indexeddb";
import { structuresOf } from "@/lib/tool-cards";
import { useChatHistory } from "@/lib/use-chat-history";
import { useConversations } from "@/lib/use-conversations";
import { useFollowAnswer } from "@/lib/use-follow-answer";

import { ChatComposer } from "./chat-composer";
import { ChatDrawer, type ChatListProps, ChatSidebar } from "./chat-sidebar";
import { ConversationTurn } from "./conversation-turn";
import { Disclaimer } from "./disclaimer";
import { ExportMenu } from "./export-menu";
import { HelpDialog, HelpGuide } from "./help-guide";

const browserHistory = indexedDbHistory();

type ChatProps = {
  initialQuestion?: string;
  /** Where the conversations are kept; the browser's IndexedDB unless a test passes its own. */
  history?: ChatHistory;
};

/** The chat: the saved chats, the conversation so far, the question box and the help guide. */
export function Chat({ initialQuestion, history = browserHistory }: ChatProps) {
  const saved = useChatHistory(history);
  const {
    id,
    turns,
    answering,
    pendingAnswer,
    sent,
    answeringId,
    queuedIds,
    ask,
    retry,
    stop,
    open,
    startNew,
    remove,
  } = useConversations(initialQuestion, saved.save);
  const conversationRef = useRef<HTMLOListElement>(null);
  // The 3D view sits above the answer, so following the text would push it away while it plays.
  // Only the newest turn counts: a view in an earlier one doesn't stop following a new answer.
  const showsStructure = structuresOf(turns.at(-1)?.steps ?? []).length > 0;
  useFollowAnswer(conversationRef, sent, answering, showsStructure);

  const { removedBookmark, unbookmark } = useBookmarkUndo(saved);
  const title =
    saved.conversations.find((conversation) => conversation.id === id)?.title ??
    turns[0]?.question ??
    "";

  const chatList: ChatListProps = {
    available: saved.available,
    conversations: saved.conversations,
    bookmarks: saved.bookmarks,
    activeId: id,
    answeringId,
    queuedIds,
    removedBookmark,
    onOpen: async (openedId) => {
      if (openedId === id) return;
      const conversation = await saved.load(openedId);
      if (conversation) open(conversation.id, reopenedTurns(conversation.turns));
    },
    onNew: startNew,
    onRename: saved.rename,
    onDelete: (deletedId) => {
      remove(deletedId);
      saved.remove(deletedId);
    },
    onBookmark: saved.bookmark,
    onUnbookmark: unbookmark,
  };

  return (
    <div className="flex flex-1">
      <ChatSidebar {...chatList} />
      <main className="mx-auto flex w-full max-w-3xl min-w-0 flex-1 flex-col px-4 sm:px-6">
        <header className="flex items-center justify-between gap-4 py-4">
          <div className="flex items-center gap-2">
            <ChatDrawer {...chatList} />
            <h1 className="text-xl font-semibold tracking-tight">Molecula</h1>
          </div>
          <nav className="flex items-center gap-3 text-sm print:hidden">
            <Link href="/drugs" className="font-medium underline-offset-4 hover:underline">
              Supported drugs
            </Link>
            {turns.length > 0 && (
              <ExportMenu title={title} turns={turns} disabled={pendingAnswer} />
            )}
            <HelpDialog onAsk={ask} />
          </nav>
        </header>
        <div className="flex flex-1 flex-col gap-6 pb-12">
          {turns.length === 0 ? (
            <EmptyState onAsk={ask} />
          ) : (
            <>
              <PrintedTitle title={title} />
              <ol
                // Keyed by conversation, so an opened chat doesn't keep the last one's open steps.
                key={id}
                ref={conversationRef}
                aria-label="Conversation"
                className="flex flex-col gap-8"
              >
                {turns.map((turn, index) => (
                  <ConversationTurn
                    key={index}
                    turn={turn}
                    onAsk={ask}
                    chatAnswering={pendingAnswer}
                    onRetry={index === turns.length - 1 ? retry : undefined}
                  />
                ))}
              </ol>
            </>
          )}
        </div>
        <div className="sticky bottom-0 flex flex-col gap-2 border-t border-zinc-200 bg-background py-3 dark:border-zinc-800 print:static print:border-0">
          <div className="contents print:hidden">
            <ChatComposer answering={pendingAnswer} onSend={ask} onStop={stop} />
          </div>
          {saved.available === false && (
            <p className="text-sm text-sky-800 dark:text-sky-300 print:hidden">
              History is off in this browser, so this chat isn&apos;t saved.
            </p>
          )}
          <Disclaimer />
        </div>
      </main>
    </div>
  );
}

/** The conversation's title and the day it was printed, at the top of the first page. */
function PrintedTitle({ title }: { title: string }) {
  const printedOn = new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  return (
    <section aria-label="Printed conversation" className="hidden print:block">
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="text-sm text-zinc-600">Printed on {printedOn}</p>
    </section>
  );
}

function EmptyState({ onAsk }: { onAsk: (question: string) => void }) {
  return (
    <section className="flex flex-col gap-4">
      <p className="text-zinc-600 dark:text-zinc-400">
        Ask about medicines: what they are for, how they work and what they bind to.
      </p>
      <HelpGuide onAsk={onAsk} />
    </section>
  );
}

const UNDO_SHOWN_MS = 6000;

/**
 * Removes bookmarks and keeps the last one removed for a few seconds, so Undo can put it back in
 * its place. It lives here rather than in the list because the sidebar and the drawer share it.
 */
function useBookmarkUndo(saved: ReturnType<typeof useChatHistory>) {
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
