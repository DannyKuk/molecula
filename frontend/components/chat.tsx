"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { failureText, requestMessages, streamChat } from "@/lib/chat";
import { type ChatHistory, newConversationId, reopenedTurns } from "@/lib/chat-history";
import { indexedDbHistory } from "@/lib/chat-history-indexeddb";
import {
  applyEvent,
  conversationWith,
  endTurn,
  failTurn,
  startTurn,
  stopTurn,
  type Turn,
} from "@/lib/chat-turn";
import { structuresOf } from "@/lib/tool-cards";
import { useChatHistory } from "@/lib/use-chat-history";
import { useFollowAnswer } from "@/lib/use-follow-answer";

import { ChatComposer } from "./chat-composer";
import { ChatDrawer, type ChatListProps, ChatSidebar } from "./chat-sidebar";
import { ConversationTurn } from "./conversation-turn";
import { Disclaimer } from "./disclaimer";
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
  const { id, turns, answering, sent, ask, retry, stop, open, startNew } = useConversation(
    initialQuestion,
    saved.save,
  );
  const conversationRef = useRef<HTMLOListElement>(null);
  // The 3D view sits above the answer, so following the text would push it away while it plays.
  // Only the newest turn counts: a view in an earlier one doesn't stop following a new answer.
  const showsStructure = structuresOf(turns.at(-1)?.steps ?? []).length > 0;
  useFollowAnswer(conversationRef, sent, answering, showsStructure);

  const chatList: ChatListProps = {
    available: saved.available,
    conversations: saved.conversations,
    activeId: id,
    onOpen: async (openedId) => {
      if (openedId === id) return;
      const conversation = await saved.load(openedId);
      if (conversation) open(conversation.id, reopenedTurns(conversation.turns));
    },
    onNew: startNew,
    onRename: saved.rename,
    onDelete: (deletedId) => {
      if (deletedId === id) startNew();
      saved.remove(deletedId);
    },
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
          <nav className="flex items-center gap-3 text-sm">
            <Link href="/drugs" className="font-medium underline-offset-4 hover:underline">
              Supported drugs
            </Link>
            <HelpDialog onAsk={ask} />
          </nav>
        </header>
        <div className="flex flex-1 flex-col gap-6 pb-12">
          {turns.length === 0 ? (
            <EmptyState onAsk={ask} />
          ) : (
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
                  chatAnswering={answering}
                  onRetry={index === turns.length - 1 ? retry : undefined}
                />
              ))}
            </ol>
          )}
        </div>
        <div className="sticky bottom-0 flex flex-col gap-2 border-t border-zinc-200 bg-background py-3 dark:border-zinc-800">
          <ChatComposer answering={answering} onSend={ask} onStop={stop} />
          {saved.available === false && (
            <p className="text-sm text-sky-800 dark:text-sky-300">
              History is off in this browser, so this chat isn&apos;t saved.
            </p>
          )}
          <Disclaimer />
        </div>
      </main>
    </div>
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

/**
 * The conversation: its id, its turns and the one answer that may be streaming in. Only the latest
 * request updates the turns, so an answer that was replaced, or left by opening another chat,
 * can't change what is shown. Each answer is saved under its conversation's id when it starts and
 * when it ends, also when it was left; the id is made with the first question.
 */
function useConversation(
  initialQuestion: string | undefined,
  save: (id: string, turns: Turn[]) => void,
) {
  const [id, setId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [sent, setSent] = useState(0);
  const controllerRef = useRef<AbortController | null>(null);
  const idRef = useRef<string | null>(null);
  const saveRef = useRef(save);
  const answering = turns.at(-1)?.state === "answering";

  useEffect(() => {
    saveRef.current = save;
  }, [save]);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const answer = useCallback(async (question: string, earlier: Turn[]) => {
    const controller = new AbortController();
    controllerRef.current = controller;
    const conversationId = (idRef.current ??= newConversationId());
    setId(conversationId);
    // Each update sets the whole list rather than changing the current one: hydrated inside a
    // Suspense boundary, the chat starts the linked question at idle priority, and React renders
    // the stream's updates before that start (#218).
    let latest = startTurn(question);
    const updateLatest = (change: (turn: Turn) => Turn) => {
      latest = change(latest);
      if (controllerRef.current === controller) setTurns([...earlier, latest]);
    };

    setTurns([...earlier, latest]);
    setSent((count) => count + 1);
    saveRef.current(conversationId, [...earlier, latest]);
    try {
      const messages = requestMessages(conversationWith(earlier, question));
      for await (const event of streamChat(messages, controller.signal)) {
        updateLatest((turn) => applyEvent(turn, event));
      }
      updateLatest(endTurn);
    } catch (error) {
      if (controller.signal.aborted) updateLatest(stopTurn);
      else updateLatest((turn) => failTurn(turn, failureText(error)));
    }
    saveRef.current(conversationId, [...earlier, latest]);
  }, []);

  useEffect(() => {
    if (initialQuestion) answer(initialQuestion, []);
  }, [initialQuestion, answer]);

  /** Shows another conversation, or an empty one with `null`; an answer still streaming stops. */
  const show = (shownId: string | null, shownTurns: Turn[]) => {
    const leaving = controllerRef.current;
    controllerRef.current = null;
    leaving?.abort();
    idRef.current = shownId;
    setId(shownId);
    setTurns(shownTurns);
    window.scrollTo({ top: 0 });
  };

  const ask = (question: string) => {
    if (!answering) answer(question, turns);
  };
  const retry = () => answer(turns[turns.length - 1].question, turns.slice(0, -1));
  const stop = () => controllerRef.current?.abort();
  const open = (openedId: string, openedTurns: Turn[]) => show(openedId, openedTurns);
  const startNew = () => show(null, []);

  return { id, turns, answering, sent, ask, retry, stop, open, startNew };
}
