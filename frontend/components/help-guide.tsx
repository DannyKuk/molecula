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

type Topic = {
  title: string;
  description: string;
  examples: string[];
};

const TOPICS: Topic[] = [
  {
    title: "How a drug works",
    description: "What it is for and how it acts in the body.",
    examples: ["How does imatinib work?", "What is atorvastatin used for?"],
  },
  {
    title: "Targets",
    description: "The proteins a drug binds to, from ChEMBL.",
    examples: ["What does sildenafil bind to?", "Which targets does celecoxib act on?"],
  },
  {
    title: "3D structures",
    description: "The drug bound in its target's pocket, from the Protein Data Bank.",
    examples: ["Show oseltamivir bound to its target in 3D."],
  },
  {
    title: "Label facts, with sources",
    description: "Warnings, side effects and interactions from the FDA drug label.",
    examples: [
      "What are the common side effects of metformin?",
      "What does the warfarin label warn about?",
    ],
  },
];

const WONT_ANSWER = [
  "How much of a medicine you personally should take, or whether to start or stop one. Ask a pharmacist or doctor.",
  "Doses meant to harm someone.",
  "How to make a drug.",
];

/** What Molecula can and can't answer, where its data comes from, and questions to try. */
export function HelpGuide({ onAsk }: { onAsk: (question: string) => void }) {
  return (
    <div className="flex flex-col gap-6 text-sm">
      <section className="flex flex-col gap-3">
        <h3 className="text-base font-semibold">What you can ask</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          {TOPICS.map((topic) => (
            <TopicCard key={topic.title} topic={topic} onAsk={onAsk} />
          ))}
        </div>
      </section>
      <section className="flex flex-col gap-2">
        <h3 className="text-base font-semibold">What Molecula won&apos;t answer</h3>
        <ul className="list-disc space-y-1 pl-5 text-ink-2">
          {WONT_ANSWER.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <p className="font-medium">
          If someone may have taken too much of a medicine, call your local emergency number (911 in
          the US, 112 in the EU) or poison control now.
        </p>
      </section>
      <section className="flex flex-col gap-2 text-ink-2">
        <h3 className="text-base font-semibold text-foreground">Where the answers come from</h3>
        <p>
          Label facts come from the FDA drug labels (the same text as on DailyMed), chemical data
          from PubChem, targets from ChEMBL and 3D structures from the Protein Data Bank. Molecula
          answers only about the{" "}
          <Link href="/drugs" className="font-medium underline underline-offset-4">
            supported drugs
          </Link>
          .
        </p>
        <p>
          A small tag after a fact, like &ldquo;Gleevec · Warnings and cautions&rdquo;, names the
          label section it comes from. Point at it to read the passage, or click it to see the
          passage with the answer&apos;s other sources. Check the passage before relying on the
          fact.
        </p>
        <p>
          The evidence behind an answer sits in a panel beside the chat, or in a sheet from the
          bottom on a phone: the 3D view, the sources with a link to each label on DailyMed, and the
          steps Molecula took. The pills under each question open it on that answer. Click a step to
          see what it found: the label passages, the properties, the targets or the 3D complex.
        </p>
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
  const [open, setOpen] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        aria-label="Help"
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
          <DialogTitle className="text-lg font-semibold">How to use Molecula</DialogTitle>
          <DialogClose ref={closeRef} render={<Button variant="ghost" />}>
            Close
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
