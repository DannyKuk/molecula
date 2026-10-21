"use client";

import { type FormEvent, type KeyboardEvent, useId, useState } from "react";

import { questionProblem } from "@/lib/chat";
import { useMessages } from "@/lib/messages";

type ChatComposerProps = {
  answering: boolean;
  onSend: (question: string) => void;
  onStop: () => void;
};

/** The question box: Enter sends, Shift+Enter starts a new line, Stop ends the answer. */
export function ChatComposer({ answering, onSend, onStop }: ChatComposerProps) {
  const t = useMessages();
  const [draft, setDraft] = useState("");
  const inputId = useId();
  const problemId = useId();
  const problem = questionProblem(draft, t);
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
      <div className="overflow-hidden rounded-xl border border-rule-2 bg-card focus-within:border-ink-3 focus-within:ring-2 focus-within:ring-rule-2">
        <label htmlFor={inputId} className="sr-only">
          {t.composer.label}
        </label>
        <textarea
          id={inputId}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={sendOnEnter}
          rows={2}
          placeholder={t.composer.placeholder}
          aria-invalid={problem !== null}
          aria-describedby={problem ? problemId : undefined}
          className="block max-h-48 min-h-14 w-full resize-none bg-transparent px-3.5 pt-2.5 pb-1 text-base outline-none"
        />
        <div className="flex items-center gap-3 border-t border-rule bg-panel py-1.5 pr-1.5 pl-3.5">
          <p className="text-xs text-ink-3 max-sm:hidden">{t.composer.hint}</p>
          {answering ? (
            <button type="button" onClick={onStop} className={`${BUTTON_CLASSES} bg-ink text-page`}>
              {t.composer.stop}
            </button>
          ) : (
            <button
              type="submit"
              disabled={!canSend}
              className={`${BUTTON_CLASSES} bg-signal text-white`}
            >
              {t.composer.send}
              <kbd aria-hidden className="font-mono text-[11px] opacity-80">
                ↵
              </kbd>
            </button>
          )}
        </div>
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
  "ml-auto flex min-h-8 items-center gap-2 rounded-lg px-3 text-[13px] font-semibold hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3 disabled:cursor-not-allowed disabled:opacity-40";
