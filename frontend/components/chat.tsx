"use client";

import { X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Dialog, DialogClose, DialogTitle } from "@/components/ui/dialog";
import { SheetContent } from "@/components/ui/sheet";
import { type ChatHistory, reopenedTurns } from "@/lib/chat-history";
import { browserHistory } from "@/lib/chat-history-indexeddb";
import { defaultTab, type Shown } from "@/lib/evidence";
import { readTurn } from "@/lib/read-turn";
import { structuresOf } from "@/lib/tool-cards";
import { conversationUsage, formatUsage } from "@/lib/usage";
import { useChatHistory } from "@/lib/use-chat-history";
import { useConversations } from "@/lib/use-conversations";
import { useFollowAnswer } from "@/lib/use-follow-answer";
import { useMediaQuery } from "@/lib/use-media-query";

import { ChatComposer } from "./chat-composer";
import { ChatDrawer, type ChatListProps, ChatSidebar } from "./chat-sidebar";
import { ConversationTurn } from "./conversation-turn";
import { Disclaimer } from "./disclaimer";
import { EvidencePanel } from "./evidence-panel";
import { ExportMenu } from "./export-menu";
import { HelpDialog, HelpGuide } from "./help-guide";
import { ModelStatus } from "./model-status";
import { useBookmarkUndo } from "./saved-chats";

/** Wide enough for the evidence panel beside the chat; narrower screens open it as a sheet. */
export const WIDE_SCREEN = "(min-width: 900px)";

type ChatProps = {
  initialQuestion?: string;
  /** A saved chat to open, from a link on another page (`savedChatLink`). */
  initialChatId?: string;
  /** Where the conversations are kept; the browser's IndexedDB unless a test passes its own. */
  history?: ChatHistory;
};

/** The chat: the saved chats, the conversation so far, the question box and the help guide. */
export function Chat({ initialQuestion, initialChatId, history = browserHistory }: ChatProps) {
  const saved = useChatHistory(history);
  const {
    id,
    turns,
    answering,
    pendingAnswer,
    sent,
    answeringId,
    queuedIds,
    ask,
    retry,
    stop,
    open,
    startNew,
    remove,
  } = useConversations(initialQuestion, saved.save);
  const conversationRef = useRef<HTMLOListElement>(null);

  // Null shows the newest answer on its own default tab; a sent question shows its steps.
  const [shown, setShown] = useState<Shown | null>(null);
  const [shownFor, setShownFor] = useState({ id, sent });
  if (shownFor.id !== id || shownFor.sent !== sent) {
    setShownFor({ id, sent });
    setShown(shownFor.sent !== sent ? { turn: null, tab: "steps" } : null);
  }
  const newest = turns.length - 1;
  const panelTurn = Math.min(shown?.turn ?? newest, newest);
  const live = pendingAnswer ? newest : null;

  // A live answer's 3D tab opens by itself once, when its structure arrives while the panel shows it.
  const [opened3dFor, setOpened3dFor] = useState<string | null>(null);
  const liveQuestion = `${id}:${sent}`;
  if (
    live !== null &&
    live === panelTurn &&
    opened3dFor !== liveQuestion &&
    structuresOf(turns[live].steps).length > 0
  ) {
    setOpened3dFor(liveQuestion);
    setShown({ turn: live, tab: "3d", fresh: true });
  }

  // The chat and the panel beside it show the same turn. A phone's sheet covers the chat, and its
  // scroll lock moves the page's scroll position, so there the sheet only opens from the pills.
  const wide = useMediaQuery(WIDE_SCREEN);
  const { followAgain, scrollToTop } = useFollowAnswer(conversationRef, sent, answering, () => {
    const list = conversationRef.current;
    if (!wide || !list?.children.length) return;
    const read = readTurn(list.children);
    if (read !== panelTurn) setShown({ turn: read, tab: defaultTab(turns[read]) });
  });
  const showInPanel = (next: Shown) => {
    const turn = conversationRef.current?.children[next.turn ?? newest];
    if (wide && next.turn !== panelTurn && turn instanceof HTMLElement) scrollToTop(turn);
    setShown(next);
  };
  const backToLive =
    live !== null && panelTurn !== live
      ? () => {
          setShown(null);
          followAgain();
        }
      : undefined;

  const [sheetOpen, setSheetOpen] = useState(false);
  const showEvidence = (next: Shown) => {
    setShown(next);
    if (!wide) setSheetOpen(true);
  };
  const evidence = turns.length > 0 && (
    <EvidencePanel
      turns={turns}
      shown={{ ...(shown ?? { tab: defaultTab(turns[newest]) }), turn: panelTurn }}
      onShow={showInPanel}
      backToLive={backToLive}
      close={
        !wide && (
          <DialogClose
            aria-label="Close"
            className="grid size-7 place-items-center rounded-md border border-rule-2 bg-card text-ink-2"
          >
            <X aria-hidden className="size-4" />
          </DialogClose>
        )
      }
    />
  );

  const { removedBookmark, unbookmark } = useBookmarkUndo(saved);
  const usage = conversationUsage(turns);
  const title =
    saved.conversations.find((conversation) => conversation.id === id)?.title ??
    turns[0]?.question ??
    "";

  const openSaved = async (openedId: string) => {
    const conversation = await saved.load(openedId);
    if (conversation) open(conversation.id, reopenedTurns(conversation.turns));
  };

  const openedLinkedChat = useRef(false);
  useEffect(() => {
    if (!initialChatId || openedLinkedChat.current) return;
    openedLinkedChat.current = true;
    void saved.load(initialChatId).then((conversation) => {
      if (conversation) open(conversation.id, reopenedTurns(conversation.turns));
    });
  }, [initialChatId, saved, open]);

  const chatList: ChatListProps = {
    available: saved.available,
    conversations: saved.conversations,
    bookmarks: saved.bookmarks,
    activeId: id,
    answeringId,
    queuedIds,
    removedBookmark,
    onOpen: (openedId) => {
      if (openedId !== id) void openSaved(openedId);
    },
    onNew: startNew,
    onRename: saved.rename,
    onDelete: (deletedId) => {
      remove(deletedId);
      saved.remove(deletedId);
    },
    onBookmark: saved.bookmark,
    onUnbookmark: unbookmark,
  };

  return (
    <div className="flex flex-1">
      <ChatSidebar {...chatList} />
      <main className="mx-auto flex w-full max-w-3xl min-w-0 flex-1 flex-col px-4 sm:px-6">
        <header className="flex items-center justify-between gap-4 py-4">
          <div className="flex items-center gap-3">
            <ChatDrawer {...chatList} />
            <h1 className="text-[17px] font-semibold tracking-tight">Molecula</h1>
            <ModelStatus />
            {usage && (
              // Each answer shows its own line, so a phone leaves the total out of the header.
              <p className="hidden font-mono text-[11px] text-ink-3 tabular-nums sm:block print:hidden">
                This chat: {formatUsage(usage)}
              </p>
            )}
          </div>
          <nav className="flex items-center gap-4 text-[13.5px] text-ink-2 print:hidden">
            <Link href="/drugs" className="font-medium underline-offset-4 hover:underline">
              Supported drugs
            </Link>
            <Link
              href="/benchmarks"
              className="hidden font-medium underline-offset-4 hover:underline sm:inline"
            >
              Benchmarks
            </Link>
            {turns.length > 0 && (
              <ExportMenu title={title} turns={turns} disabled={pendingAnswer} />
            )}
            <HelpDialog onAsk={ask} />
          </nav>
        </header>
        <div className="flex flex-1 flex-col gap-6 pb-12">
          {turns.length === 0 ? (
            <EmptyState onAsk={ask} />
          ) : (
            <>
              <PrintedTitle title={title} />
              <ol
                // Keyed by conversation, so an opened chat doesn't keep the last one's open steps.
                key={id}
                ref={conversationRef}
                aria-label="Conversation"
                className="flex flex-col gap-8"
              >
                {turns.map((turn, index) => (
                  <ConversationTurn
                    key={index}
                    turn={turn}
                    number={index + 1}
                    active={index === panelTurn}
                    onShow={(tab, refs) => showEvidence({ turn: index, tab, refs })}
                    onAsk={ask}
                    chatAnswering={pendingAnswer}
                    onRetry={index === turns.length - 1 ? retry : undefined}
                  />
                ))}
              </ol>
            </>
          )}
        </div>
        <div className="sticky bottom-0 flex flex-col gap-2 border-t border-rule bg-background py-3 print:static print:border-0">
          <div className="contents print:hidden">
            <ChatComposer answering={pendingAnswer} onSend={ask} onStop={stop} />
          </div>
          {saved.available === false && (
            <p className="text-sm text-ink print:hidden">
              History is off in this browser, so this chat isn&apos;t saved.
            </p>
          )}
          <Disclaimer />
        </div>
      </main>
      {wide && evidence && (
        <aside
          data-evidence
          aria-label="Evidence"
          className="sticky top-0 flex h-dvh w-[440px] flex-none flex-col self-start border-l border-rule bg-panel print:hidden"
        >
          {evidence}
        </aside>
      )}
      {!wide && evidence && (
        <Dialog open={sheetOpen} onOpenChange={setSheetOpen}>
          <SheetContent side="bottom" className="top-auto h-[78dvh] rounded-t-2xl bg-panel">
            <DialogTitle className="sr-only">Evidence</DialogTitle>
            {evidence}
          </SheetContent>
        </Dialog>
      )}
    </div>
  );
}

/** The conversation's title and the day it was printed, at the top of the first page. */
function PrintedTitle({ title }: { title: string }) {
  const printedOn = new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  return (
    <section aria-label="Printed conversation" className="hidden print:block">
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="text-sm text-ink-2">Printed on {printedOn}</p>
    </section>
  );
}

function EmptyState({ onAsk }: { onAsk: (question: string) => void }) {
  return (
    <section className="flex flex-col gap-4">
      <p className="text-ink-2">
        Ask about medicines: what they are for, how they work and what they bind to.
      </p>
      <HelpGuide onAsk={onAsk} />
    </section>
  );
}
