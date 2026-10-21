"use client";

import type { ChatModel } from "@/lib/api";
import { shortName, useModelChoices } from "@/lib/use-model-choices";

/** "gpt-oss-20b · local": the model's id without its provider, and where it runs. */
export function modelLabel(model: ChatModel): string {
  const name = shortName(model.name);
  return model.local ? `${name} · local` : name;
}

/** A green light and the name of the model that writes the next answer; nothing while the chat
 * is off. */
export function ModelStatus() {
  const { answering } = useModelChoices();

  if (!answering) return null;
  return (
    <p className="hidden items-center gap-1.5 text-[12.5px] text-ink-3 sm:flex print:hidden">
      <span aria-hidden className="size-1.5 rounded-full bg-ok" />
      {modelLabel(answering)}
    </p>
  );
}
