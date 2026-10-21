import { useSyncExternalStore } from "react";

import type { ChecksChoice } from "./api";

export const MODEL_KEY = "molecula:model";
export const CHECKS_KEY = "molecula:checks";

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

/**
 * Whether the checks around a picked model's answer run on the tested models or on the picked
 * model itself (#363), kept like the model. With the default model it changes nothing.
 */
export function useChosenChecks(): [ChecksChoice, (checks: ChecksChoice) => void] {
  const chosen = useSyncExternalStore(subscribe, chosenChecks, () => "tested" as const);
  return [chosen, chooseChecks];
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

/** The checks choice, read when a question is sent. */
export function chosenChecks(): ChecksChoice {
  return stored(CHECKS_KEY) === "picked" ? "picked" : "tested";
}

export function chooseChecks(checks: ChecksChoice) {
  store(CHECKS_KEY, checks === "picked" ? checks : null);
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
