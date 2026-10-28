"use client";

import { cn } from "cn";

import type { Who } from "@/lib/answer-flow";
import { type Messages, useMessages } from "@/lib/messages";

import { WhoTag } from "../answer-flow/who-tag";

type Line = { text: string; tone?: "dim" | "ok" };

type TraceStep = { id: keyof Messages["landing"]["steps"]; who: Who[]; lines: Line[] };

/** The question of the recorded run, asked in English and so shown in English in both languages. */
export const TRACE_QUESTION = "How does imatinib fight leukemia?";

/** What each step returned for TRACE_QUESTION in one run through `POST /chat` with gpt-oss-20b
 * and OFFLINE=1 on 2026-10-28 (#455): the input check, the one `search_labels` call, the answer's
 * first claim with its source, and the source check's verdicts. */
export const TRACE: TraceStep[] = [
  {
    id: "guard",
    who: ["model", "code"],
    lines: [
      { text: "category   " },
      { text: "ok", tone: "ok" },
      { text: "\n1,374 tokens in · 26 out", tone: "dim" },
    ],
  },
  {
    id: "agent",
    who: ["model", "embedder"],
    lines: [
      { text: "search_labels\n  drug     imatinib · CID 5291\n  section  pharmacology\n" },
      { text: "→ 5 passages, Gleevec label", tone: "dim" },
    ],
  },
  {
    id: "answer",
    who: ["model"],
    lines: [
      { text: "“…by inhibiting the BCR-ABL\n  tyrosine kinase…” " },
      { text: "[1]", tone: "dim" },
      { text: "\n[1] Gleevec · 12.1 Mechanism\n    of Action", tone: "dim" },
    ],
  },
  {
    id: "check",
    who: ["model", "code"],
    lines: [
      { text: "claims     3\nsupported  " },
      { text: "3 of 3", tone: "ok" },
      { text: "\nunsupported ones get a mark", tone: "dim" },
    ],
  },
];

const TONES = { dim: "text-ink-3", ok: "text-ok" };

/** The recorded question followed through its four steps, each drawn like the Steps tab: a mark,
 * what the step returned, and why the step is there. */
export function QuestionTrace() {
  const t = useMessages();
  const l = t.landing;
  return (
    <div>
      <div className="mb-9 flex flex-wrap items-baseline gap-x-5 gap-y-2 border-b border-rule pb-7">
        <span className="font-mono text-xs text-ink-3">{l.oneQuestion}</span>
        <h2
          lang="en"
          className="text-[clamp(24px,2.8vw,32px)] leading-tight font-semibold tracking-tight"
        >
          {t.quote(TRACE_QUESTION)}
        </h2>
      </div>
      <ol className="grid gap-x-7 gap-y-10 md:grid-cols-2 lg:grid-cols-4">
        {TRACE.map((step, index) => (
          <li key={step.id} className="relative border-l border-rule-2 pl-5">
            <span
              aria-hidden
              className="absolute top-1 -left-[6px] size-[11px] rounded-full border-2 border-signal bg-page"
            />
            <div className="mb-2 flex flex-wrap items-center gap-1.5">
              <span className="mr-1 font-mono text-xs text-ink-3">{index + 1}</span>
              {step.who.map((who) => (
                <WhoTag key={who} who={who} />
              ))}
            </div>
            <h3 className="mb-2.5 text-[17px] font-semibold tracking-tight">
              {l.steps[step.id].title}
            </h3>
            <pre
              lang="en"
              className="mb-3 overflow-x-auto border-b border-dashed border-rule-2 pb-3 font-mono text-[12.5px] leading-relaxed text-ink"
            >
              {step.lines.map((line, i) => (
                <span key={i} className={cn(line.tone && TONES[line.tone])}>
                  {line.text}
                </span>
              ))}
            </pre>
            <p className="text-[15px] text-ink-2">{l.steps[step.id].text}</p>
          </li>
        ))}
      </ol>
      <p className="mt-8 font-mono text-xs text-ink-3">{l.recorded}</p>
    </div>
  );
}
