import { useSyncExternalStore } from "react";

type StoredValueOptions<T> = {
  /** The value for the stored text, or for null when nothing is stored. */
  parse: (stored: string | null) => T;
  /** The text to store for a value, or null to remove the key. */
  serialize: (value: T) => string | null;
  /** The value the server renders, before the browser's storage can be read. */
  server: T;
};

export type StoredValue<T> = {
  useValue: () => [T, (value: T) => void];
  read: () => T;
  write: (value: T) => void;
};

/**
 * A setting kept in `localStorage` under `key` and shared by every component that shows it. A browser
 * that refuses storage keeps the setting until the page closes. `T` should be a primitive:
 * `useSyncExternalStore` compares each read with the last one.
 */
export function createStoredValue<T>(
  key: string,
  { parse, serialize, server }: StoredValueOptions<T>,
): StoredValue<T> {
  const listeners = new Set<() => void>();
  let unsaved: string | null = null;

  function subscribe(onChange: () => void) {
    listeners.add(onChange);
    return () => listeners.delete(onChange);
  }

  function read(): T {
    try {
      return parse(localStorage.getItem(key));
    } catch {
      return parse(unsaved);
    }
  }

  function write(value: T) {
    const text = serialize(value);
    try {
      if (text === null) localStorage.removeItem(key);
      else localStorage.setItem(key, text);
    } catch {
      unsaved = text;
    }
    listeners.forEach((notify) => notify());
  }

  function useValue(): [T, (value: T) => void] {
    return [useSyncExternalStore(subscribe, read, () => server), write];
  }

  return { useValue, read, write };
}
