"use client";

import { createContext, useContext, type ReactNode } from "react";

/** Opens the evidence panel's 3D tab on a drug of the answer it shows. */
export const ShowStructure = createContext<((cid: number) => void) | null>(null);

/** Opens the drug's 3D view in the evidence panel. */
export function ViewIn3D({ cid, children }: { cid: number; children: ReactNode }) {
  const show = useContext(ShowStructure);
  return (
    <button
      type="button"
      onClick={() => show?.(cid)}
      className="rounded-md border border-rule-2 px-3 py-1 hover:bg-panel focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3"
    >
      {children}
    </button>
  );
}
