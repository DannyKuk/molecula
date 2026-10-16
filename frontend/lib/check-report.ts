import type { CheckedClaim } from "./chat";
import type { Turn } from "./chat-turn";

/**
 * One turn as a Markdown report for debugging a source-check verdict (#221): the question, the
 * answer as streamed, every claim with its verdict, the sources the answer can cite, and every
 * tool call with its full result, which is what the check judged the claims against.
 */
export function checkReport(turn: Turn): string {
  return [
    "# Molecula answer report",
    section("Question", turn.question),
    section("Answer", turn.answer),
    section("Source check", checkLines(turn)),
    section("Sources", sourceLines(turn)),
    section("Tool calls", toolLines(turn)),
  ].join("\n\n");
}

function section(title: string, body: string): string {
  return `## ${title}\n\n${body}`;
}

function checkLines(turn: Turn): string {
  const check = turn.sourceCheck;
  if (!check) return "No check.";
  if (!check.checked) return "Not checked: the check failed.";
  if (check.claims.length === 0) return "No claims.";
  return check.claims.map((claim, index) => claimLines(claim, index + 1)).join("\n\n");
}

function claimLines(claim: CheckedClaim, number: number): string {
  const facts = [
    `refs ${refList(claim.refs)}`,
    claim.held_by.length > 0 && `held by ${refList(claim.held_by)}`,
    `decided by ${claim.decided_by}`,
  ].filter(Boolean);
  const lines = [`${number}. **${claim.label}** (${facts.join(", ")})`, quoted(claim.text)];
  if (claim.reason) lines.push(`   Reason: ${claim.reason}`);
  return lines.join("\n");
}

function refList(refs: number[]): string {
  return refs.length > 0 ? refs.map((ref) => `[${ref}]`).join("") : "none";
}

function quoted(text: string): string {
  return text
    .split("\n")
    .map((line) => `   > ${line}`)
    .join("\n");
}

function sourceLines(turn: Turn): string {
  if (!turn.sources || turn.sources.length === 0) return "None.";
  return turn.sources
    .map((source) => {
      const label = [source.name, source.section].filter(Boolean).join(" · ");
      return `- [${source.ref ?? "-"}] ${label} (${source.kind}): ${source.url}`;
    })
    .join("\n");
}

function toolLines(turn: Turn): string {
  const runs = turn.steps.flatMap((step) => (step.tool ? [step.tool] : []));
  if (runs.length === 0) return "None.";
  return runs
    .map((run) =>
      [
        `### ${run.name} ${JSON.stringify(run.args)}`,
        "```json",
        JSON.stringify(run.result ?? null, null, 2),
        "```",
      ].join("\n"),
    )
    .join("\n\n");
}
