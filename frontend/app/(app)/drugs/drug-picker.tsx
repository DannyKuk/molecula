"use client";

import { useRouter } from "next/navigation";

import { ChatDrawer, ChatSidebar } from "@/components/chat-sidebar";
import { Disclaimer } from "@/components/disclaimer";
import { useSavedChats } from "@/components/saved-chats";
import { SupportedDrugsLoader } from "@/components/supported-drugs-loader";
import type { ChatHistory } from "@/lib/chat-history";
import { chatLink } from "@/lib/chat-link";
import { useMessages } from "@/lib/messages";

/** The supported drugs page: the saved chats beside it, and the list, where picking a drug asks
 * the chat about it. */
export function DrugsPage({ history }: { history?: ChatHistory }) {
  const t = useMessages();
  const router = useRouter();
  const chats = useSavedChats(history);
  return (
    <div className="flex flex-1">
      <ChatSidebar {...chats} />
      <main className="mx-auto flex w-full max-w-3xl min-w-0 flex-1 flex-col gap-6 px-4 py-8 sm:px-6 sm:py-12">
        <ChatDrawer {...chats} />
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold tracking-tight">{t.drugs.title}</h1>
          <p className="text-ink-2">{t.drugs.intro}</p>
        </div>
        <SupportedDrugsLoader onAsk={(question) => router.push(chatLink(question))} />
        <footer className="mt-auto border-t border-rule pt-6">
          <Disclaimer />
        </footer>
      </main>
    </div>
  );
}
