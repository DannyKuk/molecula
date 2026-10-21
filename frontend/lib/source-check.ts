import type { CheckedClaim, SourceCheck } from "./chat";
import type { Turn } from "./chat-turn";
import { en, type Messages } from "./messages/en";

/** Where a claim the sources don't back stands in the answer's Markdown; `claim` is its index
 * in the check. */
export type UnbackedRange = { start: number; end: number; claim: number };

/** A chip to add at offset `at` of the answer, for results the claim before it doesn't cite but
 * that hold it. */
export type FoundCitation = { at: number; refs: number[] };

/** What the source check adds to the answer's text. */
export type SourceCheckMarks = { unbacked: UnbackedRange[]; found: FoundCitation[] };

/** A list item or table row, as `ITEM` and `ROW` in `backend/src/molecula/guard/claims.py`. */
const ITEM = /^\s*(?:[-*+•]|\d+[.)])\s+/;
const ROW = /^\s*\|/;
/** The punctuation that ends a claim, so a found chip goes before it like a written one. */
const CLOSING = /[.!?;:]+["”’)]*\s*$/;

/**
 * Where the claims the sources don't back stand in the answer, and where a chip goes for each
 * claim another returned result holds (#220). The splitter joins a claim's lines with single
 * spaces and puts a list's heading in front of each of its items, so each line is looked for on
 * its own with any whitespace, the heading left out. Claims are found in the answer's order, so
 * a sentence written twice is found where it was checked; a claim that can't be found is left
 * unmarked.
 */
export function sourceCheckMarks(answer: string, claims: CheckedClaim[]): SourceCheckMarks {
  const marks: SourceCheckMarks = { unbacked: [], found: [] };
  let from = 0;
  claims.forEach((claim, index) => {
    let last: { start: number; end: number } | null = null;
    for (const line of claimLines(claim.text)) {
      const found = find(answer, line, from);
      if (!found) continue;
      from = found.end;
      last = found;
      if (claim.label === "unsupported") marks.unbacked.push({ ...found, claim: index });
    }
    if (last && claim.label === "held_elsewhere" && claim.held_by.length > 0) {
      const closing = answer.slice(last.start, last.end).match(CLOSING)?.[0].length ?? 0;
      marks.found.push({ at: last.end - closing, refs: claim.held_by });
    }
  });
  return marks;
}

function claimLines(text: string): string[] {
  const lines = text.split("\n");
  const items = lines.length > 1 && !isItem(lines[0]) ? lines.slice(1) : lines;
  return items.map((line) => line.replace(ITEM, "").trim()).filter(Boolean);
}

function isItem(line: string): boolean {
  return ITEM.test(line) || ROW.test(line);
}

function find(answer: string, line: string, from: number): { start: number; end: number } | null {
  const pattern = line
    .split(/\s+/)
    .map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("\\s+");
  const match = new RegExp(pattern, "g");
  match.lastIndex = from;
  const found = match.exec(answer);
  return found && { start: found.index, end: found.index + found[0].length };
}

/** The status the guard sends while it checks the answer (`CHECKING_ANSWER` in
 * `backend/src/molecula/guard/chat.py`). */
export const CHECKING_ANSWER = "Checking the answer against the sources";

/** Whether the answer has streamed and the source check is running on it. */
export function checkingAnswer(turn: Turn): boolean {
  return (
    turn.state === "answering" &&
    turn.sourceCheck === null &&
    turn.steps.at(-1)?.text === CHECKING_ANSWER
  );
}

/** What the badge under a checked answer says, or null when there is nothing to say. */
export type CheckSummary = {
  kind: "backed" | "unbacked" | "unchecked";
  title: string;
  detail?: string;
};

export function checkSummary(check: SourceCheck, t: Messages = en): CheckSummary | null {
  if (!check.checked) return { kind: "unchecked", title: t.check.unchecked };
  const facts = check.claims.filter((claim) => claim.label !== "not_a_claim");
  const unbacked = facts.filter((claim) => claim.label === "unsupported").length;
  const elsewhere = facts.filter((claim) => claim.label === "held_elsewhere").length;
  if (facts.length === 0) return null;
  const title = t.check.checked;
  if (unbacked === 0 && elsewhere === 0) {
    return { kind: "backed", title, detail: t.check.allBacked };
  }
  if (unbacked === 0) {
    return { kind: "backed", title, detail: t.check.allInSources };
  }
  return {
    kind: "unbacked",
    title,
    detail: t.check.someUnbacked(facts.length - unbacked, facts.length, unbacked),
  };
}

/** Why the sources don't back a claim: the check's own reason, or why it has none. The check's
 * reason comes from its model and stays as it wrote it. */
export function unbackedReason(claim: CheckedClaim, t: Messages = en): string {
  if (claim.decided_by === "unknown_refs") return t.check.unknownRefs;
  if (claim.decided_by === "no_verdict") return t.check.noVerdict;
  return claim.reason;
}
