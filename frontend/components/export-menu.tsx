"use client";

import { Download } from "lucide-react";
import { useState } from "react";

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
  /** Puts the pictures of the 3D structures on the page; the print dialog opens once it resolves. */
  onPreparePrint: () => Promise<void>;
};

/** Saves the open conversation as JSON or CSV, or opens the print dialog to print it or keep a PDF. */
export function ExportMenu({ title, turns, disabled, onPreparePrint }: ExportMenuProps) {
  const [open, setOpen] = useState(false);
  const [preparing, setPreparing] = useState(false);

  const download = (extension: "json" | "csv") => {
    const conversation = exportedConversation(title, turns, new Date());
    const name = exportFileName(conversation, extension);
    if (extension === "json")
      downloadFile(name, "application/json", conversationJson(conversation));
    else downloadFile(name, "text/csv;charset=utf-8", conversationCsv(conversation));
  };

  const print = async () => {
    setPreparing(true);
    try {
      await onPreparePrint();
    } finally {
      setPreparing(false);
    }
    setOpen(false);
    window.print();
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
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
        <DropdownMenuItem
          // Stays open while the pictures are drawn, so it can say so.
          closeOnClick={false}
          disabled={preparing}
          aria-busy={preparing}
          onClick={() => void print()}
        >
          {preparing ? "Preparing the 3D pictures…" : "Print or save as PDF"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
