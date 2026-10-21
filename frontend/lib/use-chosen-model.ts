import { useSyncExternalStore } from "react";

import type { CheckerId } from "./api";

export const MODEL_KEY = "molecula:model";
export const CHECKER_KEY = "molecula:checker";

const CHECKERS: CheckerId[] = ["decision", "local", "answer"];

const listeners = new Set<() => void>();
const unsaved = new Map<string, string>();

/**
 * The model the user picked in the settings to write the answers, by name, kept in `localStorage`
 * for every chat in this browser; null for the backend's default. A browser that refuses storage
 * keeps the choice until the page closes.
 */
export function useChosenModel(): [string | null, (name: string | null) => void] {
  const chosen = useSyncExternalStore(subscribe, chosenModel, () => null);
  return [chosen, chooseModel];
}

/** The model the user picked to check the messages (#363), kept like the model; null for the
 * backend's default checker. */
export function useChosenChecker(): [CheckerId | null, (checker: CheckerId | null) => void] {
  const chosen = useSyncExternalStore(subscribe, chosenChecker, () => null);
  return [chosen, chooseChecker];
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

/** The picked model's name, read when a question is sent; null for the default. */
export function chosenModel(): string | null {
  return stored(MODEL_KEY);
}

export function chooseModel(name: string | null) {
  store(MODEL_KEY, name);
}

/** The picked checker, read when a question is sent; null for the default. */
export function chosenChecker(): CheckerId | null {
  const checker = stored(CHECKER_KEY);
  return CHECKERS.find((id) => id === checker) ?? null;
}

export function chooseChecker(checker: CheckerId | null) {
  store(CHECKER_KEY, checker);
}

function stored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return unsaved.get(key) ?? null;
  }
}

function store(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    if (value === null) unsaved.delete(key);
    else unsaved.set(key, value);
  }
  listeners.forEach((notify) => notify());
}
