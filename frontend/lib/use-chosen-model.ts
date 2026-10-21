import { useSyncExternalStore } from "react";

export const MODEL_KEY = "molecula:model";

const listeners = new Set<() => void>();
let unsaved: string | null = null;

/**
 * The model the user picked in the settings to write the answers, by name, kept in `localStorage`
 * for every chat in this browser; null for the backend's default. A browser that refuses storage
 * keeps the choice until the page closes.
 */
export function useChosenModel(): [string | null, (name: string | null) => void] {
  const chosen = useSyncExternalStore(subscribe, chosenModel, () => null);
  return [chosen, chooseModel];
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

/** The picked model's name, read when a question is sent; null for the default. */
export function chosenModel(): string | null {
  try {
    return localStorage.getItem(MODEL_KEY);
  } catch {
    return unsaved;
  }
}

export function chooseModel(name: string | null) {
  try {
    if (name === null) localStorage.removeItem(MODEL_KEY);
    else localStorage.setItem(MODEL_KEY, name);
  } catch {
    unsaved = name;
  }
  listeners.forEach((notify) => notify());
}
