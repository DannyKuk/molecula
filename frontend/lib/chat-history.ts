import { stopTurn, type Turn } from "./chat-turn";

/** A conversation as the browser keeps it, titled by its first question until it is renamed. */
export type Conversation = {
  id: string;
  title: string;
  turns: Turn[];
  createdAt: number;
  updatedAt: number;
};

export type ConversationSummary = Omit<Conversation, "turns">;

/** Where the conversations and the bookmarks are kept. Every method rejects when the storage fails. */
export interface ChatHistory {
  list(): Promise<ConversationSummary[]>;
  get(id: string): Promise<Conversation | undefined>;
  put(conversation: Conversation): Promise<void>;
  delete(id: string): Promise<void>;
  /** The ids of the bookmarked conversations, in the order they were bookmarked. */
  bookmarks(): Promise<string[]>;
  putBookmarks(ids: string[]): Promise<void>;
}

export function newConversationId(): string {
  // `crypto.randomUUID` exists only on HTTPS and localhost, and a deployment may be neither.
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function summaryOf({ id, title, createdAt, updatedAt }: Conversation): ConversationSummary {
  return { id, title, createdAt, updatedAt };
}

/** The conversation `id` with `turns`, keeping the title and start time it was saved with. */
export function withTurns(
  saved: Conversation | undefined,
  id: string,
  turns: Turn[],
  now: number,
): Conversation {
  return {
    id,
    title: saved?.title ?? turns[0]?.question ?? "",
    turns,
    createdAt: saved?.createdAt ?? now,
    updatedAt: now,
  };
}

/** The turns of a saved conversation as the chat reopens them: no answer streams across a reload. */
export function reopenedTurns(turns: Turn[]): Turn[] {
  return turns.map((turn) => (turn.state === "answering" ? stopTurn(turn) : turn));
}

export type DayGroup = {
  label: "Today" | "Yesterday" | "Earlier";
  conversations: ConversationSummary[];
};

export type ChatGroup = {
  label: "Bookmarked" | DayGroup["label"];
  conversations: ConversationSummary[];
};

/** The bookmarked conversations in bookmark order, skipping ids whose conversation is gone. */
export function bookmarkedOf(
  conversations: ConversationSummary[],
  bookmarks: string[],
): ConversationSummary[] {
  const byId = new Map(conversations.map((conversation) => [conversation.id, conversation]));
  return bookmarks.flatMap((id) => byId.get(id) ?? []);
}

/** The bookmarked conversations on top, then the others under Today, Yesterday and Earlier. */
export function groupChats(
  conversations: ConversationSummary[],
  bookmarks: string[],
  now: Date,
): ChatGroup[] {
  const bookmarked = bookmarkedOf(conversations, bookmarks);
  const days = groupByDay(
    conversations.filter((conversation) => !bookmarks.includes(conversation.id)),
    now,
  );
  return bookmarked.length > 0
    ? [{ label: "Bookmarked", conversations: bookmarked }, ...days]
    : days;
}

/** The conversations newest first, under Today, Yesterday and Earlier by their last change. */
export function groupByDay(conversations: ConversationSummary[], now: Date): DayGroup[] {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1).getTime();
  const labelOf = (updatedAt: number): DayGroup["label"] =>
    updatedAt >= today ? "Today" : updatedAt >= yesterday ? "Yesterday" : "Earlier";
  const groups: DayGroup[] = [];
  for (const conversation of newestFirst(conversations)) {
    const label = labelOf(conversation.updatedAt);
    const group = groups.at(-1);
    if (group?.label === label) group.conversations.push(conversation);
    else groups.push({ label, conversations: [conversation] });
  }
  return groups;
}

function newestFirst(conversations: ConversationSummary[]): ConversationSummary[] {
  return [...conversations].sort((a, b) => b.updatedAt - a.updatedAt);
}
