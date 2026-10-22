"use client";

import { getDrugs } from "@/lib/api";
import { useMessages } from "@/lib/messages";
import { useFetched } from "@/lib/use-fetched";

import { SupportedDrugs } from "./supported-drugs";

/** Fetches the supported drugs from the backend and shows them as a searchable list. */
export function SupportedDrugsLoader({ onAsk }: { onAsk: (question: string) => void }) {
  const t = useMessages();
  const state = useFetched(getDrugs, []);

  if (state.kind === "loading") {
    return (
      <p role="status" className="text-sm text-ink-2">
        {t.drugs.loading}
      </p>
    );
  }
  if (state.kind === "failed") {
    return (
      <p role="alert" className="text-sm text-red-700 dark:text-red-400">
        {t.drugs.failed}
      </p>
    );
  }
  return <SupportedDrugs drugs={state.value} onAsk={onAsk} />;
}
