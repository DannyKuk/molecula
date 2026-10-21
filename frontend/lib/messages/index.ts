import { type Language, useLanguage } from "../language";

import { de } from "./de";
import { en, type Messages } from "./en";

export { en, type Messages };

const MESSAGES: Record<Language, Messages> = { en, de };

export function messagesFor(language: Language): Messages {
  return MESSAGES[language];
}

/** The interface text in the language the reader picked, or their browser's. */
export function useMessages(): Messages {
  const [language] = useLanguage();
  return MESSAGES[language];
}
