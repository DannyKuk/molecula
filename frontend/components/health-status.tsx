"use client";

import { useEffect, useState } from "react";

import { getHealth } from "@/lib/api";

type Status = "checking" | "ok" | "unreachable";

const LABELS: Record<Status, string> = {
  checking: "Checking the backend…",
  ok: "Backend is up",
  unreachable: "Backend is unreachable",
};

const DOT_COLORS: Record<Status, string> = {
  checking: "bg-zinc-400",
  ok: "bg-emerald-500",
  unreachable: "bg-red-500",
};

export function HealthStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal)
      .then(() => setStatus("ok"))
      .catch(() => {
        if (!controller.signal.aborted) setStatus("unreachable");
      });
    return () => controller.abort();
  }, []);

  return (
    <p role="status" className="flex items-center gap-2 text-sm">
      <span aria-hidden className={`size-2.5 rounded-full ${DOT_COLORS[status]}`} />
      {LABELS[status]}
    </p>
  );
}
