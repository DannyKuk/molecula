"use client";

import { useMessages } from "@/lib/messages";

const DAILYMED_URL = "https://dailymed.nlm.nih.gov/";

/** The reminder that answers come from an AI and where to check them, shown on every page. */
export function Disclaimer() {
  const t = useMessages();
  return (
    <p className="text-sm text-ink-2">
      {t.disclaimer.before}{" "}
      <a
        href={DAILYMED_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium underline underline-offset-4"
      >
        {t.disclaimer.link}
      </a>{" "}
      {t.disclaimer.after}
    </p>
  );
}
