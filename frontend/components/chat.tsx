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
import { PrintedEnd, PrintedHeader } from "./printed-conversation";
import { QuestionNavigator } from "./question-navigator";
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
  const scrollerRef = useRef<HTMLDivElement>(null);
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
  } = useConversations(initialQuestion, saved.save, () =>
    scrollerRef.current?.scrollTo({ top: 0 }),
  );
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

  // The chat and the panel beside it show the same turn. A phone's sheet covers the chat, so
  // there it opens only from the pills, and the turn it shows follows the chat behind it.
  const wide = useMediaQuery(WIDE_SCREEN);
  const { followAgain, scrollToTop } = useFollowAnswer(
    scrollerRef,
    conversationRef,
    sent,
    answering,
    () => {
      const scroller = scrollerRef.current;
      const list = conversationRef.current;
      if (!scroller || !list?.children.length) return;
      const read = readTurn(scroller, list.children);
      if (read !== panelTurn) setShown({ turn: read, tab: defaultTab(turns[read]) });
    },
  );
  const scrollToTurn = (index: number) => {
    const turn = conversationRef.current?.children[index];
    if (turn instanceof HTMLElement) scrollToTop(turn);
  };
  const showInPanel = (next: Shown) => {
    if (next.turn !== panelTurn) scrollToTurn(next.turn ?? newest);
    setShown(next);
  };
  const jumpTo = (index: number) => {
    scrollToTurn(index);
    if (index !== panelTurn) setShown({ turn: index, tab: defaultTab(turns[index]) });
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
    <div className="flex h-dvh print:h-auto">
      <ChatSidebar {...chatList} />
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="mx-auto flex w-full max-w-3xl items-center justify-between gap-4 px-4 py-4 sm:px-6 print:hidden">
          <div className="flex items-center gap-3">
            <ChatDrawer {...chatList} />
            <h1 className="text-[17px] font-semibold tracking-tight">Molecula</h1>
            <ModelStatus />
            {usage && (
              // Each answer shows its own line, so a phone leaves the total out of the header.
              <p className="hidden font-mono text-[11px] text-ink-3 tabular-nums sm:block">
                This chat: {formatUsage(usage)}
              </p>
            )}
          </div>
          <nav className="flex items-center gap-4 text-[13.5px] text-ink-2">
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
        <div className="relative min-h-0 flex-1">
          <div
            ref={scrollerRef}
            data-chat-scroll
            className="thin-scrollbar scrollbar-on-hover h-full overflow-y-auto [scrollbar-gutter:stable] print:h-auto print:overflow-visible"
          >
            <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col px-4 sm:px-6">
              <div className="flex flex-1 flex-col gap-6 pr-3 pb-6 sm:pr-0">
                {turns.length === 0 ? (
                  <EmptyState onAsk={ask} />
                ) : (
                  <>
                    <PrintedHeader title={title} questions={turns.map((turn) => turn.question)} />
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
                    <PrintedEnd turns={turns} />
                  </>
                )}
              </div>
              {/* Inside the scroll area, so its scrollbar runs beside the question box and the end
                  of the conversation stops above it. */}
              <div className="pointer-events-none sticky bottom-0 z-10 bg-[linear-gradient(transparent,var(--background)_1.5rem)] pt-6 print:hidden">
                <div className="pointer-events-auto flex flex-col gap-2 pb-3">
                  <ChatComposer answering={pendingAnswer} onSend={ask} onStop={stop} />
                  {saved.available === false && (
                    <p className="text-sm text-ink">
                      History is off in this browser, so this chat isn&apos;t saved.
                    </p>
                  )}
                  <Disclaimer />
                </div>
              </div>
            </div>
          </div>
          {turns.length > 1 && (
            <QuestionNavigator
              questions={turns.map((turn) => turn.question)}
              read={panelTurn}
              live={live}
              onJump={jumpTo}
            />
          )}
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
