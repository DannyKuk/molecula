"use client";

import { cn } from "cn";
import { useEffect } from "react";

import { type Language, useLanguage } from "@/lib/language";
import { useMessages } from "@/lib/messages";

const LANGUAGES: Language[] = ["en", "de"];

/** "EN | DE": switches the interface language; the answers follow the language of the question. */
export function LanguageSwitch({ className }: { className?: string }) {
  const [language, setLanguage] = useLanguage();
  const t = useMessages();
  return (
    <div
      role="group"
      aria-label={t.language.switch}
      className={cn(
        "inline-flex rounded-full border border-rule-2 p-0.5 font-mono text-[11px]",
        className,
      )}
    >
      {LANGUAGES.map((option) => (
        <button
          key={option}
          type="button"
          lang={option}
          aria-label={t.language[option]}
          aria-pressed={option === language}
          onClick={() => setLanguage(option)}
          className={cn(
            "rounded-full px-2 py-0.5 uppercase focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3",
            option === language ? "bg-ink text-page" : "text-ink-2 hover:text-ink",
          )}
        >
          {option}
        </button>
      ))}
    </div>
  );
}

/** Keeps `<html lang>` on the interface language, for screen readers and hyphenation. */
export function DocumentLanguage() {
  const [language] = useLanguage();
  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);
  return null;
}
