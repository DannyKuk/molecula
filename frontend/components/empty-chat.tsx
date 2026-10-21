"use client";

import Link from "next/link";

import { useMessages } from "@/lib/messages";

import { HelpSheet } from "./help-guide";

/** The empty chat: what to ask, four questions to try, and where the rest is explained. */
export function EmptyChat({ onAsk }: { onAsk: (question: string) => void }) {
  const t = useMessages();
  return (
    <section className="flex flex-col pt-6 sm:pt-10">
      <p className="text-base">{t.chat.intro}</p>
      <h2 className="mt-6 mb-1.5 font-mono text-[11px] tracking-wider text-ink-3 uppercase">
        {t.chat.try}
      </h2>
      <ul className="border-b border-rule">
        {t.chat.examples.map(({ kind, question }) => (
          <li key={question} className="border-t border-rule">
            <button
              type="button"
              onClick={() => onAsk(question)}
              className="group flex w-full items-baseline gap-3 px-1 py-2.5 text-left hover:bg-panel focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3"
            >
              <span aria-hidden className="w-24 shrink-0 font-mono text-[11px] text-ink-3">
                {kind}
              </span>
              <span className="min-w-0 flex-1">{question}</span>
              <span aria-hidden className="text-ink-3 opacity-0 group-hover:opacity-100">
                ↵
              </span>
            </button>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-[13px] text-ink-2">
        {t.chat.onlySupported}{" "}
        <Link href="/drugs" className="text-foreground underline underline-offset-4">
          {t.chat.supportedDrugs}
        </Link>
        {" · "}
        {t.chat.noDosing}
        {" · "}
        <HelpSheet
          trigger={
            <button
              type="button"
              className="text-foreground underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3"
            />
          }
          onAsk={onAsk}
        >
          {t.help.title}
        </HelpSheet>
      </p>
    </section>
  );
}
