import { useId, type ReactNode } from "react";

import type { Complex } from "@/lib/api";
import type { Source } from "@/lib/chat";
import type { Turn } from "@/lib/chat-turn";
import { isLabel, sourceEntries } from "@/lib/citations";
import { coordinationBonds } from "@/lib/complex-scene";
import type { Picture } from "@/lib/printed-pictures";
import { structureSubtitle, structureTitle, type StructureTarget } from "@/lib/tool-cards";

import { OpenFdaCredit } from "./answer-sources";
import { Disclaimer } from "./disclaimer";
import { COLORS } from "./structure/scene";

// The pieces of the printed conversation that the screen doesn't show. The rest of the print
// design is the `@media print` section of `app/globals.css`.

/** "October 20, 2026". */
function printedDate(date: Date): string {
  return date.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
}

/** "Oct 20, 2026, 14:05": when a question was asked. */
export function askedTime(epochMs: number): string {
  return new Date(epochMs).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
}

/** The head of the first page: Molecula, how many questions and when it was printed, a ruler,
 * then the chat's title when it was renamed; otherwise it is the first question, which follows. */
export function PrintedHeader({ title, questions }: { title: string; questions: string[] }) {
  const count = questions.length;
  return (
    <section aria-label="Printed conversation" className="hidden print:block">
      <div className="flex items-baseline justify-between gap-4">
        <p className="flex items-center gap-1.5 text-[11pt] font-semibold tracking-tight">
          <SignalLight />
          Molecula
        </p>
        <p className="font-mono text-[7.5pt] tracking-wider text-ink-2 uppercase tabular-nums">
          {count === 1 ? "1 question" : `${count} questions`} · Printed on {printedDate(new Date())}
        </p>
      </div>
      <Ruler />
      {title !== questions[0] && (
        <h2 className="mt-6 text-[19pt] leading-tight font-semibold tracking-tight break-words">
          {title}
        </h2>
      )}
    </section>
  );
}

/** The orange status light of the instrument look. It is drawn, not filled, because browsers leave
 * out background colours when printing unless asked to keep them. */
function SignalLight() {
  return (
    <svg aria-hidden viewBox="0 0 6 6" className="size-[6px] text-signal">
      <circle cx="3" cy="3" r="3" fill="currentColor" />
    </svg>
  );
}

/** A fine scale across the page, every tenth tick longer, like the edge of an instrument. */
function Ruler() {
  const ticks = useId();
  return (
    <svg aria-hidden className="mt-2 block h-[7px] w-full text-rule-2">
      <defs>
        <pattern id={ticks} width="60" height="7" patternUnits="userSpaceOnUse">
          <line x1="0.5" y1="0" x2="0.5" y2="7" stroke="currentColor" />
          {[6, 12, 18, 24, 30, 36, 42, 48, 54].map((x) => (
            <line key={x} x1={x + 0.5} y1="0" x2={x + 0.5} y2="3" stroke="currentColor" />
          ))}
        </pattern>
      </defs>
      <line x1="0" y1="0.5" x2="100%" y2="0.5" stroke="currentColor" />
      <rect width="100%" height="7" fill={`url(#${ticks})`} />
    </svg>
  );
}

/** Every source of the answer with its number and link, where the evidence panel doesn't print. */
export function PrintedSources({ sources }: { sources: Source[] }) {
  if (sources.length === 0) return null;
  return (
    <section aria-label="Sources" className="hidden break-inside-avoid-page print:block">
      <p className="font-mono text-[7pt] tracking-wider text-ink-3 uppercase">Sources</p>
      <ul className="mt-1 grid grid-cols-[max-content_1fr] border-t border-rule-2">
        {sourceEntries(sources).map(({ refs, where, what, url }) => (
          <li
            key={url + what}
            className="col-span-2 grid break-inside-avoid grid-cols-subgrid gap-x-3 border-b border-rule py-1 text-[8pt] leading-snug"
          >
            <span className="font-mono font-semibold text-signal tabular-nums">
              {refs.length > 0 && `[${refs.join(", ")}]`}
            </span>
            <span className="min-w-0">
              {where} – {what}
              <span className="block font-mono text-[6.5pt] break-all text-ink-3">{url}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * A drug the answer showed in 3D, as a still picture of the view's start with what it shows and a
 * colour legend. Without a picture it prints one line saying why: the drug has no 3D model, the
 * picture couldn't be drawn, or it was never drawn because the print didn't start from the menu.
 */
export function PrintedStructure({
  target,
  picture,
}: {
  target: StructureTarget;
  picture: Picture | undefined;
}) {
  const title = structureTitle(target);
  return (
    <figure
      aria-label={`3D structure of ${target.name}`}
      className="hidden break-inside-avoid print:block"
    >
      <p className="font-mono text-[7pt] tracking-wider text-ink-3 uppercase">3D structure</p>
      {picture?.status === "ready" ? (
        <div className="mt-1 grid grid-cols-[58%_1fr] gap-x-4 border-t border-rule-2 pt-2">
          <div>
            {/* A data URL drawn in the browser, which next/image can't optimise. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              data-printed-picture
              src={picture.png}
              alt={`${title}, as the 3D view first shows it`}
              className="block w-full border border-rule"
            />
            {picture.complex && <PictureLegend name={target.name} complex={picture.complex} />}
          </div>
          <figcaption className="text-[8pt] leading-snug">
            <p className="text-[10pt] font-semibold">{title}</p>
            <p className="mt-0.5 font-mono text-[7.5pt] text-ink-2">{structureSubtitle(target)}</p>
            {target.complex?.caption && <p className="mt-2">{target.complex.caption}</p>}
          </figcaption>
        </div>
      ) : (
        <p className="mt-1 border-t border-rule-2 pt-1 text-[8pt] text-ink-2">
          {withoutPicture(target.name, picture)}
        </p>
      )}
    </figure>
  );
}

function withoutPicture(name: string, picture: Picture | undefined): string {
  if (picture?.status === "missing") {
    return `No 3D model: Molecula has them for small-molecule drugs only, and ${name} is too large.`;
  }
  if (picture?.status === "failed") return `The 3D picture of ${name} couldn't be drawn.`;
  return `For the 3D picture of ${name}, print from the chat's export menu ("Print or save as PDF").`;
}

/** The colours of the binding site, as in the 3D view's legend. The swatches are SVG, because
 * browsers leave out background colours when printing. */
function PictureLegend({ name, complex }: { name: string; complex: Complex }) {
  const colors = COLORS.paper;
  return (
    <ul aria-label="Colours" className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[7.5pt]">
      <LegendItem label={name}>
        <circle cx="8" cy="4" r="3.5" fill={colors.drug} stroke="#16a34a" strokeWidth="0.75" />
      </LegendItem>
      <LegendItem label="hydrogen bond">
        <DashedLine color={colors.hbond} />
      </LegendItem>
      {coordinationBonds(complex).length > 0 && (
        <LegendItem label="metal bond">
          <DashedLine color={colors.coordination} />
        </LegendItem>
      )}
      {complex.cofactors.length > 0 && (
        <LegendItem label="cofactor">
          <line x1="0" y1="4" x2="16" y2="4" stroke={colors.cofactor} strokeWidth="2" />
        </LegendItem>
      )}
      <LegendItem label="residues within 4 Å">
        <line x1="0" y1="4" x2="16" y2="4" stroke={colors.pocket} strokeWidth="2.5" />
      </LegendItem>
    </ul>
  );
}

function LegendItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <li className="inline-flex items-center gap-1">
      <svg aria-hidden viewBox="0 0 16 8" className="h-[6pt] w-[12pt]">
        {children}
      </svg>
      {label}
    </li>
  );
}

function DashedLine({ color }: { color: string }) {
  return <line x1="0" y1="4" x2="16" y2="4" stroke={color} strokeWidth="2" strokeDasharray="3 2" />;
}

/** The end of the printed conversation: the disclaimer, and the openFDA credit once when an answer
 * used label text. */
export function PrintedEnd({ turns }: { turns: Turn[] }) {
  const usedLabels = turns.some((turn) => turn.sources?.some(isLabel));
  return (
    <section
      aria-label="End of the printed conversation"
      className="mt-10 hidden break-inside-avoid border-t border-rule-2 pt-3 text-[8pt] print:block [&_p]:text-[8pt]"
    >
      <Disclaimer />
      {usedLabels && <OpenFdaCredit />}
    </section>
  );
}
