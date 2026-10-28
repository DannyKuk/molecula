"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Chat } from "@/components/chat";
import { CHAT_PARAM, QUESTION_PARAM } from "@/lib/chat-link";

/**
 * The chat for the link that opened the page. With `cacheComponents`, Next.js keeps this page
 * hidden while another one shows and brings the same chat back on the next link here, so New chat
 * on the dashboard showed the earlier chat (#392). `bfcacheId` changes on every link but not on
 * Back and Forward, which still find the chat as it was.
 */
export function LinkedChat() {
  const { bfcacheId } = useRouter();
  return <ChatFromLink key={bfcacheId} />;
}

/** The chat, asking the question a link carries (see `chatLink`) once, or opening the saved chat
 * it names (see `savedChatLink`). */
function ChatFromLink() {
  const searchParams = useSearchParams();
  const [question] = useState(() => searchParams.get(QUESTION_PARAM)?.trim() || undefined);
  const [chatId] = useState(() => searchParams.get(CHAT_PARAM) || undefined);

  useEffect(() => {
    // Dropped from the address bar so that a reload doesn't ask it again. The History API only
    // changes the address; `router.replace` would also navigate and fetch the page again.
    if (question || chatId) window.history.replaceState(null, "", "/");
  }, [question, chatId]);

  return <Chat initialQuestion={question} initialChatId={chatId} />;
}
