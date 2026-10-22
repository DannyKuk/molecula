"use client";

import { cn } from "cn";
import { CircleCheck, CircleX } from "lucide-react";
import { useState } from "react";

import {
  type Benchmark,
  type Question,
  type Scope,
  type TopPassage,
  SCOPES,
  answerRanges,
  isHit,
  passageSource,
  previewWindow,
  rankText,
  sectionName,
  topPassages,
} from "@/lib/embedding-benchmark";

export function Pill({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs whitespace-nowrap text-ink-2">
      {children}
    </span>
  );
}

export function AppBadge({ children = "used by the app" }: { children?: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full bg-app-model px-2 py-0.5 text-xs font-medium whitespace-nowrap text-app-model-foreground">
      {children}
    </span>
  );
}

const MARK = "rounded-[3px] bg-evidence px-0.5 text-evidence-foreground";

/** One question: its answer key and what each model ranked first, grouped by passage. */
export function QuestionView({
  benchmark,
  question,
  scope,
}: {
  benchmark: Benchmark;
  question: Question;
  scope: Scope;
}) {
  const passages = topPassages(benchmark, question);
  const found = benchmark.models.filter((m) =>
    isHit(benchmark.ranks[m.label][scope][question.index]),
  ).length;
  const { app } = benchmark;

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className="flex flex-wrap items-center gap-1.5">
        <Pill>{sectionName(question.section_group)}</Pill>
        <Pill>{question.drug}</Pill>
        <span className="text-xs text-ink-2">
          Question {question.index + 1} of {benchmark.questions.length}
        </span>
      </div>
      <p className="text-lg/relaxed font-semibold tracking-tight">{question.question}</p>
      <div className="flex flex-col gap-1.5 border-l-3 border-rule-2 py-0.5 pl-3 text-sm">
        <span className="text-xs text-ink-2">
          Answer key: a passage counts as a hit if it contains
        </span>
        <blockquote>
          “<mark className={MARK}>{question.evidence}</mark>”
        </blockquote>
        {question.pooled_evidence.length > 0 && (
          <>
            <span className="text-xs text-ink-2">
              or, found later in other words ({question.pooled_evidence.length}):
            </span>
            {question.pooled_evidence.map((text) => (
              <blockquote key={text} className="text-ink-2">
                “{text}”
              </blockquote>
            ))}
          </>
        )}
      </div>
      <p className="text-sm">
        <strong>
          {found} of {benchmark.models.length} models
        </strong>{" "}
        put a passage with the answer in their top 5 ({SCOPES[scope].toLowerCase()}).
        {app &&
          ` ${app.name}, the model the app uses: ${rankText(benchmark.ranks[app.label][scope][question.index])}.`}
      </p>
      <div className="flex flex-col gap-2.5">
        <h3 className="font-semibold">What each model ranked first</h3>
        <p className="text-xs text-ink-2">
          The top passage within {question.drug}&apos;s labels. {passages.length} different
          passages; models that picked the same one share a card.
        </p>
        {passages.map((top) => (
          <PassageCard key={top.id} question={question} top={top} />
        ))}
      </div>
    </div>
  );
}

function PassageCard({ question, top }: { question: Question; top: TopPassage }) {
  const [whole, setWhole] = useState(false);
  const { text } = top.passage;
  const ranges = answerRanges(question, text);
  const [from, to] = whole ? [0, text.length] : previewWindow(text, ranges);
  const Verdict = top.holdsAnswer ? CircleCheck : CircleX;

  return (
    <article
      className={cn(
        "flex min-w-0 flex-col gap-2 border-l-2 border-rule py-1 pl-3",
        top.holdsAnswer && "border-ink-3",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-x-2.5 gap-y-1.5">
        <span className="text-[0.8125rem] font-medium [overflow-wrap:anywhere]">
          {passageSource(top.passage)}
        </span>
        <span
          className={cn(
            "inline-flex items-center gap-1 text-xs font-medium whitespace-nowrap",
            !top.holdsAnswer && "text-ink-2",
          )}
        >
          <Verdict aria-hidden className="size-3.5" />
          {top.holdsAnswer ? "Holds the answer" : "Doesn't hold the answer"}
        </span>
      </div>
      <ul aria-label="Models that ranked it first" className="flex flex-wrap gap-1">
        {top.models.map((m) => (
          <li
            key={m.label}
            className={cn(
              "rounded-full border px-2 py-px text-[0.72rem] whitespace-nowrap text-ink-2",
              m.isApp &&
                "border-transparent bg-app-model font-semibold text-app-model-foreground dark:text-app-model-foreground",
            )}
          >
            {m.isApp ? `${m.name} (app)` : m.name}
          </li>
        ))}
      </ul>
      <p className="text-[0.8125rem]/5 whitespace-pre-wrap text-ink-2 [overflow-wrap:anywhere]">
        {from > 0 && "… "}
        <MarkedText text={text} ranges={ranges} from={from} to={to} />
        {to < text.length && " …"}
      </p>
      {(from > 0 || to < text.length || whole) && (
        <button
          type="button"
          onClick={() => setWhole(!whole)}
          className="self-start text-[0.8125rem] underline underline-offset-4"
        >
          {whole
            ? "Show less"
            : `Show the whole passage (${text.length.toLocaleString("en-US")} characters)`}
        </button>
      )}
    </article>
  );
}

function MarkedText({
  text,
  ranges,
  from,
  to,
}: {
  text: string;
  ranges: [number, number][];
  from: number;
  to: number;
}) {
  const parts: React.ReactNode[] = [];
  let pos = from;
  for (const [start, end] of ranges) {
    if (end <= from || start >= to) continue;
    const s = Math.max(start, from);
    const e = Math.min(end, to);
    if (s > pos) parts.push(text.slice(pos, s));
    parts.push(
      <mark key={s} className={MARK}>
        {text.slice(s, e)}
      </mark>,
    );
    pos = e;
  }
  if (pos < to) parts.push(text.slice(pos, to));
  return <>{parts}</>;
}
