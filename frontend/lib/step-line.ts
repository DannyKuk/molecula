import { en, type Messages } from "./messages/en";
import type { Step, ToolRun } from "./tool-cards";

type Progress = Messages["progress"];

/**
 * A step's progress line in the interface language. The backend sends its lines in English: a
 * step that ran a tool is written again from the tool's name and arguments, as the status
 * functions passed to `build_tool` in `backend/src/molecula/tools/*.py` write it, and the guard's
 * two lines (`CHECKING` and `CHECKING_ANSWER` in `guard/chat.py`) are looked up. Any other line,
 * or arguments the line can't be written from, show as the backend sent them.
 */
export function stepLine(step: Step, t: Messages = en): string {
  const line = step.tool ? toolLine(step.tool, t.progress) : guardLine(step.text, t.progress);
  return line ?? step.text;
}

function toolLine({ name, args }: ToolRun, progress: Progress): string | null {
  switch (name) {
    case "resolve_drug":
      return withName(args.name, progress.resolving);
    case "get_properties":
      return withName(args.drug, progress.properties);
    case "get_targets":
      return withName(args.drug, progress.targets);
    case "get_complex":
      return withName(args.drug, progress.complex);
    case "compare_drugs":
      return isNames(args.drugs) ? progress.comparing(args.drugs) : null;
    case "search_labels":
      // The backend writes the general line for any empty `drug`, as Python's `if args.get("drug")`.
      if (!args.drug) return progress.searchingLabels;
      return withName(args.drug, progress.searchingLabel);
    default:
      return null;
  }
}

function withName(value: unknown, line: (name: string) => string): string | null {
  return typeof value === "string" && value !== "" ? line(value) : null;
}

function isNames(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((name) => typeof name === "string");
}

function guardLine(text: string, progress: Progress): string | null {
  if (text === en.progress.checking) return progress.checking;
  if (text === en.progress.checkingAnswer) return progress.checkingAnswer;
  return null;
}
