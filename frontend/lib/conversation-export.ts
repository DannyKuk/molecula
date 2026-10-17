import type { Turn } from "./chat-turn";
import { sourceLines } from "./citations";

/** The open conversation as it leaves the browser: its title and every turn as the chat keeps it. */
export type ExportedConversation = {
  title: string;
  exportedAt: string;
  turns: Turn[];
};

export function exportedConversation(
  title: string,
  turns: Turn[],
  exportedAt: Date,
): ExportedConversation {
  return { title, exportedAt: exportedAt.toISOString(), turns };
}

/** The whole conversation, with the steps, the tool results and the sources of every answer. */
export function conversationJson(conversation: ExportedConversation): string {
  return JSON.stringify(conversation, null, 2);
}

const CSV_HEADER = ["time", "role", "text", "sources"];

/** One row per message: the question, then the answer with its sources, one per line. */
export function conversationCsv({ turns }: ExportedConversation): string {
  const rows = turns.flatMap((turn) => [
    [timeOf(turn.askedAt), "user", turn.question, ""],
    [
      timeOf(turn.answeredAt),
      "assistant",
      turn.answer || turn.error || "",
      sourceLines(turn.sources ?? []).join("\n"),
    ],
  ]);
  // The byte order mark tells Excel the file is UTF-8, so umlauts and dashes come out right.
  return "\uFEFF" + [CSV_HEADER, ...rows].map((row) => row.map(csvField).join(",")).join("\r\n");
}

function timeOf(epochMs: number | undefined): string {
  return epochMs === undefined ? "" : new Date(epochMs).toISOString();
}

function csvField(value: string): string {
  // A spreadsheet runs a cell that starts like a formula; label text the answer quotes is untrusted.
  const safe = /^[=+\-@\t\r]/.test(value) ? `'${value}` : value;
  return /[",\r\n]/.test(safe) ? `"${safe.replaceAll('"', '""')}"` : safe;
}

/** "molecula-2026-10-17-how-does-imatinib-work.csv", from the title and the day it was exported. */
export function exportFileName(
  { title, exportedAt }: ExportedConversation,
  extension: "json" | "csv",
): string {
  const words = title
    .toLowerCase()
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 50)
    .replace(/-$/, "");
  return `molecula-${exportedAt.slice(0, 10)}${words ? `-${words}` : ""}.${extension}`;
}

/** Hands the browser a file to save. */
export function downloadFile(name: string, type: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  // The download reads the URL after the click returns, so it is freed a moment later.
  setTimeout(() => URL.revokeObjectURL(url));
}
