import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useFetched } from "./use-fetched";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("useFetched", () => {
  it("is loading until the call settles, then loaded with its value", async () => {
    const call = deferred<string[]>();
    const { result } = renderHook(() => useFetched(() => call.promise, []));

    expect(result.current).toEqual({ kind: "loading" });
    await act(async () => call.resolve(["imatinib"]));

    expect(result.current).toEqual({ kind: "loaded", value: ["imatinib"] });
  });

  it("is failed when the call fails", async () => {
    const { result } = renderHook(() =>
      useFetched(() => Promise.reject(new TypeError("Failed to fetch")), []),
    );

    await act(async () => {});

    expect(result.current).toEqual({ kind: "failed" });
  });

  it("aborts the call when the component closes and ignores how it ends", async () => {
    const call = deferred<string>();
    const load = vi.fn((signal: AbortSignal) => {
      signal.addEventListener("abort", () => call.reject(new DOMException("", "AbortError")));
      return call.promise;
    });
    const { result, unmount } = renderHook(() => useFetched(load, []));
    const signal = load.mock.calls[0][0];

    unmount();
    await act(async () => {});

    expect(signal.aborted).toBe(true);
    expect(result.current).toEqual({ kind: "loading" });
  });

  it("calls again when its deps change, loading meanwhile, and drops the older call", async () => {
    const calls = new Map([
      ["aspirin", deferred<string>()],
      ["ibuprofen", deferred<string>()],
    ]);
    const signals: AbortSignal[] = [];
    const { result, rerender } = renderHook(
      ({ name }) =>
        useFetched(
          (signal) => {
            signals.push(signal);
            return calls.get(name)!.promise;
          },
          [name],
        ),
      { initialProps: { name: "aspirin" } },
    );

    rerender({ name: "ibuprofen" });
    expect(signals[0].aborted).toBe(true);
    await act(async () => calls.get("aspirin")!.resolve("old"));
    expect(result.current).toEqual({ kind: "loading" });

    await act(async () => calls.get("ibuprofen")!.resolve("new"));
    expect(result.current).toEqual({ kind: "loaded", value: "new" });
  });
});
