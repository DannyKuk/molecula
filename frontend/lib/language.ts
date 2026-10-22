import { createStoredValue } from "./stored-value";

export type Language = "en" | "de";

export const LANGUAGE_KEY = "molecula:language";

/** German for a browser set to any kind of German, English for every other language. */
export function browserLanguage(language: string | undefined): Language {
  return language?.toLowerCase().startsWith("de") ? "de" : "en";
}

const pickedLanguage = createStoredValue<Language>(LANGUAGE_KEY, {
  parse: (picked) =>
    picked === "en" || picked === "de" ? picked : browserLanguage(navigator.language),
  serialize: (language) => language,
  server: "en",
});

/**
 * The interface language: the one picked with the switch, kept in `localStorage` across reloads,
 * or else the browser's. The server renders English. A browser that refuses storage keeps the
 * choice until the page closes.
 */
export function useLanguage(): [Language, (language: Language) => void] {
  return pickedLanguage.useValue();
}
