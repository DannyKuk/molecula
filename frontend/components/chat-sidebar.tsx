"use client";

import { cn } from "cn";
import { History, Menu, PanelLeft, Plus, SquarePen, X } from "lucide-react";
import { type ComponentProps, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { SheetContent } from "@/components/ui/sheet";
import { type ConversationSummary, groupByDay } from "@/lib/chat-history";
import { useSidebarExpanded } from "@/lib/use-sidebar-expanded";

import { HistoryRow } from "./history-row";

export type ChatListProps = {
  /** Null until the history has loaded, false when the browser doesn't keep it. */
  available: boolean | null;
  conversations: ConversationSummary[];
  activeId: string | null;
  onOpen: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
};

const SIDEBAR_CLASSES =
  "sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-zinc-200 bg-zinc-50 md:flex dark:border-zinc-800 dark:bg-[oklch(0.17_0.004_286)]";

/** The chats on a wide screen: a rail of icons, or once expanded, the whole list. */
export function ChatSidebar(props: ChatListProps) {
  const [expanded, setExpanded] = useSidebarExpanded();

  if (!expanded) {
    return (
      <nav aria-label="Chats" className={`${SIDEBAR_CLASSES} w-14 items-center gap-1 py-3`}>
        <IconButton label="Show chats" onClick={() => setExpanded(true)}>
          <PanelLeft />
        </IconButton>
        <IconButton label="New chat" onClick={props.onNew}>
          <SquarePen />
        </IconButton>
        <IconButton label="Chat history" onClick={() => setExpanded(true)}>
          <History />
        </IconButton>
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
      <DialogTrigger render={<IconButton label="Open chats" className="-ml-2 md:hidden" />}>
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

/** "New chat", the saved chats by day, newest first, and what to know about where they are kept. */
function ChatList({ onNew, ...props }: ChatListProps) {
  return (
    <>
      <div className="px-3 pt-2 pb-2">
        <Button variant="outline" className="h-9 w-full justify-start gap-2 px-2.5" onClick={onNew}>
          <Plus />
          New chat
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        <ChatGroups {...props} />
      </div>
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
  activeId,
  onOpen,
  onRename,
  onDelete,
}: Omit<ChatListProps, "onNew">) {
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
  return groupByDay(conversations, new Date()).map((group) => (
    <section key={group.label} aria-label={group.label}>
      <h2 className="px-2 pt-3 pb-1 text-xs font-medium text-zinc-500">{group.label}</h2>
      <ul className="flex flex-col">
        {group.conversations.map((conversation) => (
          <HistoryRow
            key={conversation.id}
            conversation={conversation}
            active={conversation.id === activeId}
            onOpen={onOpen}
            onRename={onRename}
            onDelete={onDelete}
          />
        ))}
      </ul>
    </section>
  ));
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
      className={cn(
        "text-zinc-600 hover:text-foreground dark:text-zinc-400 [&_svg:not([class*='size-'])]:size-4.5",
        className,
      )}
      {...props}
    />
  );
}
