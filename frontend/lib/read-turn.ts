import { nearEnd } from "./use-follow-answer";

/** How far down the scroll area a turn's top must be above to count as the one being read. */
const READING_LINE = 0.4;

/**
 * The turn the reader is on: the last one whose top is above 40% of the scroll area's height. At the
 * end of the chat it is the last turn, since a short last answer never reaches the line.
 */
export function readTurn(scroller: HTMLElement, turns: HTMLCollection): number {
  if (nearEnd(scroller)) return turns.length - 1;
  const line = scroller.getBoundingClientRect().top + scroller.clientHeight * READING_LINE;
  const read = Array.from(turns).findLastIndex((turn) => turn.getBoundingClientRect().top < line);
  return Math.max(read, 0);
}
