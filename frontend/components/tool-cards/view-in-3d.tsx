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
      className="rounded-md border border-rule-2 px-3 py-1 hover:bg-panel focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3"
    >
      {children}
    </button>
  );
}
