import { useSyncExternalStore } from "react";

/** Whether a CSS media query such as `(prefers-color-scheme: dark)` matches, updated live. False
 * on the server. */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}
