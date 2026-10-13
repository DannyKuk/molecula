"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { failureText, requestMessages, streamChat } from "@/lib/chat";
import {
  applyEvent,
  conversationWith,
  endTurn,
  failTurn,
  startTurn,
  stopTurn,
  type Turn,
} from "@/lib/chat-turn";

import { ChatComposer } from "./chat-composer";
import { ConversationTurn } from "./conversation-turn";
import { Disclaimer } from "./disclaimer";
import { HelpDialog, HelpGuide } from "./help-guide";

/** The chat: the conversation so far, the question box and the help guide. */
export function Chat({ initialQuestion }: { initialQuestion?: string }) {
  const { turns, answering, sent, ask, retry, stop } = useConversation(initialQuestion);

  // The page's own bottom, not an element's: scrolling an element into view ignores the sticky
  // question box, which then covers the end of the conversation.
  useEffect(() => {
    if (sent > 0) window.scrollTo({ top: document.documentElement.scrollHeight });
  }, [sent]);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 sm:px-6">
      <header className="flex items-center justify-between gap-4 py-4">
        <h1 className="text-xl font-semibold tracking-tight">Molecula</h1>
        <nav className="flex items-center gap-3 text-sm">
          <Link href="/drugs" className="font-medium underline-offset-4 hover:underline">
            Supported drugs
          </Link>
          <HelpDialog onAsk={ask} />
        </nav>
      </header>
      <div className="flex flex-1 flex-col gap-6 pb-6">
        {turns.length === 0 ? (
          <EmptyState onAsk={ask} />
        ) : (
          <ol aria-label="Conversation" className="flex flex-col gap-8">
            {turns.map((turn, index) => (
              <ConversationTurn
                key={index}
                turn={turn}
                onRetry={index === turns.length - 1 ? retry : undefined}
              />
            ))}
          </ol>
        )}
      </div>
      <div className="sticky bottom-0 flex flex-col gap-2 border-t border-zinc-200 bg-background py-3 dark:border-zinc-800">
        <ChatComposer answering={answering} onSend={ask} onStop={stop} />
        <Disclaimer />
      </div>
    </main>
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
 * The turns of the conversation and the one answer that may be streaming in. Only the latest
 * request updates the turns, so an answer that was replaced can't change the one replacing it.
 */
function useConversation(initialQuestion?: string) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [sent, setSent] = useState(0);
  const controllerRef = useRef<AbortController | null>(null);
  const answering = turns.at(-1)?.state === "answering";

  useEffect(() => () => controllerRef.current?.abort(), []);

  const answer = useCallback(async (question: string, earlier: Turn[]) => {
    const controller = new AbortController();
    controllerRef.current = controller;
    const updateLatest = (change: (turn: Turn) => Turn) => {
      if (controllerRef.current !== controller) return;
      setTurns((current) => [...current.slice(0, -1), change(current[current.length - 1])]);
    };

    setTurns([...earlier, startTurn(question)]);
    setSent((count) => count + 1);
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
  }, []);

  useEffect(() => {
    if (initialQuestion) answer(initialQuestion, []);
  }, [initialQuestion, answer]);

  const ask = (question: string) => {
    if (!answering) answer(question, turns);
  };
  const retry = () => answer(turns[turns.length - 1].question, turns.slice(0, -1));
  const stop = () => controllerRef.current?.abort();

  return { turns, answering, sent, ask, retry, stop };
}
