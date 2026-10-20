"use client";

import { useState } from "react";

import type { ChatHistory } from "@/lib/chat-history";

import { ChatDrawer, ChatSidebar } from "../chat-sidebar";
import { Disclaimer } from "../disclaimer";
import { useSavedChats } from "../saved-chats";
import { BENCHMARKS } from "./registry";

/** The benchmark page: the saved chats beside it, a picker at the top, then the picked benchmark. */
export function Benchmarks({ history }: { history?: ChatHistory }) {
  const chats = useSavedChats(history);
  const [id, setId] = useState(BENCHMARKS[0].id);
  const benchmark = BENCHMARKS.find((b) => b.id === id) ?? BENCHMARKS[0];

  return (
    <div className="flex flex-1">
      <ChatSidebar {...chats} />
      <main className="mx-auto flex w-full max-w-6xl min-w-0 flex-1 flex-col gap-6 px-4 py-8 sm:px-6 sm:py-12">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <ChatDrawer {...chats} />
          <label className="ml-auto inline-flex items-center gap-2 text-sm text-ink-2">
            <span className="max-sm:sr-only">Benchmark</span>
            <select
              value={id}
              onChange={(e) => setId(e.target.value)}
              className="max-w-full rounded-lg border border-input bg-background px-2.5 py-1.5 text-foreground"
            >
              {BENCHMARKS.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.title}
                </option>
              ))}
            </select>
          </label>
        </div>
        {benchmark.render()}
        <footer className="mt-auto border-t border-rule pt-6">
          <Disclaimer />
        </footer>
      </main>
    </div>
  );
}
