import type { CheckedClaim } from "./chat";
import type { Turn } from "./chat-turn";
import { en, type Messages } from "./messages/en";

type Report = Messages["report"];

/**
 * One turn as a Markdown report for debugging a source-check verdict (#221): the question, the
 * answer as streamed, every claim with its verdict, the sources the answer can cite, and every
 * tool call with its full result, which is what the check judged the claims against. The words
 * are in the reader's language; the verdicts, tool names and results stay as the backend sent
 * them, so a report reads the same to whoever debugs it.
 */
export function checkReport(turn: Turn, t: Messages = en): string {
  const report = t.report;
  return [
    `# ${report.title}`,
    section(report.question, turn.question),
    section(report.answer, turn.answer),
    section(report.sourceCheck, checkLines(turn, report)),
    section(report.sources, sourceLines(turn, report)),
    section(report.toolCalls, toolLines(turn, report)),
  ].join("\n\n");
}

function section(title: string, body: string): string {
  return `## ${title}\n\n${body}`;
}

function checkLines(turn: Turn, report: Report): string {
  const check = turn.sourceCheck;
  if (!check) return report.noCheck;
  if (!check.checked) return report.checkFailed;
  if (check.claims.length === 0) return report.noClaims;
  return check.claims.map((claim, index) => claimLines(claim, index + 1, report)).join("\n\n");
}

function claimLines(claim: CheckedClaim, number: number, report: Report): string {
  const facts = [
    report.refs(refList(claim.refs, report)),
    claim.held_by.length > 0 && report.heldBy(refList(claim.held_by, report)),
    report.decidedBy(claim.decided_by),
  ].filter(Boolean);
  const lines = [`${number}. **${claim.label}** (${facts.join(", ")})`, quoted(claim.text)];
  if (claim.reason) lines.push(`   ${report.reason(claim.reason)}`);
  return lines.join("\n");
}

function refList(refs: number[], report: Report): string {
  return refs.length > 0 ? refs.map((ref) => `[${ref}]`).join("") : report.noRefs;
}

function quoted(text: string): string {
  return text
    .split("\n")
    .map((line) => `   > ${line}`)
    .join("\n");
}

function sourceLines(turn: Turn, report: Report): string {
  if (!turn.sources || turn.sources.length === 0) return report.none;
  return turn.sources
    .map((source) => {
      const label = [source.name, source.section].filter(Boolean).join(" · ");
      return `- [${source.ref ?? "-"}] ${label} (${source.kind}): ${source.url}`;
    })
    .join("\n");
}

function toolLines(turn: Turn, report: Report): string {
  const runs = turn.steps.flatMap((step) => (step.tool ? [step.tool] : []));
  if (runs.length === 0) return report.none;
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
