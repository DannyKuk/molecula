"use client";

import { cn } from "cn";
import { ArrowLeft, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { AnswerMarkdown } from "@/components/answer-markdown";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogTitle } from "@/components/ui/dialog";
import { SheetContent } from "@/components/ui/sheet";
import {
  type Answer,
  type ChatModel,
  type ChatModelRun,
  type ComparisonKind,
  EVALS,
  type EvalName,
  VERDICTS,
  type Verdict,
  answersTo,
  formatArgs,
  formatCost,
  isFlagged,
  questionText,
  questionsOf,
  runCost,
  verdictOf,
} from "@/lib/chat-model-benchmark";
import { useMediaQuery } from "@/lib/use-media-query";

import { VerdictDot, VerdictLegend } from "./verdict-dot";

const DOC_URL = "https://github.com/DannyKuk/molecula/blob/main/docs/decisions/chat-model.md";
const MUTED = "text-ink-2";
const LEGEND: Verdict[] = ["clean", "memory", "denies", "both", "failed"];
const KIND_SHORT: Record<ComparisonKind, string> = {
  comparison: "compare",
  "3d_comparison": "3D",
  control: "control",
};

type View =
  | { kind: "model"; model: string }
  | { kind: "answer"; model: string; eval: EvalName; answer: string };

/** The chat models measured on the from-memory and comparisons evals: a summary per model, every
 * answer as a dot under its question, and the answer, its tools and its verdict beside them. */
export function ChatModelBenchmark({ run }: { run: ChatModelRun }) {
  const [evalName, setEvalName] = useState<EvalName>("from_memory");
  const [view, setView] = useState<View>(() => ({
    kind: "model",
    model: (run.models.find((m) => m.default) ?? run.models[0]).id,
  }));
  const [sheetOpen, setSheetOpen] = useState(false);
  const wide = useMediaQuery("(min-width: 1024px)");
  const panelRef = useRef<HTMLElement>(null);
  const model = run.models.find((m) => m.id === view.model)!;

  useEffect(() => {
    if (panelRef.current) panelRef.current.scrollTop = 0;
  }, [view]);

  function show(next: View) {
    setView(next);
    if (!wide) setSheetOpen(true);
  }

  const detail =
    view.kind === "model" ? (
      <ModelDetail
        run={run}
        model={model}
        onAnswer={(name, answer) => show({ kind: "answer", model: model.id, eval: name, answer })}
      />
    ) : (
      <AnswerDetail
        key={`${view.model}:${view.answer}`}
        run={run}
        model={model}
        evalName={view.eval}
        answer={model.answers[view.eval].find((a) => a.id === view.answer)!}
        onModel={() => show({ kind: "model", model: model.id })}
      />
    );

  return (
    <>
      <div className="flex max-w-3xl flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">Which chat model answers?</h1>
        <p className={MUTED}>
          The same {run.questions.from_memory.length} label questions and{" "}
          {run.models[0].comparisons.answers} comparisons went to {run.models.length} models, with
          the app&apos;s prompts and tools at {run.meta.effort} effort, and every answer was judged
          by hand: does it add a drug fact none of its tool results holds, or tell the reader
          Molecula has no data it never looked for? The app answers with {defaultName(run, false)}{" "}
          in the cloud and {defaultName(run, true)} on your own computer.
        </p>
      </div>

      <SummaryTable
        run={run}
        selected={view.model}
        onModel={(id) => show({ kind: "model", model: id })}
      />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_420px]">
        <div className="flex min-w-0 flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <h2 className="text-xl font-semibold tracking-tight">Every answer</h2>
            <div role="group" aria-label="Eval" className="flex gap-4 border-b border-rule">
              {(Object.keys(EVALS) as EvalName[]).map((name) => (
                <button
                  key={name}
                  type="button"
                  aria-pressed={name === evalName}
                  onClick={() => setEvalName(name)}
                  className={cn(
                    "-mb-px border-b-2 py-1 text-sm",
                    name === evalName ? "border-signal text-ink" : "border-transparent text-ink-2",
                  )}
                >
                  {EVALS[name]}
                </button>
              ))}
            </div>
          </div>
          <p className={cn("text-[0.8125rem]", MUTED)}>
            {evalName === "from_memory"
              ? "One answer per model to each question about one drug's label."
              : "Three answers per model to each question about two drugs; the controls ask about one."}{" "}
            Click a dot to read that answer, the tools it called and why it was flagged.
          </p>
          <VerdictLegend verdicts={LEGEND} />
          <AnswerGrid
            run={run}
            evalName={evalName}
            selected={view.kind === "answer" ? view : null}
            onAnswer={(modelId, answer) =>
              show({ kind: "answer", model: modelId, eval: evalName, answer })
            }
          />
        </div>
        <aside
          ref={panelRef}
          aria-label="Details"
          className="sticky top-4 hidden max-h-[calc(100vh-2rem)] overflow-auto border-l border-rule-2 pl-5 lg:block"
        >
          {detail}
        </aside>
      </div>

      <Dialog open={sheetOpen && !wide} onOpenChange={setSheetOpen}>
        <SheetContent side="bottom" className="bg-background">
          <header className="flex items-center gap-2 border-b px-4 py-2.5">
            <DialogClose render={<Button variant="outline" size="icon-sm" aria-label="Close" />}>
              <X />
            </DialogClose>
            <DialogTitle className="min-w-0 flex-1 truncate text-sm font-semibold">
              {model.name}
            </DialogTitle>
          </header>
          <div className="flex-1 overflow-auto p-4">{detail}</div>
        </SheetContent>
      </Dialog>

      <section className="flex flex-col gap-3 border-t pt-7">
        <h2 className="text-xl font-semibold tracking-tight">How this was measured</h2>
        <div className={cn("flex max-w-3xl flex-col gap-2.5 text-sm", MUTED)}>
          <p>
            The label questions are a fixed sample of the retrieval questions, two per part of the
            label; &ldquo;right passage&rdquo; counts the answers whose search returned the passage
            that answers the question. The comparisons ask about two drugs, a 3D view and a
            comparison, or one drug as a control; &ldquo;both drugs looked up&rdquo; counts the
            plain comparisons that searched the label or the targets of each drug.
          </p>
          <ul className="flex list-disc flex-col gap-1 pl-4">
            <li>
              <strong className="text-foreground">One run per model.</strong> Identical runs of
              gpt-oss-20b differed by two to four answers, so a difference of one or two says
              nothing.
            </li>
            <li>
              <strong className="text-foreground">Judged by hand.</strong> Subagents judged each
              answer against written rules and every flag was read again; the note under an answer
              is the verdict as written.
            </li>
            <li>
              <strong className="text-foreground">Local seconds.</strong> The local models ran in LM
              Studio on an {run.meta.gpu}, and their seconds include the label-filter call on the
              same model, which the cloud models handed to Jev, so they don&apos;t compare one to
              one.
            </li>
            <li>
              <strong className="text-foreground">Without the input check.</strong> The label
              questions went to the agent directly, so the answers about overdoses lack the
              emergency line the app puts first.
            </li>
            <li>
              <strong className="text-foreground">Cost</strong> is what OpenRouter charged for both
              runs together, {run.models[0].from_memory.answers + run.models[0].comparisons.answers}{" "}
              answers.
            </li>
          </ul>
          <p>
            The full write-up, with what each model got wrong and how to run it again:{" "}
            <a
              href={DOC_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-foreground underline underline-offset-4"
            >
              {run.meta.source}
            </a>
            .
          </p>
        </div>
      </section>
    </>
  );
}

function defaultName(run: ChatModelRun, local: boolean): string {
  return run.models.find((m) => m.default && m.local === local)?.name ?? "—";
}

function DefaultMark({ model }: { model: ChatModel }) {
  if (!model.default) return null;
  return (
    <span className="font-mono text-[10px] font-medium tracking-wide text-signal uppercase">
      {model.local ? "local default" : "cloud default"}
    </span>
  );
}

function whereText(model: ChatModel): string {
  return model.local ? `LM Studio · ${model.gpu}` : "OpenRouter";
}

const TH = "px-2.5 py-1.5 text-right font-mono text-[10px] font-medium tracking-wide uppercase";
const TD = "px-2.5 py-2 text-right tabular-nums";
const GROUP = "border-l border-rule-2";

function SummaryTable({
  run,
  selected,
  onModel,
}: {
  run: ChatModelRun;
  selected: string;
  onModel: (id: string) => void;
}) {
  const label = run.questions.from_memory.length;
  const compared = run.models[0].comparisons;
  return (
    <div className="flex flex-col gap-2">
      <div className="max-w-full overflow-x-auto">
        <table className="w-full border-collapse text-sm whitespace-nowrap">
          <thead className="text-ink-3">
            <tr>
              <th />
              <th colSpan={4} className={cn(TH, GROUP, "text-left")}>
                {label} label questions
              </th>
              <th colSpan={4} className={cn(TH, GROUP, "text-left")}>
                {compared.answers} comparisons
              </th>
              <th colSpan={2} className={cn(TH, GROUP, "text-left")}>
                Run
              </th>
            </tr>
            <tr className="border-b border-rule-2">
              <th className={cn(TH, "text-left")}>Model</th>
              <th className={cn(TH, GROUP)}>Pass</th>
              <th className={TH}>From memory</th>
              <th className={TH}>Denies data</th>
              <th className={TH}>Right passage</th>
              <th className={cn(TH, GROUP)}>No flag</th>
              <th className={TH}>Both drugs looked up</th>
              <th className={TH}>From memory</th>
              <th className={TH}>Denies data</th>
              <th className={cn(TH, GROUP)}>Seconds p50</th>
              <th className={TH}>Cost</th>
            </tr>
          </thead>
          <tbody>
            {run.models.map((m) => {
              const memory = m.from_memory;
              const comparisons = m.comparisons;
              const cost = runCost(m);
              const isSelected = m.id === selected;
              return (
                <tr
                  key={m.id}
                  className={cn(
                    "border-b border-rule hover:bg-panel",
                    isSelected && "bg-signal-soft hover:bg-signal-soft",
                  )}
                >
                  <th
                    scope="row"
                    className={cn(
                      "px-2.5 py-1.5 text-left font-normal",
                      isSelected && "shadow-[inset_3px_0_0_var(--signal)]",
                    )}
                  >
                    <button
                      type="button"
                      aria-label={`${m.name}: open its flagged answers`}
                      aria-pressed={isSelected}
                      onClick={() => onModel(m.id)}
                      className="flex flex-col items-start text-left"
                    >
                      <span className="flex items-baseline gap-2">
                        <span className="font-semibold">{m.name}</span>
                        <DefaultMark model={m} />
                      </span>
                      <span className="font-mono text-[11px] text-ink-3">{whereText(m)}</span>
                    </button>
                  </th>
                  <td className={cn(TD, GROUP)}>{memory.passed}</td>
                  <Flag count={memory.from_memory} verdict="memory" />
                  <Flag count={memory.denies_data} verdict="denies" />
                  <td className={TD}>{memory.passage_returned}</td>
                  <td className={cn(TD, GROUP)}>
                    {comparisons.passed}
                    {comparisons.errors > 0 && (
                      <span className="text-ink-3"> · {comparisons.errors} failed</span>
                    )}
                  </td>
                  <td className={TD}>
                    {comparisons.evidence.comparison.found} of {comparisons.evidence.comparison.of}
                  </td>
                  <Flag count={comparisons.from_memory} verdict="memory" />
                  <Flag count={comparisons.denies_data} verdict="denies" />
                  <td className={cn(TD, GROUP)}>
                    {memory.seconds_p50.toFixed(1)} / {comparisons.seconds_p50.toFixed(1)}
                  </td>
                  <td className={TD}>{cost === null ? "local" : formatCost(cost)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className={cn("text-xs", MUTED)}>
        Click a model for its flagged answers. Seconds: the median label question / comparison; the
        local models&apos; were measured on an {run.meta.gpu}. Pass and no flag: neither flag, and
        the answer arrived.
      </p>
    </div>
  );
}

function Flag({ count, verdict }: { count: number; verdict: "memory" | "denies" }) {
  return (
    <td className={TD}>
      <span className="inline-flex items-center justify-end gap-1.5">
        {count > 0 && <VerdictDot verdict={verdict} className="size-2" />}
        {count}
      </span>
    </td>
  );
}

function AnswerGrid({
  run,
  evalName,
  selected,
  onAnswer,
}: {
  run: ChatModelRun;
  evalName: EvalName;
  selected: { model: string; eval: EvalName; answer: string } | null;
  onAnswer: (model: string, answer: string) => void;
}) {
  const questions = questionsOf(run, evalName);
  return (
    <div className="max-w-full overflow-x-auto">
      <table className="border-separate border-spacing-0 text-xs">
        <thead>
          <tr>
            <th className="px-2 text-left align-bottom text-xs font-normal text-ink-2">Question</th>
            {run.models.map((m) => (
              <th key={m.id} className="h-[140px] px-1 align-bottom">
                <span
                  className={cn(
                    "inline-block rotate-180 py-1.5 text-[0.72rem] font-medium whitespace-nowrap text-ink-2 [writing-mode:vertical-rl]",
                    m.default && "font-semibold text-ink",
                  )}
                >
                  {m.name}
                  {m.default && <span className="text-signal"> ●</span>}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {questions.map((q) => (
            <tr key={q.id} className="group/row">
              <td className="border-t border-rule group-hover/row:bg-panel">
                <span
                  title={q.question}
                  className="flex w-40 items-baseline gap-1.5 px-2 py-1 sm:w-[220px]"
                >
                  {"kind" in q && (
                    <span className="font-mono text-[10px] text-ink-3 uppercase">
                      {KIND_SHORT[q.kind]}
                    </span>
                  )}
                  <span className="line-clamp-2">{q.question}</span>
                </span>
              </td>
              {run.models.map((m) => (
                <td key={m.id} className="border-t border-rule px-1.5 group-hover/row:bg-panel">
                  <span className="flex items-center justify-center gap-0.5">
                    {answersTo(m, evalName, q.id).map((a) => {
                      const verdict = verdictOf(a);
                      const isSelected =
                        selected?.model === m.id &&
                        selected.eval === evalName &&
                        selected.answer === a.id;
                      return (
                        <button
                          key={a.id}
                          type="button"
                          title={`${m.name}: ${VERDICTS[verdict]}`}
                          aria-label={`${q.question} · ${m.name}: ${VERDICTS[verdict]}`}
                          aria-pressed={isSelected}
                          onClick={() => onAnswer(m.id, a.id)}
                          className={cn(
                            "flex size-4 items-center justify-center rounded-full outline-offset-0 hover:outline-1 hover:outline-ink-3 focus-visible:outline-2 focus-visible:outline-ink",
                            isSelected &&
                              "outline-2 outline-signal hover:outline-2 hover:outline-signal",
                          )}
                        >
                          <VerdictDot verdict={verdict} />
                        </button>
                      );
                    })}
                  </span>
                </td>
              ))}
            </tr>
          ))}
          <tr>
            <td className="border-t border-rule-2 px-2 pt-1.5 text-ink-2">No flag</td>
            {run.models.map((m) => (
              <td
                key={m.id}
                className="border-t border-rule-2 pt-1.5 text-center text-ink-2 tabular-nums"
              >
                {m[evalName].passed} of {m[evalName].answers}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

/** One model: where it runs, both evals' counts and its flagged answers with their notes. */
function ModelDetail({
  run,
  model,
  onAnswer,
}: {
  run: ChatModelRun;
  model: ChatModel;
  onAnswer: (name: EvalName, answer: string) => void;
}) {
  const cost = runCost(model);
  return (
    <div className="flex flex-col gap-3.5">
      <div>
        <DefaultMark model={model} />
        <p className="text-lg font-semibold tracking-tight">{model.name}</p>
        <p className="text-xs text-ink-2">
          {model.id} · {whereText(model)}
          {cost !== null && ` · ${formatCost(cost)} for both runs`}
        </p>
      </div>
      {(Object.keys(EVALS) as EvalName[]).map((name) => {
        const flagged = model.answers[name].filter(isFlagged);
        return (
          <div key={name} className="flex flex-col gap-1.5">
            <h3 className="font-semibold">
              {EVALS[name]}: {flagged.length} flagged of {model[name].answers}
            </h3>
            {flagged.length === 0 && <p className={cn("text-[0.8125rem]", MUTED)}>None.</p>}
            <ul className="flex flex-col">
              {flagged.map((a) => (
                <li key={a.id}>
                  <button
                    type="button"
                    onClick={() => onAnswer(name, a.id)}
                    className="flex w-full flex-col gap-0.5 border-l-2 border-rule-2 py-1.5 pl-3 text-left text-[0.8125rem] hover:border-ink-3 hover:bg-panel"
                  >
                    <span className="flex items-center gap-1.5 font-mono text-[10px] tracking-wide text-ink-3 uppercase">
                      <VerdictDot verdict={verdictOf(a)} className="size-2" />
                      {VERDICTS[verdictOf(a)]}
                    </span>
                    <span className="font-medium">{questionText(run, name, a.question)}</span>
                    <span className={cn("line-clamp-3", MUTED)}>{a.note}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

/** One answer as the reader got it, with the tools it called and the verdict's note. */
function AnswerDetail({
  run,
  model,
  evalName,
  answer,
  onModel,
}: {
  run: ChatModelRun;
  model: ChatModel;
  evalName: EvalName;
  answer: Answer;
  onModel: () => void;
}) {
  const verdict = verdictOf(answer);
  return (
    <div className="flex flex-col gap-3">
      <button
        type="button"
        onClick={onModel}
        className="inline-flex items-center gap-1 self-start text-xs text-ink-2 hover:text-ink"
      >
        <ArrowLeft className="size-3.5" /> {model.name}
      </button>
      <div className="flex items-center gap-1.5 font-mono text-[10px] tracking-wide text-ink-3 uppercase">
        <VerdictDot verdict={verdict} className="size-2" />
        {VERDICTS[verdict]} · {EVALS[evalName]} · {answer.seconds.toFixed(1)} s
      </div>
      <p className="text-lg font-semibold tracking-tight">
        {questionText(run, evalName, answer.question)}
      </p>
      <div className="flex flex-col gap-1">
        <h3 className="text-xs font-semibold text-ink-2">Verdict</h3>
        <p className="text-[0.8125rem]">{answer.note}</p>
      </div>
      <div className="flex flex-col gap-1">
        <h3 className="text-xs font-semibold text-ink-2">Tools called</h3>
        {answer.tools.length === 0 ? (
          <p className={cn("text-[0.8125rem]", MUTED)}>None.</p>
        ) : (
          <ol className="flex flex-col gap-0.5 font-mono text-[11px] text-ink-2">
            {answer.tools.map((tool, i) => (
              <li key={i} className="break-words">
                <span className="text-ink">{tool.name}</span> {formatArgs(tool.args)}
              </li>
            ))}
          </ol>
        )}
      </div>
      <div className="flex flex-col gap-1">
        <h3 className="text-xs font-semibold text-ink-2">Answer</h3>
        {answer.text ? (
          <div className="border-l-2 border-rule-2 pl-3 [&_[data-answer]]:text-sm [&_[data-answer]]:leading-relaxed">
            <AnswerMarkdown text={answer.text} />
          </div>
        ) : (
          <p className={cn("text-[0.8125rem]", MUTED)}>No answer arrived.</p>
        )}
      </div>
    </div>
  );
}
