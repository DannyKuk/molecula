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
  SECTION_BOOST,
  WHO,
  type Who,
} from "@/lib/answer-flow";
import type { ChatHistory } from "@/lib/chat-history";

import { ChatDrawer, ChatSidebar } from "../chat-sidebar";
import { Disclaimer } from "../disclaimer";
import { useSavedChats } from "../saved-chats";
import { BoostBars } from "./boost-bars";
import { FlowLineStep as Step } from "./flow-line";
import { WhoTag } from "./who-tag";

const EMBEDDINGS_DECISION_URL =
  "https://github.com/DannyKuk/molecula/blob/main/docs/decisions/embeddings.md";

/** The guide page: one fixed question followed through every step, each marked by who does it. */
export function HowItAnswers({ history }: { history?: ChatHistory }) {
  const chats = useSavedChats(history);
  return (
    <div className="flex flex-1">
      <ChatSidebar {...chats} />
      <main className="mx-auto flex w-full max-w-3xl min-w-0 flex-1 flex-col gap-10 px-4 py-8 sm:px-6 sm:py-12">
        <ChatDrawer {...chats} />
        <header className="flex flex-col gap-3">
          <Eyebrow>One question, start to finish</Eyebrow>
          <h1 className="text-2xl font-semibold tracking-tight">How Molecula answers a question</h1>
          <p className="max-w-prose text-sm text-ink-2">
            This follows one real question, “{EXAMPLE_QUESTION}”, through every step. The tag on
            each step says who does it. Most steps are plain code; the AI is used in only a few
            places.
          </p>
          <dl aria-label="Who does a step" className="flex flex-col gap-1.5 text-[13.5px]">
            {(Object.keys(WHO) as Who[]).map((who) => (
              <div key={who} className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
                <dt>
                  <WhoTag who={who} />
                </dt>
                <dd className="text-ink-2">{WHO[who].meaning}</dd>
              </div>
            ))}
          </dl>
        </header>

        <Section title="The flow">
          <ol aria-label="Steps" className="flex flex-col">
            <Step number="0" title="You ask" who={null} passes="the question">
              <p>“{EXAMPLE_QUESTION}”</p>
            </Step>
            {FLOW_STEPS.map((step) => (
              <FlowItem key={step.id} step={step} />
            ))}
          </ol>
        </Section>

        <Section eyebrow="Step 5 up close" title="What the +0.15 did to the warfarin question">
          <p>
            These are the 5 passages from the real run. The two interactions passages scored lowest
            on similarity alone, and the bonus moves them to the top.
          </p>
          <BoostBars
            passages={boostedRanking(EXAMPLE_PASSAGES, SECTION_BOOST)}
            boost={SECTION_BOOST}
          />
          <p className="text-[13px] text-ink-3">
            The chat model still reads all 5 passages. In this run its answer cited [3], a nursing
            mothers passage: the bonus decides the order and which passages make the cut, the chat
            model decides which ones to use.
          </p>
        </Section>

        <Section eyebrow="Where 0.15 comes from" title="A fixed setting, chosen by testing">
          <p>
            The size of the bonus is one setting, <Code>RETRIEVAL_SECTION_GROUP_BOOST</Code>. It is
            the same for every question and nothing changes it while the app runs. It was picked
            with 94 test questions whose answering passage is known: for each bonus size, how often
            that passage made the top 5, with the chat model&apos;s section guesses and with the
            right section every time.
          </p>
          <div className="thin-scrollbar overflow-x-auto border-y border-rule">
            <table className="w-full text-[13.5px] tabular-nums">
              <thead>
                <tr className="font-mono text-[10.5px] tracking-wider whitespace-nowrap text-ink-3 uppercase">
                  <th className="py-2.5 pr-6 text-left font-medium">Bonus</th>
                  <th className="py-2.5 pr-6 text-left font-medium">Guessed</th>
                  <th className="py-2.5 pr-6 text-left font-medium">Always right</th>
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
                    <td className="py-2 pr-6">{row.bonus}</td>
                    <td className="py-2 pr-6">{percent(row.guessed)}</td>
                    <td className="py-2 pr-6">{percent(row.alwaysRight)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p>
            The last row is why it is a bonus and not a hard rule. The chat model guesses the wrong
            section for 20 of the 94 questions, and searching only that section then hides the
            answer. With the bonus the other sections still compete, so a wrong guess costs less.
            0.15 is the smallest bonus that comes within one question of the hard rule when the
            guess is right; above 0.08 the real result stays at 90–91%.
          </p>
          <p className="text-[13px] text-ink-3">
            Measured for bge-m3 in <Code>docs/evals/chat-model-filters-2026-10-12.md</Code>. In
            hybrid search mode, which is off by default, the keyword and embedding rankings are
            merged by place, and the bonus only changes the order of the embedding ranking.
          </p>
          <p className="text-[13px] text-ink-3">
            The cloud setup, for a server too small for bge-m3, embeds with gemini-embedding-2 and
            gives no bonus. Measured the same way, Gemini put the answering passage in the top 5 for
            98% of the questions with no bonus and for 91% with +0.15: it finds the right section
            without help, so the bonus only let a wrong guess push the answer out. On such an
            instance the Flow tab calls this step Keep the top 5. The numbers are in{" "}
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

        <Section title="In one sentence">
          <p className="border-l-[3px] border-signal py-1 pl-3.5 text-[15px]">
            “Before searching, the chat model guesses which part of the label holds the answer. The
            embedder scores the passages by meaning, and our code gives the guessed part a fixed
            +0.15 head start before keeping the top 5. We picked 0.15 by testing on 94 questions
            with known answers.”
          </p>
        </Section>

        <footer className="mt-auto border-t border-rule pt-6">
          <Disclaimer />
        </footer>
      </main>
    </div>
  );
}

function FlowItem({ step }: { step: FlowStep }) {
  return (
    <Step id={step.id} number={step.number} title={step.title} who={step.who} passes={step.passes}>
      <p>{step.text}</p>
      {step.call && <Code>{step.call}</Code>}
      {step.aside && <p className="text-[13px] text-ink-3">{step.aside}</p>}
      {step.onSteps && (
        <p className="text-xs text-ink-3">
          On the Steps tab: <span className="font-medium text-ink-2">{step.onSteps}</span>
        </p>
      )}
    </Step>
  );
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

function percent(share: number): string {
  return `${Math.round(share * 100)}%`;
}
