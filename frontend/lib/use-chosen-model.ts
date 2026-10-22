import type { CheckerId } from "./api";
import { createStoredValue } from "./stored-value";

export const MODEL_KEY = "molecula:model";
export const CHECKER_KEY = "molecula:checker";

const CHECKERS: CheckerId[] = ["decision", "local", "answer"];

const pickedModel = createStoredValue<string | null>(MODEL_KEY, {
  parse: (name) => name,
  serialize: (name) => name,
  server: null,
});

const pickedChecker = createStoredValue<CheckerId | null>(CHECKER_KEY, {
  parse: (checker) => CHECKERS.find((id) => id === checker) ?? null,
  serialize: (checker) => checker,
  server: null,
});

/**
 * The model the user picked in the settings to write the answers, by name, kept in `localStorage`
 * for every chat in this browser; null for the backend's default. A browser that refuses storage
 * keeps the choice until the page closes.
 */
export function useChosenModel(): [string | null, (name: string | null) => void] {
  return pickedModel.useValue();
}

/** The model the user picked to check the messages (#363), kept like the model; null for the
 * backend's default checker. */
export function useChosenChecker(): [CheckerId | null, (checker: CheckerId | null) => void] {
  return pickedChecker.useValue();
}

/** The picked model's name, read when a question is sent; null for the default. */
export function chosenModel(): string | null {
  return pickedModel.read();
}

export function chooseModel(name: string | null) {
  pickedModel.write(name);
}

/** The picked checker, read when a question is sent; null for the default. */
export function chosenChecker(): CheckerId | null {
  return pickedChecker.read();
}

export function chooseChecker(checker: CheckerId | null) {
  pickedChecker.write(checker);
}
