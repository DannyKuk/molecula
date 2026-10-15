import type { CheckedClaim, SourceCheck } from "./chat";
import type { Turn } from "./chat-turn";

/** Where an unbacked claim stands in the answer's Markdown; `claim` is its index in the check. */
export type UnbackedRange = { start: number; end: number; claim: number };

/** A list item or table row, as `ITEM` and `ROW` in `backend/src/molecula/guard/claims.py`. */
const ITEM = /^\s*(?:[-*+•]|\d+[.)])\s+/;
const ROW = /^\s*\|/;

/**
 * Where the claims the sources don't back stand in the answer, in order. The splitter joins a
 * claim's lines with single spaces and puts a list's heading in front of each of its items, so
 * each line is looked for on its own with any whitespace, the heading left out. Claims are
 * found in the answer's order, so a sentence written twice is found where it was checked; a
 * claim that can't be found is left unmarked.
 */
export function unbackedRanges(answer: string, claims: CheckedClaim[]): UnbackedRange[] {
  const ranges: UnbackedRange[] = [];
  let from = 0;
  claims.forEach((claim, index) => {
    for (const line of claimLines(claim.text)) {
      const found = find(answer, line, from);
      if (!found) continue;
      from = found.end;
      if (claim.label === "unsupported") ranges.push({ ...found, claim: index });
    }
  });
  return ranges;
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

export function checkSummary(check: SourceCheck): CheckSummary | null {
  if (!check.checked) return { kind: "unchecked", title: "Not checked against the sources" };
  const facts = check.claims.filter((claim) => claim.label !== "not_a_claim");
  const unbacked = facts.filter((claim) => claim.label === "unsupported").length;
  if (facts.length === 0) return null;
  const title = "Checked against the sources";
  if (unbacked === 0) {
    return { kind: "backed", title, detail: "Every fact is backed by the source it cites." };
  }
  const sentences = unbacked === 1 ? "1 sentence isn't" : `${unbacked} sentences aren't`;
  return {
    kind: "unbacked",
    title,
    detail: `${facts.length - unbacked} of ${facts.length} facts backed · ${sentences} backed by the sources (underlined).`,
  };
}

/** Why the sources don't back a claim: the check's own reason, or why it has none. */
export function unbackedReason(claim: CheckedClaim): string {
  if (claim.decided_by === "unknown_refs") return "It cites a source Molecula didn't look up.";
  if (claim.decided_by === "no_verdict") return "The check gave no verdict on it.";
  return claim.reason;
}
