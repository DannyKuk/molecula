"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { SupportedDrugsLoader } from "@/components/supported-drugs-loader";
import { chatLink } from "@/lib/chat-link";
import { useMessages } from "@/lib/messages";

/** The supported drugs list, where picking a drug asks the chat on the home page about it. */
export function DrugPicker() {
  const router = useRouter();
  return <SupportedDrugsLoader onAsk={(question) => router.push(chatLink(question))} />;
}

/** The way back to the chat, the page title and what the list is for. */
export function DrugsIntro() {
  const t = useMessages();
  return (
    <>
      <Link href="/" className="self-start text-sm text-ink-2 underline-offset-4 hover:underline">
        {t.drugs.back}
      </Link>
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">{t.drugs.title}</h1>
        <p className="text-ink-2">{t.drugs.intro}</p>
      </div>
    </>
  );
}
