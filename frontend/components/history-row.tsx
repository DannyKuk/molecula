"use client";

import { cn } from "cn";
import { Bookmark, BookmarkX, Clock, Ellipsis, LoaderCircle, Pencil, Trash2 } from "lucide-react";
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
import { useMessages } from "@/lib/messages";

type HistoryRowProps = {
  conversation: ConversationSummary;
  active: boolean;
  bookmarked: boolean;
  /** Whether the chat's answer is coming in, or its question waits for another chat's answer. */
  progress: "answering" | "queued" | null;
  onOpen: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  onBookmark: (id: string) => void;
  onUnbookmark: (id: string) => void;
};

/**
 * One saved conversation in the list: it opens on click, the bookmark button beside it bookmarks
 * it, and its ⋯ menu renames, bookmarks or deletes it.
 */
export function HistoryRow({
  conversation,
  active,
  bookmarked,
  progress,
  onOpen,
  onRename,
  onDelete,
  onBookmark,
  onUnbookmark,
}: HistoryRowProps) {
  const [mode, setMode] = useState<"idle" | "renaming" | "deleting">("idle");
  const { id, title } = conversation;
  const toggleBookmark = () => (bookmarked ? onUnbookmark(id) : onBookmark(id));

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
        "group flex items-center rounded-lg border border-transparent text-sm hover:bg-rule",
        active && "border-rule-2 bg-card hover:bg-card",
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
      {progress && <ProgressMark progress={progress} />}
      <BookmarkButton title={title} bookmarked={bookmarked} onToggle={toggleBookmark} />
      <RowMenu
        title={title}
        alwaysShown={active}
        bookmarked={bookmarked}
        onRename={() => setMode("renaming")}
        onToggleBookmark={toggleBookmark}
        onDelete={() => setMode("deleting")}
      />
    </li>
  );
}

/** A spinner while the chat's answer comes in, a clock while its question waits in line. */
function ProgressMark({ progress }: { progress: "answering" | "queued" }) {
  const t = useMessages();
  const label = progress === "answering" ? t.historyRow.answering : t.historyRow.waiting;
  return (
    <span role="img" aria-label={label} title={label} className="px-1 text-ink-3">
      {progress === "answering" ? (
        <LoaderCircle aria-hidden className="size-3.5 animate-spin motion-reduce:animate-none" />
      ) : (
        <Clock aria-hidden className="size-3.5" />
      )}
    </span>
  );
}

const SHOWN_ON_HOVER =
  "pointer-fine:opacity-0 pointer-fine:group-focus-within:opacity-100 pointer-fine:group-hover:opacity-100";

type BookmarkButtonProps = { title: string; bookmarked: boolean; onToggle: () => void };

/** With a mouse it shows on hover and focus; on touch it is left out and the ⋯ menu bookmarks. */
function BookmarkButton({ title, bookmarked, onToggle }: BookmarkButtonProps) {
  const t = useMessages();
  const label = bookmarked ? t.historyRow.removeBookmark(title) : t.historyRow.bookmark(title);
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label={label}
      title={label}
      onClick={onToggle}
      className={cn("hidden text-ink-2 pointer-fine:inline-flex", SHOWN_ON_HOVER)}
    >
      <Bookmark className={cn(bookmarked && "fill-current")} />
    </Button>
  );
}

type RowMenuProps = {
  title: string;
  alwaysShown: boolean;
  bookmarked: boolean;
  onRename: () => void;
  onToggleBookmark: () => void;
  onDelete: () => void;
};

/** With a mouse the ⋯ button shows on hover and focus; on touch it always shows. */
function RowMenu({
  title,
  alwaysShown,
  bookmarked,
  onRename,
  onToggleBookmark,
  onDelete,
}: RowMenuProps) {
  const t = useMessages();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={t.historyRow.options(title)}
            className={cn(
              "mr-1 text-ink-2",
              !alwaysShown && [SHOWN_ON_HOVER, "pointer-fine:aria-expanded:opacity-100"],
            )}
          />
        }
      >
        <Ellipsis />
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuItem onClick={onRename}>
          <Pencil />
          {t.historyRow.rename}
        </DropdownMenuItem>
        <DropdownMenuItem onClick={onToggleBookmark}>
          {bookmarked ? <BookmarkX /> : <Bookmark />}
          {bookmarked ? t.historyRow.removeBookmarkItem : t.historyRow.bookmarkItem}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onClick={onDelete}>
          <Trash2 />
          {t.historyRow.delete}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Enter or leaving the field saves the title, Esc keeps the old one. */
function RenameField({ title, onDone }: { title: string; onDone: (title: string | null) => void }) {
  const t = useMessages();
  const [draft, setDraft] = useState(title);
  const finished = useRef(false);
  const finish = (save: boolean) => {
    if (finished.current) return;
    finished.current = true;
    onDone(save ? draft.trim() || null : null);
  };

  return (
    <div className="flex flex-col gap-0.5 rounded-md bg-rule p-0.5">
      <input
        aria-label={t.historyRow.title}
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
        className="w-full rounded-md border border-ink-3 bg-background px-2 py-1.25 text-sm outline-2 outline-ring/50"
      />
      <span className="px-1 pb-0.5 text-[11px] text-ink-3">{t.historyRow.renameHint}</span>
    </div>
  );
}

type DeleteConfirmProps = { title: string; onDelete: () => void; onCancel: () => void };

function DeleteConfirm({ title, onDelete, onCancel }: DeleteConfirmProps) {
  const t = useMessages();
  return (
    <div
      role="group"
      aria-label={t.historyRow.deleteChat}
      className="flex flex-col gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-2"
    >
      <p className="text-[13px] leading-4.5">
        {t.historyRow.deleteConfirm}
        <span className="block truncate text-ink-2">{title}</span>
      </p>
      <div className="flex gap-1.5">
        <Button variant="destructive" size="sm" onClick={onDelete}>
          {t.historyRow.delete}
        </Button>
        <Button variant="ghost" size="sm" onClick={onCancel}>
          {t.historyRow.cancel}
        </Button>
      </div>
    </div>
  );
}
