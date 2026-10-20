"use client";

import { type FormEvent, type KeyboardEvent, useId, useState } from "react";

import { questionProblem } from "@/lib/chat";

type ChatComposerProps = {
  answering: boolean;
  onSend: (question: string) => void;
  onStop: () => void;
};

/** The question box: Enter sends, Shift+Enter starts a new line, Stop ends the answer. */
export function ChatComposer({ answering, onSend, onStop }: ChatComposerProps) {
  const [draft, setDraft] = useState("");
  const inputId = useId();
  const problemId = useId();
  const problem = questionProblem(draft);
  const canSend = !answering && !problem && draft.trim() !== "";

  function send(event: FormEvent | KeyboardEvent) {
    event.preventDefault();
    if (!canSend) return;
    onSend(draft.trim());
    setDraft("");
  }

  function sendOnEnter(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) send(event);
  }

  return (
    <form onSubmit={send} className="flex flex-col gap-1.5">
      <div className="flex items-end gap-2">
        <label htmlFor={inputId} className="sr-only">
          Ask about a medicine
        </label>
        <textarea
          id={inputId}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={sendOnEnter}
          rows={2}
          placeholder="Ask about a medicine, e.g. How does imatinib work?"
          aria-invalid={problem !== null}
          aria-describedby={problem ? problemId : undefined}
          className="max-h-48 min-h-11 flex-1 resize-y rounded-[10px] border border-rule-2 bg-card px-3 py-2 text-base outline-none focus:border-ink-3 focus:ring-2 focus:ring-rule-2"
        />
        {answering ? (
          <button type="button" onClick={onStop} className={`${BUTTON_CLASSES} bg-ink text-page`}>
            Stop
          </button>
        ) : (
          <button
            type="submit"
            disabled={!canSend}
            className={`${BUTTON_CLASSES} bg-signal text-white`}
          >
            Send
          </button>
        )}
      </div>
      {problem && (
        <p id={problemId} role="alert" className="text-sm text-red-700 dark:text-red-400">
          {problem}
        </p>
      )}
    </form>
  );
}

const BUTTON_CLASSES =
  "min-h-11 rounded-lg px-4 font-semibold hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3 disabled:cursor-not-allowed disabled:opacity-40";
