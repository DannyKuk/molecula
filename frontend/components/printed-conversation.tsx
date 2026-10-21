import { useId, type ReactNode } from "react";

import type { Complex } from "@/lib/api";
import type { Source } from "@/lib/chat";
import type { Turn } from "@/lib/chat-turn";
import { isLabel, sourceEntries } from "@/lib/citations";
import { coordinationBonds } from "@/lib/complex-scene";
import { en, type Messages, useMessages } from "@/lib/messages";
import type { Picture } from "@/lib/printed-pictures";
import { structureSubtitle, structureTitle, type StructureTarget } from "@/lib/tool-cards";

import { OpenFdaCredit } from "./answer-sources";
import { Brand } from "./brand-mark";
import { Disclaimer } from "./disclaimer";
import { COLORS, type Palette } from "./structure/scene";

// The pieces of the printed conversation that the screen doesn't show. The rest of the print
// design is the `@media print` section of `app/globals.css`.

/** "October 20, 2026", or "20. Oktober 2026" for a German reader. */
function printedDate(date: Date, locale: string): string {
  return date.toLocaleDateString(locale, { year: "numeric", month: "long", day: "numeric" });
}

/** "Oct 20, 2026, 14:05": when a question was asked. */
export function askedTime(epochMs: number, locale = en.locale): string {
  return new Date(epochMs).toLocaleString(locale, {
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
  const t = useMessages();
  return (
    <section aria-label={t.print.label} className="hidden print:block">
      <div className="flex items-baseline justify-between gap-4">
        <Brand className="text-[11pt]" />
        <p className="font-mono text-[7.5pt] tracking-wider text-ink-2 uppercase tabular-nums">
          {t.print.questions(questions.length)} ·{" "}
          {t.print.printedOn(printedDate(new Date(), t.locale))}
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
  const t = useMessages();
  if (sources.length === 0) return null;
  return (
    <section aria-label={t.sources.sources} className="hidden break-inside-avoid-page print:block">
      <p className="font-mono text-[7pt] tracking-wider text-ink-3 uppercase">
        {t.sources.sources}
      </p>
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
  const t = useMessages();
  const title = structureTitle(target, t);
  return (
    <figure
      aria-label={t.print.structureOf(target.name)}
      className="hidden break-inside-avoid print:block"
    >
      <p className="font-mono text-[7pt] tracking-wider text-ink-3 uppercase">
        {t.print.structure}
      </p>
      {picture?.status === "ready" ? (
        <div className="mt-1 grid grid-cols-[58%_1fr] gap-x-4 border-t border-rule-2 pt-2">
          <div>
            {/* A data URL drawn in the browser, which next/image can't optimise. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              data-printed-picture
              src={picture.png}
              alt={t.print.pictureAlt(title)}
              className="block w-full border border-rule"
            />
            <PictureLegend
              name={target.name}
              complex={picture.complex}
              elements={picture.elements}
              t={t}
            />
          </div>
          <figcaption className="text-[8pt] leading-snug">
            <p className="text-[10pt] font-semibold">{title}</p>
            <p className="mt-0.5 font-mono text-[7.5pt] text-ink-2">
              {structureSubtitle(target, t)}
            </p>
            {target.complex?.caption && <p className="mt-2">{target.complex.caption}</p>}
          </figcaption>
        </div>
      ) : (
        <p className="mt-1 border-t border-rule-2 pt-1 text-[8pt] text-ink-2">
          {withoutPicture(target.name, picture, t)}
        </p>
      )}
    </figure>
  );
}

function withoutPicture(name: string, picture: Picture | undefined, t: Messages): string {
  if (picture?.status === "missing") return t.structure.noModel(name);
  if (picture?.status === "failed") return t.print.pictureFailed(name);
  return t.print.printFromMenu(name);
}

/** The colours of the picture, as in the 3D view's legend: the drug's carbons and `elements`, and
 * in a complex the binding site's. The swatches are SVG, because browsers leave out background
 * colours when printing. */
function PictureLegend({
  name,
  complex,
  elements,
  t,
}: {
  name: string;
  complex: Complex | null;
  elements: string[];
  t: Messages;
}) {
  const colors: Palette = COLORS.paper;
  return (
    <ul
      aria-label={t.print.colours}
      className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[7.5pt]"
    >
      <LegendItem label={t.structure.carbons(name)}>
        <circle cx="8" cy="4" r="3.5" fill={colors.drug} stroke="#16a34a" strokeWidth="0.75" />
      </LegendItem>
      {elements.map((element) => (
        <LegendItem key={element} label={t.structure.elements[element]}>
          <circle cx="8" cy="4" r="3" fill={colors.elements[element]} />
        </LegendItem>
      ))}
      {complex && <BindingSiteLegend complex={complex} colors={colors} t={t} />}
    </ul>
  );
}

function BindingSiteLegend({
  complex,
  colors,
  t,
}: {
  complex: Complex;
  colors: Palette;
  t: Messages;
}) {
  const s = t.structure;
  return (
    <>
      <LegendItem label={s.hydrogenBond}>
        <DashedLine color={colors.hbond} />
      </LegendItem>
      {coordinationBonds(complex).length > 0 && (
        <LegendItem label={s.metalBond}>
          <DashedLine color={colors.coordination} />
        </LegendItem>
      )}
      {complex.cofactors.length > 0 && (
        <LegendItem label={s.cofactor}>
          <line x1="0" y1="4" x2="16" y2="4" stroke={colors.cofactor} strokeWidth="2" />
        </LegendItem>
      )}
      <LegendItem label={s.pocket}>
        <line x1="0" y1="4" x2="16" y2="4" stroke={colors.pocket} strokeWidth="2.5" />
      </LegendItem>
    </>
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
  const t = useMessages();
  const usedLabels = turns.some((turn) => turn.sources?.some(isLabel));
  return (
    <section
      aria-label={t.print.end}
      className="mt-10 hidden break-inside-avoid border-t border-rule-2 pt-3 text-[8pt] print:block [&_p]:text-[8pt]"
    >
      <Disclaimer />
      {usedLabels && <OpenFdaCredit />}
    </section>
  );
}
