"use client";

import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";

import { StepDot } from "@/components/step-dot";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { type Messages, useMessages } from "@/lib/messages";
import type { Card } from "@/lib/tool-cards";

import { ComplexCard, NoComplexCard } from "./complex-card";
import { DrugCard } from "./drug-card";
import { LabelsCard } from "./labels-card";
import { InvalidCard, NotSupportedCard } from "./problem-cards";
import { PropertiesCard } from "./properties-card";
import { TargetsCard } from "./targets-card";

type ShownCard = Exclude<Card, { kind: "pending" }>;

/**
 * A step that ran a tool. It looks like every other step, a mark and its text, with a short
 * summary of the result on the line under it; clicking it opens what the tool returned.
 */
export function ToolCard({
  text,
  card,
  answer,
  current,
}: {
  text: string;
  card: ShownCard;
  answer: string;
  current: boolean;
}) {
  const t = useMessages();
  return (
    <Collapsible>
      <CollapsibleTrigger className="group grid grid-cols-[auto_1fr] items-center gap-x-2 gap-y-0.5 rounded text-left text-ink-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3">
        <StepDot current={current} />
        <span className="flex items-center gap-1">
          <span className="underline-offset-4 group-hover:underline">{text}</span>
          <ChevronRight
            aria-hidden
            className="size-3.5 shrink-0 transition-transform group-data-[panel-open]:rotate-90"
          />
        </span>
        <span className="col-start-2 font-mono text-xs text-ink-3">{summary(card, t)}</span>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-1.5 mb-2 ml-[2px] border-l border-rule pl-4">
        {body(card, answer)}
      </CollapsibleContent>
    </Collapsible>
  );
}

function summary(card: ShownCard, { cards: t, quote }: Messages): ReactNode {
  switch (card.kind) {
    case "invalid":
      return <Badge tone="error">{t.rejected}</Badge>;
    case "not_supported":
      return <Badge tone="warning">{t.notSupported}</Badge>;
    case "drug":
      return `${quote(card.result.query)} → ${card.result.name}`;
    case "properties": {
      if (card.drugs.length > 1) return t.sideBySide;
      const drug = card.drugs[0];
      return drug.status === "found"
        ? `${drug.compound.formula} · ${drug.compound.molecular_weight} g/mol`
        : t.notSupported;
    }
    case "targets": {
      const count = card.result.targets.length;
      return count === 0 ? t.noMechanism : t.targets(count);
    }
    case "complex":
      return [card.result.pdb_id, card.result.target].filter(Boolean).join(" · ");
    case "no_complex":
      return t.noStructure;
    case "labels":
      return t.passages(card.result.passages.length);
  }
}

function body(card: ShownCard, answer: string): ReactNode {
  switch (card.kind) {
    case "invalid":
      return <InvalidCard errors={card.errors} />;
    case "not_supported":
      return <NotSupportedCard drugs={card.drugs} />;
    case "drug":
      return <DrugCard result={card.result} />;
    case "properties":
      return <PropertiesCard drugs={card.drugs} />;
    case "targets":
      return <TargetsCard result={card.result} />;
    case "complex":
      return <ComplexCard result={card.result} />;
    case "no_complex":
      return <NoComplexCard result={card.result} />;
    case "labels":
      return (
        <LabelsCard
          result={card.result}
          drug={card.drug}
          section={card.section}
          trace={card.trace}
          answer={answer}
        />
      );
  }
}

function Badge({ tone, children }: { tone: "warning" | "error"; children: ReactNode }) {
  const colors =
    tone === "warning"
      ? "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200"
      : "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300";
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${colors}`}>{children}</span>
  );
}
