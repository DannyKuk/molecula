"use client";

import Link from "next/link";
import { useEffect, useId, useRef } from "react";

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
        <ul className="list-disc space-y-1 pl-5 text-zinc-700 dark:text-zinc-300">
          {WONT_ANSWER.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <p className="font-medium">
          If someone may have taken too much of a medicine, call your local emergency number or
          poison control now.
        </p>
      </section>
      <section className="flex flex-col gap-2 text-zinc-700 dark:text-zinc-300">
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
          A number in brackets, like [1], points to the label passage a fact comes from. Check the
          passage before relying on the fact.
        </p>
      </section>
    </div>
  );
}

function TopicCard({ topic, onAsk }: { topic: Topic; onAsk: (question: string) => void }) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
      <h4 className="font-medium">{topic.title}</h4>
      <p className="text-zinc-600 dark:text-zinc-400">{topic.description}</p>
      <ul className="flex flex-col gap-1.5">
        {topic.examples.map((question) => (
          <li key={question}>
            <button
              type="button"
              onClick={() => onAsk(question)}
              className="w-full rounded-md bg-zinc-100 px-3 py-2 text-left hover:bg-zinc-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:bg-zinc-900 dark:hover:bg-zinc-800"
            >
              {question}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The help guide over the chat, closed with its button, Escape or a click beside it. */
export function HelpDialog({
  onAsk,
  onClose,
}: {
  onAsk: (question: string) => void;
  onClose: () => void;
}) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-20 flex items-end justify-center bg-black/40 sm:items-center sm:p-6"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(event) => event.stopPropagation()}
        className="flex max-h-[90dvh] w-full max-w-2xl flex-col gap-4 overflow-y-auto rounded-t-2xl bg-background p-4 shadow-xl sm:rounded-2xl sm:p-6"
      >
        <div className="flex items-center justify-between gap-4">
          <h2 id={titleId} className="text-lg font-semibold">
            How to use Molecula
          </h2>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="rounded-md px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-zinc-500 dark:hover:bg-zinc-900"
          >
            Close
          </button>
        </div>
        <HelpGuide
          onAsk={(question) => {
            onClose();
            onAsk(question);
          }}
        />
      </div>
    </div>
  );
}
