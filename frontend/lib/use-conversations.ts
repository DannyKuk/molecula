import { useCallback, useEffect, useRef, useState } from "react";

import { failureText, requestMessages, streamChat } from "./chat";
import { newConversationId } from "./chat-history";
import {
  applyEvent,
  conversationWith,
  endTurn,
  failTurn,
  pending,
  queueTurn,
  startTurn,
  stopTurn,
  type Turn,
} from "./chat-turn";
import { chosenChecker, chosenModel } from "./use-chosen-model";

/** A question and the chat it was asked in, with the turns before it. */
type Asked = { id: string; question: string; earlier: Turn[]; askedAt: number };

/**
 * The chats this page has answered, the one on screen and the answers coming in. One answer
 * streams at a time, into its own chat also while another chat is shown; a question asked in a
 * chat meanwhile waits in line as a queued turn and starts once the answers before it end. Each
 * answer is saved under its chat's id when it is asked, when it starts and when it ends.
 */
export function useConversations(
  initialQuestion: string | undefined,
  save: (id: string, turns: Turn[]) => void,
) {
  const [shown, setShown] = useState<{ id: string | null; turns: Turn[] }>({ id: null, turns: [] });
  const [busy, setBusy] = useState<{ answeringId: string | null; queuedIds: string[] }>({
    answeringId: null,
    queuedIds: [],
  });
  const [sent, setSent] = useState(0);
  const shownIdRef = useRef<string | null>(null);
  const chats = useRef(new Map<string, Turn[]>());
  const removed = useRef(new Set<string>());
  const running = useRef<{ id: string; controller: AbortController } | null>(null);
  const line = useRef<Asked[]>([]);
  const saveRef = useRef(save);

  useEffect(() => {
    saveRef.current = save;
  }, [save]);

  // Each update sets the whole list rather than changing the current one: hydrated inside a
  // Suspense boundary, the chat starts the linked question at idle priority, and React renders
  // the stream's updates before that start (#218).
  const setTurnsOf = useCallback((id: string, turns: Turn[]) => {
    if (removed.current.has(id)) return;
    chats.current.set(id, turns);
    if (shownIdRef.current === id) setShown({ id, turns });
  }, []);

  const showBusy = useCallback(() => {
    setBusy({
      answeringId: running.current?.id ?? null,
      queuedIds: line.current.map((asked) => asked.id),
    });
  }, []);

  /** Streams the answer into its chat until the stream ends or `controller` aborts it. */
  const streamAnswer = useCallback(
    async ({ id, question, earlier, askedAt }: Asked, controller: AbortController) => {
      let latest: Turn = { ...startTurn(question), askedAt };
      const updateLatest = (change: (turn: Turn) => Turn) => {
        latest = change(latest);
        if (running.current?.controller === controller) setTurnsOf(id, [...earlier, latest]);
      };

      setTurnsOf(id, [...earlier, latest]);
      saveRef.current(id, [...earlier, latest]);
      try {
        const messages = requestMessages(conversationWith(earlier, question));
        const answering = streamChat(messages, controller.signal, chosenModel(), chosenChecker());
        for await (const event of answering) {
          updateLatest((turn) => applyEvent(turn, event));
          // `done` or `error` ends the answer, so the next one in line needn't wait for the close.
          if (latest.state !== "answering") break;
        }
        updateLatest(endTurn);
      } catch (error) {
        if (controller.signal.aborted) updateLatest(stopTurn);
        else updateLatest((turn) => failTurn(turn, failureText(error)));
      }
      updateLatest((turn) => ({ ...turn, answeredAt: Date.now() }));
      saveRef.current(id, [...earlier, latest]);
    },
    [setTurnsOf],
  );

  /** Answers `first`, then each question that joined the line meanwhile, one after another. */
  const answerInLine = useCallback(
    async (first: Asked) => {
      for (let next: Asked | undefined = first; next; next = line.current.shift()) {
        const controller = new AbortController();
        running.current = { id: next.id, controller };
        showBusy();
        await streamAnswer(next, controller);
        // Closing the page took the answer away from this line, and the line with it.
        if (running.current?.controller !== controller) return;
      }
      running.current = null;
      showBusy();
    },
    [showBusy, streamAnswer],
  );

  useEffect(
    () => () => {
      const leaving = running.current;
      running.current = null;
      line.current = [];
      leaving?.controller.abort();
    },
    [],
  );

  const askIn = useCallback(
    (question: string, earlier: Turn[]) => {
      const asked = {
        id: (shownIdRef.current ??= newConversationId()),
        question,
        earlier,
        askedAt: Date.now(),
      };
      setSent((count) => count + 1);
      if (!running.current) {
        answerInLine(asked);
        return;
      }
      line.current.push(asked);
      const turns = [...earlier, { ...queueTurn(question), askedAt: asked.askedAt }];
      setTurnsOf(asked.id, turns);
      saveRef.current(asked.id, turns);
      showBusy();
    },
    [answerInLine, setTurnsOf, showBusy],
  );

  useEffect(() => {
    if (initialQuestion) askIn(initialQuestion, []);
  }, [initialQuestion, askIn]);

  /** Takes the chat's question out of the line; false when it has none waiting. */
  const leaveLine = (id: string) => {
    const index = line.current.findIndex((asked) => asked.id === id);
    if (index < 0) return false;
    line.current.splice(index, 1);
    showBusy();
    return true;
  };

  /** Shows another conversation, or an empty one with `null`; an answer coming in keeps going. */
  const show = (id: string | null, turns: Turn[]) => {
    shownIdRef.current = id;
    setShown({ id, turns });
  };

  const { id, turns } = shown;
  const ask = (question: string) => {
    if (!pending(turns.at(-1))) askIn(question, turns);
  };
  const retry = () => askIn(turns[turns.length - 1].question, turns.slice(0, -1));

  /** Stops the shown chat's answer, or takes its question out of the line. */
  const stop = () => {
    if (!id) return;
    if (running.current?.id === id) running.current.controller.abort();
    else if (leaveLine(id)) {
      const stopped = [...turns.slice(0, -1), stopTurn(turns[turns.length - 1])];
      setTurnsOf(id, stopped);
      saveRef.current(id, stopped);
    }
  };

  /** Opens a saved conversation, as this page last had it if it answered there. */
  const open = (openedId: string, savedTurns: Turn[]) =>
    show(openedId, chats.current.get(openedId) ?? savedTurns);
  const startNew = () => show(null, []);

  /** Forgets a deleted conversation, ending its answer or its place in the line. */
  const remove = (removedId: string) => {
    removed.current.add(removedId);
    chats.current.delete(removedId);
    leaveLine(removedId);
    if (running.current?.id === removedId) running.current.controller.abort();
    if (removedId === id) startNew();
  };

  return {
    id,
    turns,
    answering: turns.at(-1)?.state === "answering",
    pendingAnswer: pending(turns.at(-1)),
    sent,
    ...busy,
    ask,
    retry,
    stop,
    open,
    startNew,
    remove,
  };
}
