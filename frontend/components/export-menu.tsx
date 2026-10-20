"use client";

import { Download } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Turn } from "@/lib/chat-turn";
import {
  conversationCsv,
  conversationJson,
  downloadFile,
  exportedConversation,
  exportFileName,
} from "@/lib/conversation-export";

type ExportMenuProps = {
  title: string;
  turns: Turn[];
  /** While an answer is still coming in, the conversation isn't ready to take along. */
  disabled: boolean;
};

/** Saves the open conversation as JSON or CSV, or opens the print dialog to print it or keep a PDF. */
export function ExportMenu({ title, turns, disabled }: ExportMenuProps) {
  const download = (extension: "json" | "csv") => {
    const conversation = exportedConversation(title, turns, new Date());
    const name = exportFileName(conversation, extension);
    if (extension === "json")
      downloadFile(name, "application/json", conversationJson(conversation));
    else downloadFile(name, "text/csv;charset=utf-8", conversationCsv(conversation));
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Export chat"
        disabled={disabled}
        className="flex size-9 items-center justify-center rounded-full border border-rule-2 hover:bg-panel focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3 disabled:opacity-50 disabled:hover:bg-transparent"
      >
        <Download className="size-4" />
      </DropdownMenuTrigger>
      <DropdownMenuContent className="print:hidden">
        <DropdownMenuItem onClick={() => download("json")}>
          JSON, with sources and tools
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => download("csv")}>
          CSV, one row per message
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => window.print()}>Print or save as PDF</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
