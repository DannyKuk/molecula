"use client";

import { cn } from "cn";
import {
  ChartColumn,
  History,
  LoaderCircle,
  Menu,
  PanelLeft,
  Plus,
  SquarePen,
  X,
} from "lucide-react";
import Link from "next/link";
import { type ComponentProps, useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Dialog, DialogClose, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SheetContent } from "@/components/ui/sheet";
import { bookmarkedOf, type ConversationSummary, groupChats } from "@/lib/chat-history";
import { useSidebarExpanded } from "@/lib/use-sidebar-expanded";

import { HistoryRow } from "./history-row";

export type ChatListProps = {
  /** Null until the history has loaded, false when the browser doesn't keep it. */
  available: boolean | null;
  conversations: ConversationSummary[];
  /** The bookmarked conversations' ids, in the order they were bookmarked. */
  bookmarks: string[];
  activeId: string | null;
  /** The chat whose answer is coming in, and the chats whose questions wait for it, in order. */
  answeringId: string | null;
  queuedIds: string[];
  /** The bookmark removed last, which Undo puts back, for a few seconds after its removal. */
  removedBookmark: { title: string; onUndo: () => void } | null;
  onOpen: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  onBookmark: (id: string) => void;
  onUnbookmark: (id: string) => void;
};

const RAIL_BOOKMARKS = 5;
const OUTLINED = "border-zinc-500 text-foreground dark:border-zinc-400";

const ICON =
  "text-zinc-600 hover:text-foreground dark:text-zinc-400 [&_svg:not([class*='size-'])]:size-4.5";

const SIDEBAR_CLASSES =
  "sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-zinc-200 bg-zinc-50 md:flex dark:border-zinc-800 dark:bg-[oklch(0.17_0.004_286)] print:hidden";

/** The chats on a wide screen: a rail of icons, or once expanded, the whole list. */
export function ChatSidebar(props: ChatListProps) {
  const [expanded, setExpanded] = useSidebarExpanded();

  if (!expanded) {
    // The rail marks the answering chat's number, or Chat history when that chat has none.
    const numbered = bookmarkedOf(props.conversations, props.bookmarks).slice(0, RAIL_BOOKMARKS);
    const answeringElsewhere =
      props.answeringId !== null && !numbered.some(({ id }) => id === props.answeringId);
    return (
      <nav aria-label="Chats" className={`${SIDEBAR_CLASSES} w-14 items-center gap-1 py-3`}>
        <IconButton label="Show chats" onClick={() => setExpanded(true)}>
          <PanelLeft />
        </IconButton>
        <IconButton label="New chat" onClick={props.onNew}>
          <SquarePen />
        </IconButton>
        <IconButton
          label={answeringElsewhere ? "Chat history, an answer is coming in" : "Chat history"}
          onClick={() => setExpanded(true)}
          className="relative"
        >
          <History />
          {answeringElsewhere && <AnsweringBadge />}
        </IconButton>
        <Link
          href="/benchmarks"
          aria-label="Benchmarks"
          title="Benchmarks"
          className={cn(buttonVariants({ variant: "ghost", size: "icon-lg" }), ICON)}
        >
          <ChartColumn />
        </Link>
        <RailBookmarks {...props} />
      </nav>
    );
  }
  return (
    <aside aria-label="Chat history" className={`${SIDEBAR_CLASSES} w-65`}>
      <div className="flex min-h-9 items-center gap-1 px-3 pt-3">
        <IconButton label="Hide chats" onClick={() => setExpanded(false)}>
          <PanelLeft />
        </IconButton>
        <span className="pl-1 text-[15px] font-semibold">Chats</span>
      </div>
      <ChatList {...props} />
    </aside>
  );
}

/**
 * The first bookmarks as numbered buttons, and the rest behind "+N", which lists them all. The open
 * chat's number is outlined, or "+N" when the open chat is past the numbers.
 */
function RailBookmarks({ conversations, bookmarks, activeId, answeringId, onOpen }: ChatListProps) {
  const bookmarked = bookmarkedOf(conversations, bookmarks);
  if (bookmarked.length === 0) return null;
  const numbered = bookmarked.slice(0, RAIL_BOOKMARKS);
  const more = bookmarked.length - numbered.length;
  const activeIsMore = bookmarked.findIndex(({ id }) => id === activeId) >= RAIL_BOOKMARKS;

  return (
    <div
      role="group"
      aria-label="Bookmarks"
      className="mt-2 flex flex-col items-center gap-1 border-t border-zinc-200 pt-3 dark:border-zinc-800"
    >
      {numbered.map(({ id, title }, index) => (
        <IconButton
          key={id}
          label={id === answeringId ? `${title}, answering` : title}
          aria-current={id === activeId ? "page" : undefined}
          onClick={() => onOpen(id)}
          className={cn("relative text-[13px] tabular-nums", id === activeId && OUTLINED)}
        >
          {index + 1}
          {id === answeringId && <AnsweringBadge />}
        </IconButton>
      ))}
      {more > 0 && (
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <IconButton
                label={`All ${bookmarked.length} bookmarks`}
                className={cn("text-[13px] tabular-nums", activeIsMore && OUTLINED)}
              />
            }
          >
            +{more}
          </DropdownMenuTrigger>
          <DropdownMenuContent side="right" align="start" className="max-w-72">
            {bookmarked.map(({ id, title }, index) => (
              <DropdownMenuItem
                key={id}
                onClick={() => onOpen(id)}
                className={cn(id === activeId && "font-medium")}
              >
                <span aria-hidden className="w-4 shrink-0 text-xs text-zinc-500 tabular-nums">
                  {index + 1}
                </span>
                <span className="truncate">{title}</span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
}

/** The chats on a phone: a drawer opened from ☰ in the header, closed by picking a chat. */
export function ChatDrawer(props: ChatListProps) {
  const [open, setOpen] = useState(false);
  const thenClose =
    <T extends unknown[]>(action: (...args: T) => void) =>
    (...args: T) => {
      setOpen(false);
      action(...args);
    };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={<IconButton label="Open chats" className="-ml-2 md:hidden print:hidden" />}
      >
        <Menu />
      </DialogTrigger>
      <SheetContent className="bg-zinc-50 dark:bg-[oklch(0.17_0.004_286)]">
        <div className="flex min-h-9 items-center justify-between px-3 pt-3">
          <DialogTitle className="pl-1 text-[15px] font-semibold">Chats</DialogTitle>
          <DialogClose render={<IconButton label="Close chats" />}>
            <X />
          </DialogClose>
        </div>
        <ChatList {...props} onOpen={thenClose(props.onOpen)} onNew={thenClose(props.onNew)} />
      </SheetContent>
    </Dialog>
  );
}

/**
 * "New chat", the benchmarks link, the bookmarked chats, the others by day, newest first, and what
 * to know about where they are kept.
 */
function ChatList({ onNew, removedBookmark, ...props }: ChatListProps) {
  return (
    <>
      <div className="px-3 pt-2 pb-2">
        <Button variant="outline" className="h-9 w-full justify-start gap-2 px-2.5" onClick={onNew}>
          <Plus />
          New chat
        </Button>
        <Link
          href="/benchmarks"
          className="mt-1 flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm text-zinc-600 hover:bg-zinc-200/60 hover:text-foreground dark:text-zinc-400 dark:hover:bg-zinc-800 [&_svg]:size-4"
        >
          <ChartColumn />
          Benchmarks
        </Link>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        <ChatGroups {...props} />
      </div>
      {removedBookmark && <UndoBar {...removedBookmark} />}
      {props.available !== false && (
        <p className="border-t border-zinc-200 px-4 py-3 text-xs text-zinc-500 dark:border-zinc-800">
          Saved in this browser only.
        </p>
      )}
    </>
  );
}

function ChatGroups({
  available,
  conversations,
  bookmarks,
  activeId,
  answeringId,
  queuedIds,
  ...actions
}: Omit<ChatListProps, "onNew" | "removedBookmark">) {
  if (available === false) return <HistoryOff />;
  if (available === null) return null;
  if (conversations.length === 0) {
    return (
      <div className="flex flex-col gap-2 px-3 py-4 text-sm text-zinc-600 dark:text-zinc-400">
        <span className="font-medium text-foreground">No chats yet</span>
        Your questions show up here, titled by the first question. They&apos;re saved in this
        browser only, not on a server.
      </div>
    );
  }
  return groupChats(conversations, bookmarks, new Date()).map((group) => (
    <section key={group.label} aria-label={group.label}>
      <h2 className="px-2 pt-3 pb-1 text-xs font-medium text-zinc-500">{group.label}</h2>
      <ul className="flex flex-col">
        {group.conversations.map((conversation) => (
          <HistoryRow
            key={conversation.id}
            conversation={conversation}
            active={conversation.id === activeId}
            bookmarked={group.label === "Bookmarked"}
            progress={progressOf(conversation.id, answeringId, queuedIds)}
            {...actions}
          />
        ))}
      </ul>
    </section>
  ));
}

function progressOf(id: string, answeringId: string | null, queuedIds: string[]) {
  if (id === answeringId) return "answering";
  return queuedIds.includes(id) ? "queued" : null;
}

function AnsweringBadge() {
  return (
    <LoaderCircle
      aria-hidden
      className="absolute top-0.5 right-0.5 size-3 animate-spin text-zinc-500 motion-reduce:animate-none"
    />
  );
}

function UndoBar({ title, onUndo }: { title: string; onUndo: () => void }) {
  return (
    <div
      role="status"
      className="mx-2 mb-2 flex items-center gap-1 rounded-md bg-zinc-900 py-1.5 pr-1.5 pl-3 text-[13px] text-zinc-50 dark:bg-zinc-100 dark:text-zinc-900"
    >
      <p className="min-w-0 flex-1 truncate">
        Removed &apos;
        <span className="inline-block max-w-28 truncate align-bottom">{title}</span>
        &apos; from bookmarks
      </p>
      <span aria-hidden>·</span>
      <Button
        variant="ghost"
        size="sm"
        onClick={onUndo}
        className="font-semibold text-inherit hover:bg-white/15 hover:text-inherit dark:hover:bg-black/10"
      >
        Undo
      </Button>
    </div>
  );
}

function HistoryOff() {
  return (
    <div className="mx-1 my-2 flex flex-col gap-1 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2.5 text-[13px] leading-4.5 text-sky-900 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-200">
      <b className="font-semibold">History is off in this browser</b>
      It doesn&apos;t let Molecula save chats (a private window, or storage is full). The chat still
      works; this conversation is gone when you close the tab.
    </div>
  );
}

function IconButton({
  label,
  className,
  ...props
}: ComponentProps<typeof Button> & { label: string }) {
  return (
    <Button
      variant="ghost"
      size="icon-lg"
      aria-label={label}
      title={label}
      className={cn(ICON, className)}
      {...props}
    />
  );
}
