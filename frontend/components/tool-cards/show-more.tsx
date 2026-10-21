"use client";

import { useState, type ReactNode } from "react";

import { useMessages } from "@/lib/messages";

/** The first `shown` items, and a button that shows the rest. */
export function ShowMore<T>({
  items,
  shown,
  render,
}: {
  items: T[];
  shown: number;
  render: (item: T, index: number) => ReactNode;
}) {
  const t = useMessages();
  const [all, setAll] = useState(false);
  const visible = all ? items : items.slice(0, shown);
  return (
    <>
      {visible.map(render)}
      {items.length > visible.length && (
        <button
          type="button"
          onClick={() => setAll(true)}
          className="text-xs text-muted-foreground underline underline-offset-4"
        >
          {t.cards.showAll(items.length)}
        </button>
      )}
    </>
  );
}
