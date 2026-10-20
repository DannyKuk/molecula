import type { Source } from "./chat";
import type { Turn } from "./chat-turn";
import { isLabel } from "./citations";
import { cardSteps, structuresOf, type StructureTarget } from "./tool-cards";

/** The evidence panel's tabs. */
export type EvidenceTab = "3d" | "sources" | "steps";

/**
 * What the evidence panel shows: a turn's tab, by the turn's index, or the newest turn's when
 * `turn` is null. `cid` picks one of the turn's structures; `refs` are the sources a citation chip
 * opened, highlighted on the Sources tab. `fresh` marks a 3D tab the panel opened by itself, for a
 * structure that just arrived, until the reader picks a tab.
 */
export type Shown = {
  turn: number | null;
  tab: EvidenceTab;
  cid?: number;
  refs?: number[];
  fresh?: boolean;
};

/** The tab a turn opens on: its steps while it answers, else its 3D view, else its sources. */
export function defaultTab(turn: Turn): EvidenceTab {
  if (turn.state === "answering" || turn.state === "queued") return "steps";
  return structuresOf(turn.steps).length > 0 ? "3d" : "sources";
}

/** The steps the panel lists, as many as the turn's "steps" pill counts. */
export function shownSteps(turn: Turn) {
  return cardSteps(turn.steps, turn.state !== "answering");
}

/** One structure of the chat, with the turn that looked it up. */
export type ChatStructure = { turn: number; target: StructureTarget };

/** Every structure the chat's answers looked up, in the order they were asked. */
export function structuresInChat(turns: Turn[]): ChatStructure[] {
  return turns.flatMap((turn, index) =>
    structuresOf(turn.steps).map((target) => ({ turn: index, target })),
  );
}

/** A card on the Sources tab: one source and every number the answer can cite it with. */
export type SourceCard = { source: Source; refs: number[] };

/**
 * The answer's sources as the Sources tab lists them, in the order of their numbers: each label
 * passage on its own, each page once however many numbers point at it.
 */
export function sourceCards(sources: Source[]): SourceCard[] {
  const pages = new Map<string, SourceCard>();
  const cards: SourceCard[] = [];
  for (const source of sources) {
    const refs = source.ref === null ? [] : [source.ref];
    const page = isLabel(source) ? undefined : pages.get(source.url);
    if (page) {
      page.refs.push(...refs);
      continue;
    }
    const card = { source, refs };
    if (!isLabel(source)) pages.set(source.url, card);
    cards.push(card);
  }
  for (const card of cards) card.refs.sort((a, b) => a - b);
  return cards.sort((a, b) => (a.refs[0] ?? Infinity) - (b.refs[0] ?? Infinity));
}
