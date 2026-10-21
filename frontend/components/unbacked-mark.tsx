"use client";

import { createContext, useContext, type ReactNode } from "react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { CheckedClaim } from "@/lib/chat";
import { useMessages } from "@/lib/messages";
import { unbackedReason } from "@/lib/source-check";

/** The claims of the answer's source check, by the index a mark carries. */
export const CheckedClaimsContext = createContext<CheckedClaim[]>([]);

/** Text of a claim the sources don't back, underlined; its popover says why. */
export function UnbackedMark({ claim, children }: { claim: number; children: ReactNode }) {
  const t = useMessages();
  const checked = useContext(CheckedClaimsContext)[claim];
  if (!checked) return <>{children}</>;
  return (
    <Popover>
      <PopoverTrigger
        openOnHover
        delay={150}
        nativeButton={false}
        render={<mark />}
        className="cursor-help bg-transparent text-current underline decoration-amber-500 decoration-dotted decoration-2 underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3"
      >
        {children}
      </PopoverTrigger>
      <PopoverContent align="start" className="gap-1">
        <p className="font-medium text-amber-700 dark:text-amber-400">{t.check.notInSources}</p>
        <p className="text-ink-2">{unbackedReason(checked, t)}</p>
      </PopoverContent>
    </Popover>
  );
}
