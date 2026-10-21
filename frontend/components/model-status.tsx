"use client";

import { useEffect, useState } from "react";

import { type ChatModel, getChatModel } from "@/lib/api";
import { en, type Messages, useMessages } from "@/lib/messages";

/** "gpt-oss-20b · local": the model's id without its provider, and where it runs. */
export function modelLabel(model: ChatModel, t: Messages = en): string {
  const name = model.name.split("/").at(-1) ?? model.name;
  return model.local ? `${name} · ${t.model.local}` : name;
}

/** A green light and the name of the model that answers; nothing while the chat is off. */
export function ModelStatus() {
  const t = useMessages();
  const [model, setModel] = useState<ChatModel | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getChatModel(controller.signal)
      .then(setModel)
      .catch(() => {});
    return () => controller.abort();
  }, []);

  if (!model) return null;
  return (
    <p className="hidden items-center gap-1.5 text-[12.5px] whitespace-nowrap text-ink-3 sm:flex print:hidden">
      <span aria-hidden className="size-1.5 rounded-full bg-ok" />
      {modelLabel(model, t)}
    </p>
  );
}
