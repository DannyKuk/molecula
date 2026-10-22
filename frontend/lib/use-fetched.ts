import { type DependencyList, useEffect, useState } from "react";

export type Fetched<T> = { kind: "loading" } | { kind: "failed" } | { kind: "loaded"; value: T };

const LOADING = { kind: "loading" } as const;

/**
 * Calls `load` when the component opens and again whenever `deps` change, aborting the call
 * before; loading until it settles, then loaded or failed. An aborted call changes nothing.
 */
export function useFetched<T>(
  load: (signal: AbortSignal) => Promise<T>,
  deps: DependencyList,
): Fetched<T> {
  const [settled, setSettled] = useState<{ deps: DependencyList; fetched: Fetched<T> } | null>(
    null,
  );

  useEffect(() => {
    const controller = new AbortController();
    const settle = (fetched: Fetched<T>) => {
      if (!controller.signal.aborted) setSettled({ deps, fetched });
    };
    load(controller.signal).then(
      (value) => settle({ kind: "loaded", value }),
      () => settle({ kind: "failed" }),
    );
    return () => controller.abort();
    // `deps` are what `load` reads, as for useEffect itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  // A result for other deps is the last call's; the current one is still loading.
  return settled && sameDeps(settled.deps, deps) ? settled.fetched : LOADING;
}

function sameDeps(a: DependencyList, b: DependencyList): boolean {
  return a.length === b.length && a.every((dep, i) => Object.is(dep, b[i]));
}
