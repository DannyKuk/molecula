"use client";

import Link from "next/link";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { type Messages, useMessages } from "@/lib/messages";

type Topic = Messages["help"]["topics"][number];

/** What Molecula can and can't answer, where its data comes from, and questions to try. */
export function HelpGuide({ onAsk }: { onAsk: (question: string) => void }) {
  const t = useMessages();
  return (
    <div className="flex flex-col gap-6 text-sm">
      <section className="flex flex-col gap-3">
        <h3 className="text-base font-semibold">{t.help.canAsk}</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          {t.help.topics.map((topic) => (
            <TopicCard key={topic.title} topic={topic} onAsk={onAsk} />
          ))}
        </div>
      </section>
      <section className="flex flex-col gap-2">
        <h3 className="text-base font-semibold">{t.help.wontAnswerTitle}</h3>
        <ul className="list-disc space-y-1 pl-5 text-ink-2">
          {t.help.wontAnswer.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <p className="font-medium">{t.help.emergency}</p>
      </section>
      <section className="flex flex-col gap-2 text-ink-2">
        <h3 className="text-base font-semibold text-foreground">{t.help.sourcesTitle}</h3>
        <p>
          {t.help.sources.before}{" "}
          <Link href="/drugs" className="font-medium underline underline-offset-4">
            {t.help.sources.link}
          </Link>
          {t.help.sources.after}
        </p>
        <p>{t.help.tags}</p>
        <p>{t.help.panel}</p>
      </section>
    </div>
  );
}

function TopicCard({ topic, onAsk }: { topic: Topic; onAsk: (question: string) => void }) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-rule p-3">
      <h4 className="font-medium">{topic.title}</h4>
      <p className="text-ink-2">{topic.description}</p>
      <ul className="flex flex-col gap-1.5">
        {topic.examples.map((question) => (
          <li key={question}>
            <button
              type="button"
              onClick={() => onAsk(question)}
              className="w-full rounded-md bg-panel px-3 py-2 text-left hover:bg-rule focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3"
            >
              {question}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The "?" button and the help guide it opens over the chat, closed with its Close button,
 * Escape or a click beside it. */
export function HelpDialog({ onAsk }: { onAsk: (question: string) => void }) {
  const t = useMessages();
  const [open, setOpen] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        aria-label={t.help.open}
        className="flex size-9 items-center justify-center rounded-full border border-rule-2 font-semibold hover:bg-panel focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3"
      >
        ?
      </DialogTrigger>
      <DialogContent
        showCloseButton={false}
        initialFocus={closeRef}
        className="top-auto bottom-0 max-h-[90dvh] max-w-2xl translate-y-0 gap-4 overflow-y-auto rounded-b-none bg-background p-4 sm:top-1/2 sm:bottom-auto sm:max-w-2xl sm:-translate-y-1/2 sm:rounded-2xl sm:p-6"
      >
        <div className="flex items-center justify-between gap-4">
          <DialogTitle className="text-lg font-semibold">{t.help.title}</DialogTitle>
          <DialogClose ref={closeRef} render={<Button variant="ghost" />}>
            {t.help.close}
          </DialogClose>
        </div>
        <HelpGuide
          onAsk={(question) => {
            setOpen(false);
            onAsk(question);
          }}
        />
      </DialogContent>
    </Dialog>
  );
}
