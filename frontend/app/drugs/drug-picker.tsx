"use client";

import { useRouter } from "next/navigation";

import { SupportedDrugsLoader } from "@/components/supported-drugs-loader";
import { chatLink } from "@/lib/chat-link";

/** The supported drugs list, where picking a drug asks the chat on the home page about it. */
export function DrugPicker() {
  const router = useRouter();
  return <SupportedDrugsLoader onAsk={(question) => router.push(chatLink(question))} />;
}
