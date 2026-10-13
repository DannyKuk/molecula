"use client";

import type { ReactNode } from "react";

/** Scrolls to the drug's 3D view in the same turn. */
export function ViewIn3D({ cid, children }: { cid: number; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={(event) =>
        event.currentTarget
          .closest("[data-turn]")
          ?.querySelector(`[data-structure="${cid}"]`)
          ?.scrollIntoView({
            behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
            block: "start",
          })
      }
      className="rounded-md border border-zinc-300 px-3 py-1 hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:border-zinc-700 dark:hover:bg-zinc-900"
    >
      {children}
    </button>
  );
}
