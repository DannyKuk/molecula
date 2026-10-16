"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Chat } from "@/components/chat";
import { QUESTION_PARAM } from "@/lib/chat-link";

/** The chat, asking the question a link carries (see `chatLink`) once. */
export function LinkedChat() {
  const searchParams = useSearchParams();
  const [question] = useState(() => searchParams.get(QUESTION_PARAM)?.trim() || undefined);

  useEffect(() => {
    // Dropped from the address bar so that a reload doesn't ask it again. The History API only
    // changes the address; `router.replace` would also navigate and fetch the page again.
    if (question) window.history.replaceState(null, "", "/");
  }, [question]);

  return <Chat initialQuestion={question} />;
}
