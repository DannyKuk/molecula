"use client";

import { cn } from "cn";
import {
  ChartColumn,
  Gauge,
  History,
  LoaderCircle,
  Menu,
  PanelLeft,
  Plug,
  Plus,
  Settings,
  SquarePen,
  Workflow,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ComponentProps, type ReactNode, useState } from "react";

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
import { useLanguage } from "@/lib/language";
import { useMessages } from "@/lib/messages";
import { useSidebarExpanded } from "@/lib/use-sidebar-expanded";

import { Brand, BrandMark } from "./brand-mark";
import { HistoryRow } from "./history-row";
import { LanguageSwitch } from "./language-switch";
import { UserMenu } from "./login";
import { McpDialog } from "./mcp-dialog";
import { ModelSettings } from "./model-settings";

export type ChatListProps = {
  /** Null until the history has loaded, false when the browser doesn't keep it. */
  available: boolean | null;
  conversations: ConversationSummary[];
  /** The bookmarked conversations' ids, in the order they were bookmarked. */
  bookmarks: string[];
  activeId: string | null;
  /** Whether the chat shows an empty new chat, which makes "New chat" the current page. */
  newChatOpen: boolean;
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
const OUTLINED = "border-ink-3 text-foreground";
const CURRENT = "border-rule-2 bg-card text-foreground hover:bg-card";

const ICON =
  "text-ink-2 hover:bg-rule hover:text-foreground [&_svg:not([class*='size-'])]:size-4.5";

// The rows are as tall as the rail's buttons, with their icons where the rail's are, so nothing
// moves when the sidebar opens or closes.
const LIST_LINK =
  "flex h-9 w-full items-center gap-2.5 rounded-lg border border-transparent px-2 text-sm text-ink-2 hover:bg-rule hover:text-foreground [&_svg]:size-4.5";

const SIDEBAR_CLASSES =
  "sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-rule bg-panel md:flex print:hidden";

/** The chats on a wide screen: a rail of icons, or once expanded, the whole list. */
export function ChatSidebar(props: ChatListProps) {
  const t = useMessages();
  const [expanded, setExpanded] = useSidebarExpanded();

  if (!expanded) {
    // The rail marks the answering chat's number, or Chat history when that chat has none.
    const numbered = bookmarkedOf(props.conversations, props.bookmarks).slice(0, RAIL_BOOKMARKS);
    const answeringElsewhere =
      props.answeringId !== null && !numbered.some(({ id }) => id === props.answeringId);
    return (
      <nav
        aria-label={t.sidebar.chats}
        className={`${SIDEBAR_CLASSES} w-14 items-center gap-1 py-3`}
      >
        <IconButton label={t.sidebar.show} onClick={() => setExpanded(true)} className="group">
          <BrandMark className="size-6 group-hover:hidden group-focus-visible:hidden" />
          <PanelLeft className="hidden group-hover:block group-focus-visible:block" />
        </IconButton>
        <IconButton
          label={t.sidebar.newChat}
          aria-current={props.newChatOpen ? "page" : undefined}
          onClick={props.onNew}
          className={cn(props.newChatOpen && OUTLINED)}
        >
          <SquarePen />
        </IconButton>
        {PAGES.map(({ href, label, icon }) => (
          <RailLink key={href} href={href} label={t.sidebar[label]}>
            {icon}
          </RailLink>
        ))}
        <IconButton
          label={answeringElsewhere ? t.sidebar.historyAnswering : t.sidebar.history}
          onClick={() => setExpanded(true)}
          className="relative"
        >
          <History />
          {answeringElsewhere && <AnsweringBadge />}
        </IconButton>
        <RailBookmarks {...props} />
        <McpDialog trigger={<IconButton label={t.sidebar.mcpServer} className="mt-auto" />}>
          <Plug />
        </McpDialog>
        <RailLanguage />
        <ModelSettings trigger={<IconButton label={t.sidebar.settings} />}>
          <Settings />
        </ModelSettings>
        <UserMenu />
      </nav>
    );
  }
  return (
    <aside aria-label={t.sidebar.history} className={`${SIDEBAR_CLASSES} w-65`}>
      <div className="mt-3 flex h-9 shrink-0 items-center justify-between px-2.5">
        <Brand className="pl-1.5 text-[17px]" markClassName="size-6" />
        <IconButton label={t.sidebar.hide} onClick={() => setExpanded(false)}>
          <PanelLeft />
        </IconButton>
      </div>
      <ChatList {...props} withMcp />
    </aside>
  );
}

/**
 * The first bookmarks as numbered buttons, and the rest behind "+N", which lists them all. The open
 * chat's number is outlined, or "+N" when the open chat is past the numbers.
 */
function RailBookmarks({ conversations, bookmarks, activeId, answeringId, onOpen }: ChatListProps) {
  const t = useMessages();
  const bookmarked = bookmarkedOf(conversations, bookmarks);
  if (bookmarked.length === 0) return null;
  const numbered = bookmarked.slice(0, RAIL_BOOKMARKS);
  const more = bookmarked.length - numbered.length;
  const activeIsMore = bookmarked.findIndex(({ id }) => id === activeId) >= RAIL_BOOKMARKS;

  return (
    <div
      role="group"
      aria-label={t.sidebar.bookmarks}
      className="mt-2 flex flex-col items-center gap-1 border-t border-rule pt-3"
    >
      {numbered.map(({ id, title }, index) => (
        <IconButton
          key={id}
          label={id === answeringId ? t.sidebar.answering(title) : title}
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
                label={t.sidebar.allBookmarks(bookmarked.length)}
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
                <span aria-hidden className="w-4 shrink-0 text-xs text-ink-3 tabular-nums">
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

const PAGES = [
  { href: "/benchmarks", label: "benchmarks", icon: <ChartColumn /> },
  { href: "/dashboard", label: "dashboard", icon: <Gauge /> },
  { href: "/how-it-answers", label: "howItAnswers", icon: <Workflow /> },
] as const;

function RailLink({ href, label, children }: { href: string; label: string; children: ReactNode }) {
  const current = usePathname() === href;
  return (
    <Link
      href={href}
      aria-label={label}
      title={label}
      aria-current={current ? "page" : undefined}
      className={cn(
        buttonVariants({ variant: "ghost", size: "icon-lg" }),
        ICON,
        current && OUTLINED,
      )}
    >
      {children}
    </Link>
  );
}

/** The rail's language button: it shows the interface language and switches to the other one. */
function RailLanguage() {
  const t = useMessages();
  const [language, setLanguage] = useLanguage();
  return (
    <IconButton
      label={`${t.language.switch}: ${t.language[language]}`}
      onClick={() => setLanguage(language === "en" ? "de" : "en")}
      className="font-mono text-[11px] uppercase"
    >
      {language}
    </IconButton>
  );
}

/** The chats on a phone: a drawer opened from ☰ in the header, closed by picking a chat. */
export function ChatDrawer(props: ChatListProps) {
  const t = useMessages();
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
        render={<IconButton label={t.sidebar.open} className="-ml-2 md:hidden print:hidden" />}
      >
        <Menu />
      </DialogTrigger>
      <SheetContent className="bg-panel">
        <div className="flex min-h-9 items-center justify-between px-3 pt-3">
          <DialogTitle className="pl-1 text-[15px] font-semibold">{t.sidebar.chats}</DialogTitle>
          <DialogClose render={<IconButton label={t.sidebar.close} />}>
            <X />
          </DialogClose>
        </div>
        <ChatList {...props} onOpen={thenClose(props.onOpen)} onNew={thenClose(props.onNew)} />
      </SheetContent>
    </Dialog>
  );
}

/**
 * "New chat", the links to the other pages, the bookmarked chats, the others by day, newest
 * first, what to know about where the chats are kept, the MCP server guide when `withMcp`, the
 * language and the settings. The current page is outlined.
 */
function ChatList({
  onNew,
  newChatOpen,
  removedBookmark,
  withMcp = false,
  ...props
}: ChatListProps & { withMcp?: boolean }) {
  const t = useMessages();
  const pathname = usePathname();
  return (
    <>
      <div className="flex flex-col gap-1 px-2.5 pt-1 pb-2">
        <button
          type="button"
          aria-current={newChatOpen ? "page" : undefined}
          onClick={onNew}
          className={cn(LIST_LINK, newChatOpen && CURRENT)}
        >
          <Plus />
          {t.sidebar.newChat}
        </button>
        {PAGES.map(({ href, label, icon }) => (
          <Link
            key={href}
            href={href}
            aria-current={pathname === href ? "page" : undefined}
            className={cn(LIST_LINK, pathname === href && CURRENT)}
          >
            {icon}
            {t.sidebar[label]}
          </Link>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        <ChatGroups {...props} />
      </div>
      {removedBookmark && <UndoBar {...removedBookmark} />}
      {props.available !== false && (
        <p className="border-t border-rule px-4 py-3 text-xs text-ink-3">{t.sidebar.savedHere}</p>
      )}
      <div className="flex flex-col gap-1 border-t border-rule px-2.5 pt-2 pb-3">
        {withMcp && (
          // Connecting an assistant needs a checkout on a computer, so the phone drawer leaves it out.
          <McpDialog trigger={<button type="button" className={LIST_LINK} />}>
            <Plug />
            {t.sidebar.mcpServer}
          </McpDialog>
        )}
        <div className="flex items-center gap-2">
          <ModelSettings trigger={<button type="button" className={cn(LIST_LINK, "flex-1")} />}>
            <Settings />
            {t.sidebar.settings}
          </ModelSettings>
          <LanguageSwitch className="shrink-0" />
          <UserMenu />
        </div>
      </div>
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
}: Omit<ChatListProps, "onNew" | "newChatOpen" | "removedBookmark">) {
  const t = useMessages();
  if (available === false) return <HistoryOff />;
  if (available === null) return null;
  if (conversations.length === 0) {
    return (
      <div className="flex flex-col gap-2 px-3 py-4 text-sm text-ink-2">
        <span className="font-medium text-foreground">{t.sidebar.noChats}</span>
        {t.sidebar.noChatsText}
      </div>
    );
  }
  return groupChats(conversations, bookmarks, new Date()).map((group) => (
    <section key={group.label} aria-label={t.sidebar.groups[group.label]}>
      <h2 className="px-2 pt-3 pb-1 text-xs font-medium text-ink-3">
        {t.sidebar.groups[group.label]}
      </h2>
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
      className="absolute top-0.5 right-0.5 size-3 animate-spin text-ink-3 motion-reduce:animate-none"
    />
  );
}

function UndoBar({ title, onUndo }: { title: string; onUndo: () => void }) {
  const t = useMessages();
  return (
    <div
      role="status"
      className="mx-2 mb-2 flex items-center gap-1 rounded-md bg-ink py-1.5 pr-1.5 pl-3 text-[13px] text-page"
    >
      <p className="min-w-0 flex-1 truncate">
        {t.sidebar.removedBefore}
        <span className="inline-block max-w-28 truncate align-bottom">{title}</span>
        {t.sidebar.removedAfter}
      </p>
      <span aria-hidden>·</span>
      <Button
        variant="ghost"
        size="sm"
        onClick={onUndo}
        className="font-semibold text-inherit hover:bg-page/15 hover:text-inherit"
      >
        {t.sidebar.undo}
      </Button>
    </div>
  );
}

function HistoryOff() {
  const t = useMessages();
  return (
    <div className="mx-1 my-2 flex flex-col gap-1 rounded-lg border border-rule-2 bg-card px-3 py-2.5 text-[13px] leading-4.5 text-ink">
      <b className="font-semibold">{t.sidebar.historyOffTitle}</b>
      {t.sidebar.historyOffText}
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
