"use client";

import { cn } from "cn";
import { ArrowLeft, ArrowRight, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogTitle } from "@/components/ui/dialog";
import { SheetContent } from "@/components/ui/sheet";
import { getEmbeddingSetup } from "@/lib/api";
import {
  type Benchmark,
  type EmbeddingRun,
  GROUP_NAMES,
  type InstanceModel,
  LOCAL_SETUP,
  type Scope,
  SCOPES,
  loadBenchmark,
  percent,
  showcaseQuestion,
} from "@/lib/embedding-benchmark";
import { useMediaQuery } from "@/lib/use-media-query";

import { HitGrid, RankLegend } from "./hit-grid";
import { ModelView } from "./model-view";
import { QuestionView } from "./question-view";
import { ModelRecall, RecallLegend } from "./recall-chart";
import { TradeoffTable } from "./tradeoff-table";

const DOC_URL = "https://github.com/DannyKuk/molecula/blob/main/docs/decisions/embeddings.md";

type View =
  { kind: "question"; question: number; model: string | null } | { kind: "model"; label: string };

const MUTED = "text-ink-2";

/** The embedding comparison, with the model this instance embeds with marked as the app's. */
export function EmbeddingBenchmark({ run }: { run: EmbeddingRun }) {
  const [instance, setInstance] = useState<InstanceModel>(LOCAL_SETUP);

  useEffect(() => {
    const controller = new AbortController();
    getEmbeddingSetup(controller.signal)
      .then(setInstance)
      .catch(() => {});
    return () => controller.abort();
  }, []);

  // Keyed so that another model opens on its own showcase question.
  return <BenchmarkView key={instance.embedding_model} run={run} instance={instance} />;
}

function InstanceSentence({
  benchmark,
  instance,
}: {
  benchmark: Benchmark;
  instance: InstanceModel;
}) {
  const { app } = benchmark;
  if (!app) {
    return (
      <>This instance embeds with {instance.embedding_model}, which this run didn&apos;t measure.</>
    );
  }
  const top5 = percent(app.recall_at_5.in_drug);
  if (app.group === "cloud") {
    const local = benchmark.models.find(
      (m) => m.model === LOCAL_SETUP.embedding_model && m.group !== "cloud",
    );
    return (
      <>
        This instance uses {app.name}, a cloud model, which gets {top5} of the questions into its
        top 5.
        {local &&
          ` Run on its own, the app uses ${local.name} instead, which gets ${percent(local.recall_at_5.in_drug)} on an ordinary CPU.`}
      </>
    );
  }
  return (
    <>
      The app uses {app.name}, which gets {top5} of the questions into its top 5
      {app.group === "cpu" ? " on an ordinary CPU" : " on a graphics card"}; the best GPU and cloud
      models reach 97–98%.
    </>
  );
}

/** The hit grid with a detail panel beside it (a sheet on a phone), then the recall curves, the
 * costs and how it was measured. */
function BenchmarkView({ run, instance }: { run: EmbeddingRun; instance: InstanceModel }) {
  const benchmark = useMemo(() => loadBenchmark(run, instance), [run, instance]);
  const order = benchmark.sections.flatMap((s) => s.questions.map((q) => q.index));
  const [scope, setScope] = useState<Scope>("in_drug");
  const [view, setView] = useState<View>(() => ({
    kind: "question",
    question: showcaseQuestion(benchmark),
    model: null,
  }));
  const [sheetOpen, setSheetOpen] = useState(false);
  const wide = useMediaQuery("(min-width: 1024px)");
  const hubRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (panelRef.current) panelRef.current.scrollTop = 0;
  }, [view]);

  function show(next: View) {
    setView(next);
    if (!wide) setSheetOpen(true);
  }

  function step(by: number) {
    if (view.kind !== "question") return;
    const at = order.indexOf(view.question);
    show({
      kind: "question",
      question: order[(at + by + order.length) % order.length],
      model: null,
    });
  }

  const steps = view.kind === "question" && (
    <div className="flex gap-1.5">
      <Button
        variant="outline"
        size="icon-sm"
        aria-label="Previous question"
        onClick={() => step(-1)}
      >
        <ArrowLeft />
      </Button>
      <Button variant="outline" size="icon-sm" aria-label="Next question" onClick={() => step(1)}>
        <ArrowRight />
      </Button>
    </div>
  );
  const detail =
    view.kind === "question" ? (
      <QuestionView
        key={view.question}
        benchmark={benchmark}
        question={benchmark.questions[view.question]}
        scope={scope}
      />
    ) : (
      <ModelView
        benchmark={benchmark}
        model={benchmark.models.find((m) => m.label === view.label)!}
        scope={scope}
        onQuestion={(question) => show({ kind: "question", question, model: null })}
      />
    );

  return (
    <>
      <div className="flex max-w-3xl flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">
          Which embedding model finds the answer?
        </h1>
        <p className={MUTED}>
          Every square is one question asked of one model, shaded by where the passage with the
          answer ranked. <InstanceSentence benchmark={benchmark} instance={instance} />
        </p>
      </div>

      <div
        ref={hubRef}
        className="grid scroll-mt-4 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_420px]"
      >
        <div className="flex min-w-0 flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <h2 className="text-xl font-semibold tracking-tight">
              {benchmark.questions.length} questions × {benchmark.models.length} models
            </h2>
            <div
              role="group"
              aria-label="Search"
              className="inline-flex gap-0.5 rounded-lg border p-0.5"
            >
              {(Object.keys(SCOPES) as Scope[]).map((key) => (
                <button
                  key={key}
                  type="button"
                  aria-pressed={key === scope}
                  onClick={() => setScope(key)}
                  className={cn(
                    "rounded-md px-2.5 py-0.5 text-sm",
                    key === scope ? "bg-muted font-medium" : MUTED,
                  )}
                >
                  {SCOPES[key]}
                </button>
              ))}
            </div>
          </div>
          <p className={cn("text-[0.8125rem]", MUTED)}>
            Click a question for what each model found. Click a model&apos;s name for its scores and
            the questions it missed. The number in a group&apos;s row is how many of its questions
            the model got in the top 5.
          </p>
          <RankLegend />
          <HitGrid
            benchmark={benchmark}
            scope={scope}
            selected={view.kind === "question" ? view : null}
            onQuestion={(question, model) => show({ kind: "question", question, model })}
            onModel={(label) => show({ kind: "model", label })}
          />
        </div>
        <aside
          ref={panelRef}
          aria-label="Details"
          className="sticky top-4 hidden max-h-[calc(100vh-2rem)] overflow-auto rounded-lg border p-4 lg:block"
        >
          <div className="mb-2 flex justify-end">{steps}</div>
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
              {view.kind === "question"
                ? benchmark.questions[view.question].drug
                : benchmark.models.find((m) => m.label === view.label)!.name}
            </DialogTitle>
            {steps}
          </header>
          <div className="flex-1 overflow-auto p-4">{detail}</div>
        </SheetContent>
      </Dialog>

      <section className="flex flex-col gap-3 border-t pt-7">
        <h2 className="text-xl font-semibold tracking-tight">Recall at every k, model by model</h2>
        <p className={cn("text-sm", MUTED)}>
          How often a passage with the answer is among the first k the model returns, for k from 1
          to 10. The app hands the chat model 5. Each panel is one model; the faint lines behind it
          are the other {benchmark.models.length - 1}, so you can see where it sits.
        </p>
        <RecallLegend />
        {(Object.keys(GROUP_NAMES) as (keyof typeof GROUP_NAMES)[]).map((group) => (
          <div key={group} className="flex flex-col gap-2">
            <h3 className={cn("mt-1.5 text-[0.8125rem] font-semibold", MUTED)}>
              {GROUP_NAMES[group]}
            </h3>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(160px,1fr))] gap-2.5">
              {benchmark.models
                .filter((m) => m.group === group)
                .map((m) => (
                  <button
                    key={m.label}
                    type="button"
                    aria-label={`${m.name}: open details`}
                    onClick={() => {
                      show({ kind: "model", label: m.label });
                      if (wide) hubRef.current?.scrollIntoView({ behavior: "smooth" });
                    }}
                    className={cn(
                      "flex min-w-0 flex-col gap-0.5 rounded-lg border px-2 pt-2.5 pb-1 text-left hover:border-ink-3",
                      m.isApp && "border-app-model-foreground ring-1 ring-app-model-foreground",
                    )}
                  >
                    <span className="truncate text-[0.8125rem] font-semibold">{m.name}</span>
                    <span className={cn("text-[0.72rem] tabular-nums", MUTED)}>
                      {percent(m.recall_at_5.in_drug)} in top 5{m.isApp && " · the app's model"}
                    </span>
                    <ModelRecall benchmark={benchmark} model={m} height={120} />
                  </button>
                ))}
            </div>
          </div>
        ))}
      </section>

      <section className="flex flex-col gap-3 border-t pt-7">
        <h2 className="text-xl font-semibold tracking-tight">What each model costs</h2>
        <p className={cn("text-sm", MUTED)}>
          The app has to run on an ordinary computer without a graphics card, so time on a CPU and
          the download size matter as much as the score.
        </p>
        <TradeoffTable benchmark={benchmark} />
      </section>

      <section className="flex flex-col gap-3 border-t pt-7">
        <h2 className="text-xl font-semibold tracking-tight">How this was measured</h2>
        <div className={cn("flex max-w-3xl flex-col gap-2.5 text-sm", MUTED)}>
          <p>
            Each of the {benchmark.meta.questions} questions names one drug and comes with a passage
            from that drug&apos;s label that answers it. Every model turned the{" "}
            {benchmark.meta.chunks.toLocaleString("en-US")} label passages in the app&apos;s index
            into vectors, then fetched the 10 passages closest to each question, once only among the
            drug&apos;s own passages and once over the whole index. A hit is a returned passage of
            the right drug that contains the answer.
          </p>
          <ul className="flex list-disc flex-col gap-1 pl-4">
            <li>
              <strong className="text-foreground">{benchmark.meta.questions} questions.</strong>{" "}
              Near 85% the margin of error is about ±7 points, so models within a few points of each
              other are a tie.
            </li>
            <li>
              <strong className="text-foreground">A strict answer key.</strong> A passage counts
              only if it gives the same specific fact; related or partial answers are misses, so
              every score is a little low.
            </li>
            <li>
              <strong className="text-foreground">One machine.</strong> CPU times are from one Intel
              Core Ultra 7 265K; GPU runs from one AMD RX 7900 XTX.
            </li>
          </ul>
          <p>
            The full write-up, with the pairwise tests and how to reproduce the run:{" "}
            <a
              href={DOC_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-foreground underline underline-offset-4"
            >
              docs/decisions/embeddings.md
            </a>
            .
          </p>
        </div>
      </section>
    </>
  );
}
