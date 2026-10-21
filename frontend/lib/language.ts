import { useSyncExternalStore } from "react";

export type Language = "en" | "de";

export const LANGUAGE_KEY = "molecula:language";

const listeners = new Set<() => void>();
let unsaved: Language | null = null;

/** German for a browser set to any kind of German, English for every other language. */
export function browserLanguage(language: string | undefined): Language {
  return language?.toLowerCase().startsWith("de") ? "de" : "en";
}

/**
 * The interface language: the one picked with the switch, kept in `localStorage` across reloads,
 * or else the browser's. The server renders English. A browser that refuses storage keeps the
 * choice until the page closes.
 */
export function useLanguage(): [Language, (language: Language) => void] {
  const language = useSyncExternalStore(subscribe, readLanguage, () => "en" as const);
  return [language, writeLanguage];
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

function readLanguage(): Language {
  const picked = pickedLanguage();
  return picked === "en" || picked === "de" ? picked : browserLanguage(navigator.language);
}

function pickedLanguage(): string | null {
  try {
    return localStorage.getItem(LANGUAGE_KEY);
  } catch {
    return unsaved;
  }
}

function writeLanguage(language: Language) {
  try {
    localStorage.setItem(LANGUAGE_KEY, language);
  } catch {
    unsaved = language;
  }
  listeners.forEach((notify) => notify());
}
