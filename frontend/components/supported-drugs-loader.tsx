"use client";

import { useEffect, useState } from "react";

import { type Drug, getDrugs } from "@/lib/api";
import { useMessages } from "@/lib/messages";

import { SupportedDrugs } from "./supported-drugs";

type LoadState = { kind: "loading" } | { kind: "failed" } | { kind: "loaded"; drugs: Drug[] };

/** Fetches the supported drugs from the backend and shows them as a searchable list. */
export function SupportedDrugsLoader({ onAsk }: { onAsk: (question: string) => void }) {
  const t = useMessages();
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    getDrugs(controller.signal)
      .then((drugs) => setState({ kind: "loaded", drugs }))
      .catch(() => {
        if (!controller.signal.aborted) setState({ kind: "failed" });
      });
    return () => controller.abort();
  }, []);

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
  return <SupportedDrugs drugs={state.drugs} onAsk={onAsk} />;
}
