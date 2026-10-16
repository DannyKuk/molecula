"use client";

import { cn } from "cn";
import { Ellipsis, Pencil, Trash2 } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ConversationSummary } from "@/lib/chat-history";

type HistoryRowProps = {
  conversation: ConversationSummary;
  active: boolean;
  onOpen: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
};

/** One saved conversation in the list: it opens on click, and its ⋯ menu renames or deletes it. */
export function HistoryRow({ conversation, active, onOpen, onRename, onDelete }: HistoryRowProps) {
  const [mode, setMode] = useState<"idle" | "renaming" | "deleting">("idle");
  const { id, title } = conversation;

  if (mode === "renaming") {
    const finish = (newTitle: string | null) => {
      setMode("idle");
      if (newTitle && newTitle !== title) onRename(id, newTitle);
    };
    return (
      <li>
        <RenameField title={title} onDone={finish} />
      </li>
    );
  }
  if (mode === "deleting") {
    return (
      <li>
        <DeleteConfirm
          title={title}
          onDelete={() => onDelete(id)}
          onCancel={() => setMode("idle")}
        />
      </li>
    );
  }
  return (
    <li
      className={cn(
        "group flex items-center rounded-md text-sm hover:bg-zinc-100 dark:hover:bg-zinc-900",
        active && "bg-zinc-200 hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-800",
      )}
    >
      <button
        type="button"
        title={title}
        aria-current={active ? "page" : undefined}
        onClick={() => onOpen(id)}
        className="min-w-0 flex-1 truncate rounded-md px-2 py-1.75 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
      >
        {title}
      </button>
      <RowMenu
        title={title}
        alwaysShown={active}
        onRename={() => setMode("renaming")}
        onDelete={() => setMode("deleting")}
      />
    </li>
  );
}

type RowMenuProps = {
  title: string;
  alwaysShown: boolean;
  onRename: () => void;
  onDelete: () => void;
};

/** With a mouse the ⋯ button shows on hover and focus; on touch it always shows. */
function RowMenu({ title, alwaysShown, onRename, onDelete }: RowMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Options: ${title}`}
            className={cn(
              "mr-1 text-zinc-600 dark:text-zinc-400",
              !alwaysShown &&
                "pointer-fine:opacity-0 pointer-fine:group-focus-within:opacity-100 pointer-fine:group-hover:opacity-100 pointer-fine:aria-expanded:opacity-100",
            )}
          />
        }
      >
        <Ellipsis />
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuItem onClick={onRename}>
          <Pencil />
          Rename
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onClick={onDelete}>
          <Trash2 />
          Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Enter or leaving the field saves the title, Esc keeps the old one. */
function RenameField({ title, onDone }: { title: string; onDone: (title: string | null) => void }) {
  const [draft, setDraft] = useState(title);
  const finished = useRef(false);
  const finish = (save: boolean) => {
    if (finished.current) return;
    finished.current = true;
    onDone(save ? draft.trim() || null : null);
  };

  return (
    <div className="flex flex-col gap-0.5 rounded-md bg-zinc-200 p-0.5 dark:bg-zinc-800">
      <input
        aria-label="Chat title"
        value={draft}
        autoFocus
        onFocus={(event) => event.target.select()}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={() => finish(true)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            finish(true);
          } else if (event.key === "Escape") {
            finish(false);
          }
        }}
        className="w-full rounded-md border border-zinc-600 bg-background px-2 py-1.25 text-sm outline-2 outline-ring/50 dark:border-zinc-400"
      />
      <span className="px-1 pb-0.5 text-[11px] text-zinc-500">Enter saves · Esc cancels</span>
    </div>
  );
}

type DeleteConfirmProps = { title: string; onDelete: () => void; onCancel: () => void };

function DeleteConfirm({ title, onDelete, onCancel }: DeleteConfirmProps) {
  return (
    <div
      role="group"
      aria-label="Delete chat"
      className="flex flex-col gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-2"
    >
      <p className="text-[13px] leading-4.5">
        Delete this chat? It can&apos;t be undone.
        <span className="block truncate text-zinc-600 dark:text-zinc-400">{title}</span>
      </p>
      <div className="flex gap-1.5">
        <Button variant="destructive" size="sm" onClick={onDelete}>
          Delete
        </Button>
        <Button variant="ghost" size="sm" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
