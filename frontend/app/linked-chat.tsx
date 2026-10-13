"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Chat } from "@/components/chat";
import { QUESTION_PARAM } from "@/lib/chat-link";

/** The chat, asking the question a link carries (see `chatLink`) once. */
export function LinkedChat() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [question] = useState(() => searchParams.get(QUESTION_PARAM)?.trim() || undefined);

  useEffect(() => {
    // Dropped from the address bar so that a reload doesn't ask it again.
    if (question) router.replace("/", { scroll: false });
  }, [question, router]);

  return <Chat initialQuestion={question} />;
}
