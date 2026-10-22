"use client";

import { cn } from "cn";
import { Check, Copy } from "lucide-react";

import { useMessages } from "@/lib/messages";
import { useTransient } from "@/lib/use-transient";

const SHOWN_MS = 2000;

type CopyButtonProps = {
  /** The text to copy, read when the button is clicked. */
  text: () => string;
  /** What the button says before it is clicked. */
  label: string;
  /** A fuller name for screen readers than `label`; once clicked they hear the outcome instead. */
  ariaLabel?: string;
  className: string;
};

/** Copies `text` to the clipboard and says for two seconds whether it worked. */
export function CopyButton({ text, label, ariaLabel, className }: CopyButtonProps) {
  const t = useMessages();
  const [outcome, show] = useTransient<"copied" | "failed">(SHOWN_MS);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text());
      show("copied");
    } catch {
      show("failed");
    }
  }

  const said = outcome ? t.copy[outcome] : null;
  const Icon = outcome === "copied" ? Check : Copy;
  return (
    <button
      type="button"
      onClick={copy}
      aria-label={ariaLabel === undefined ? undefined : (said ?? ariaLabel)}
      className={cn(
        "inline-flex items-center gap-1 rounded-md py-0.5 text-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3",
        className,
      )}
    >
      <Icon aria-hidden className="size-3.5" />
      <span aria-live="polite">{said ?? label}</span>
    </button>
  );
}
