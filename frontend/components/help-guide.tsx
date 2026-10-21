"use client";

import { X } from "lucide-react";
import Link from "next/link";
import { type ReactElement, type ReactNode, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { SheetContent } from "@/components/ui/sheet";
import { type Messages, useMessages } from "@/lib/messages";

type Topic = Messages["help"]["topics"][number];

/** What Molecula can and can't answer, where its data comes from, and questions to try. */
export function HelpGuide({ onAsk }: { onAsk: (question: string) => void }) {
  const t = useMessages();
  return (
    <div className="flex flex-col gap-6 text-sm text-ink-2">
      <section className="flex flex-col gap-3">
        <h3 className="text-[15px] font-semibold text-foreground">{t.help.canAsk}</h3>
        <ul className="ml-[3px] flex flex-col gap-4 border-l border-rule pl-4">
          {t.help.topics.map((topic) => (
            <TopicItem key={topic.title} topic={topic} onAsk={onAsk} />
          ))}
        </ul>
      </section>
      <section className="flex flex-col gap-2">
        <h3 className="text-[15px] font-semibold text-foreground">{t.help.wontAnswerTitle}</h3>
        <ul className="list-disc space-y-1 pl-5">
          {t.help.wontAnswer.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <p className="mt-1 border-l-2 border-signal pl-3 text-foreground">{t.help.emergency}</p>
      </section>
      <section className="flex flex-col gap-2">
        <h3 className="text-[15px] font-semibold text-foreground">{t.help.sourcesTitle}</h3>
        <p>
          {t.help.sources.before}{" "}
          <Link href="/drugs" className="font-medium text-foreground underline underline-offset-4">
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

function TopicItem({ topic, onAsk }: { topic: Topic; onAsk: (question: string) => void }) {
  return (
    <li className="relative flex flex-col gap-1">
      <span aria-hidden className="absolute top-2 -left-[19.5px] size-1.5 rounded-full bg-signal" />
      <h4 className="font-semibold text-foreground">{topic.title}</h4>
      <p>{topic.description}</p>
      <ul className="flex flex-wrap gap-x-4 gap-y-1">
        {topic.examples.map((question) => (
          <li key={question}>
            <button
              type="button"
              onClick={() => onAsk(question)}
              className="text-left text-foreground underline decoration-rule-2 underline-offset-4 hover:decoration-ink-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3"
            >
              {question}
            </button>
          </li>
        ))}
      </ul>
    </li>
  );
}

/**
 * The help guide in a sheet from the right, opened by `trigger`, so the chat stays in view. Asking
 * one of its questions closes it.
 */
export function HelpSheet({
  trigger,
  children,
  onAsk,
}: {
  trigger: ReactElement;
  children: ReactNode;
  onAsk: (question: string) => void;
}) {
  const t = useMessages();
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={trigger}>{children}</DialogTrigger>
      <SheetContent side="right" className="bg-panel">
        <div className="flex items-center justify-between gap-4 border-b border-rule px-5 py-3">
          <DialogTitle className="text-[15px] font-semibold">{t.help.title}</DialogTitle>
          <DialogClose
            render={
              <Button
                variant="ghost"
                size="icon"
                aria-label={t.help.close}
                className="text-ink-2 hover:bg-rule dark:hover:bg-rule"
              />
            }
          >
            <X />
          </DialogClose>
        </div>
        <div className="thin-scrollbar min-h-0 flex-1 overflow-y-auto px-5 py-5">
          <HelpGuide
            onAsk={(question) => {
              setOpen(false);
              onAsk(question);
            }}
          />
        </div>
      </SheetContent>
    </Dialog>
  );
}
