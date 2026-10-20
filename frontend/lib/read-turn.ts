import { nearEnd } from "./use-follow-answer";

/** How far down the window a turn's top must be above to count as the one being read. */
const READING_LINE = 0.4;

/**
 * The turn the reader is on: the last one whose top is above 40% of the window's height. At the end
 * of the page it is the last turn, since a short last answer never reaches the line.
 */
export function readTurn(turns: HTMLCollection): number {
  if (nearEnd()) return turns.length - 1;
  const line = window.innerHeight * READING_LINE;
  const read = Array.from(turns).findLastIndex((turn) => turn.getBoundingClientRect().top < line);
  return Math.max(read, 0);
}
