"use client";

import { cn } from "cn";
import type { ReactNode } from "react";

import {
  BOOST_MEASUREMENTS,
  boostedRanking,
  EXAMPLE_PASSAGES,
  EXAMPLE_QUESTION,
  FLOW_STEPS,
  type FlowStep,
  type GuideWords,
  SECTION_BOOST,
  WHO,
} from "@/lib/answer-flow";
import type { ChatHistory } from "@/lib/chat-history";
import { type Messages, useMessages } from "@/lib/messages";
import { percent } from "@/lib/stats";

import { ChatDrawer, ChatSidebar } from "../chat-sidebar";
import { Disclaimer } from "../disclaimer";
import { useSavedChats } from "../saved-chats";
import { BoostBars } from "./boost-bars";
import { FlowLineStep as Step } from "./flow-line";
import { WhoTag } from "./who-tag";

const EMBEDDINGS_DECISION_URL =
  "https://github.com/DannyKuk/molecula/blob/main/docs/decisions/embeddings.md";

/** The guide page: one fixed question followed through every step, each marked by who does it.
 * The question and the label passages stay as recorded, an English run against the English
 * label. */
export function HowItAnswers({ history }: { history?: ChatHistory }) {
  const chats = useSavedChats(history);
  const t = useMessages();
  const h = t.howItAnswers;
  return (
    <div className="flex flex-1">
      <ChatSidebar {...chats} />
      <main className="mx-auto flex w-full max-w-3xl min-w-0 flex-1 flex-col gap-10 px-4 py-8 sm:px-6 sm:py-12">
        <ChatDrawer {...chats} />
        <header className="flex flex-col gap-3">
          <Eyebrow>{h.eyebrow}</Eyebrow>
          <h1 className="text-2xl font-semibold tracking-tight">{h.title}</h1>
          <p className="max-w-prose text-sm text-ink-2">{h.intro(t.quote(EXAMPLE_QUESTION))}</p>
          <dl aria-label={h.whoDoesAStep} className="flex flex-col gap-1.5 text-[13.5px]">
            {WHO.map((who) => (
              <div key={who} className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
                <dt>
                  <WhoTag who={who} />
                </dt>
                <dd className="text-ink-2">{h.whoMeaning[who]}</dd>
              </div>
            ))}
          </dl>
        </header>

        <Section title={h.theFlow}>
          <ol aria-label={t.flow.steps} className="flex flex-col">
            <Step number="0" title={h.youAsk} who={null} passes={h.theQuestion}>
              <p>{t.quote(EXAMPLE_QUESTION)}</p>
            </Step>
            {FLOW_STEPS.map((step) => (
              <FlowItem key={step.id} step={step} t={t} />
            ))}
          </ol>
        </Section>

        <Section eyebrow={h.closeUp.eyebrow} title={h.closeUp.title}>
          <p>{h.closeUp.before}</p>
          <BoostBars
            passages={boostedRanking(EXAMPLE_PASSAGES, SECTION_BOOST)}
            boost={SECTION_BOOST}
            t={t}
          />
          <p className="text-[13px] text-ink-3">{h.closeUp.after}</p>
        </Section>

        <Section eyebrow={h.setting.eyebrow} title={h.setting.title}>
          <p>
            {h.setting.lead} <Code>RETRIEVAL_SECTION_GROUP_BOOST</Code>
            {h.setting.rest}
          </p>
          <div className="thin-scrollbar overflow-x-auto border-y border-rule">
            <table className="w-full text-[13.5px] tabular-nums">
              <thead>
                <tr className="font-mono text-[10.5px] tracking-wider whitespace-nowrap text-ink-3 uppercase">
                  <th className="py-2.5 pr-6 text-left font-medium">{h.setting.bonus}</th>
                  <th className="py-2.5 pr-6 text-left font-medium">{h.setting.guessed}</th>
                  <th className="py-2.5 pr-6 text-left font-medium">{h.setting.alwaysRight}</th>
                </tr>
              </thead>
              <tbody>
                {BOOST_MEASUREMENTS.map((row) => (
                  <tr
                    key={row.bonus}
                    aria-current={row.picked || undefined}
                    className={cn(
                      "border-t border-rule",
                      row.picked && "font-semibold text-signal",
                    )}
                  >
                    <td className="py-2 pr-6">{bonusName(row.bonus, t)}</td>
                    <td className="py-2 pr-6">{percent(row.guessed, t)}</td>
                    <td className="py-2 pr-6">{percent(row.alwaysRight, t)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p>{h.setting.whyABonus}</p>
          <p className="text-[13px] text-ink-3">
            {h.setting.measuredIn} <Code>docs/evals/chat-model-filters-2026-10-12.md</Code>
            {h.setting.hybrid}
          </p>
          <p className="text-[13px] text-ink-3">
            {h.setting.cloud(t.flow.keepTitle(5))}{" "}
            <a
              href={EMBEDDINGS_DECISION_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-4"
            >
              docs/decisions/embeddings.md
            </a>
            .
          </p>
        </Section>

        <Section title={h.inOneSentence}>
          <p className="border-l-[3px] border-signal py-1 pl-3.5 text-[15px]">
            {t.quote(h.sentence)}
          </p>
        </Section>

        <footer className="mt-auto border-t border-rule pt-6">
          <Disclaimer />
        </footer>
      </main>
    </div>
  );
}

function FlowItem({ step, t }: { step: FlowStep; t: Messages }) {
  const words: GuideWords = t.flow.guide[step.id];
  return (
    <Step
      id={step.id}
      number={step.number}
      title={words.title}
      who={step.who}
      passes={words.passes}
    >
      <p>{words.text}</p>
      {step.call && <Code>{step.call}</Code>}
      {words.aside && <p className="text-[13px] text-ink-3">{words.aside}</p>}
      {step.onSteps && (
        <p className="text-xs text-ink-3">
          {t.howItAnswers.onStepsTab}{" "}
          <span className="font-medium text-ink-2">{step.onSteps(t)}</span>
        </p>
      )}
    </Step>
  );
}

function bonusName(bonus: number | "hard rule", t: Messages): string {
  if (bonus === "hard rule") return t.howItAnswers.setting.hardRule;
  if (bonus === 0) return t.howItAnswers.setting.noBonus;
  return `+${bonus.toFixed(2)}`;
}

function Section({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section aria-label={title} className="flex max-w-prose flex-col gap-3 text-sm sm:max-w-none">
      {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      {children}
    </section>
  );
}

function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <span className="font-mono text-[11px] tracking-wider text-signal uppercase">{children}</span>
  );
}

function Code({ children }: { children: ReactNode }) {
  return <code className="font-mono text-[12px] break-words">{children}</code>;
}
