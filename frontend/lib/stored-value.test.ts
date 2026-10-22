import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createStoredValue } from "./stored-value";
import { LANGUAGE_KEY, useLanguage } from "./language";
import {
  CHECKER_KEY,
  chooseChecker,
  chooseModel,
  chosenChecker,
  chosenModel,
  MODEL_KEY,
} from "./use-chosen-model";
import { SIDEBAR_KEY, useSidebarExpanded } from "./use-sidebar-expanded";

function storedSize(key: string) {
  return createStoredValue<"small" | "large">(key, {
    parse: (stored) => (stored === "large" ? "large" : "small"),
    serialize: (size) => size,
    server: "small",
  });
}

function blockStorage() {
  const refuse = () => {
    throw new DOMException("The storage is off.", "SecurityError");
  };
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(refuse);
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(refuse);
  vi.spyOn(Storage.prototype, "removeItem").mockImplementation(refuse);
}

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("createStoredValue", () => {
  it("reads what is stored under its key and stores what is written", () => {
    localStorage.setItem("test:size", "large");
    const size = storedSize("test:size");

    expect(size.read()).toBe("large");
    size.write("small");
    expect(localStorage.getItem("test:size")).toBe("small");
  });

  it("parses nothing stored into the default", () => {
    expect(storedSize("test:empty").read()).toBe("small");
  });

  it("removes the key when the value serializes to null", () => {
    localStorage.setItem(MODEL_KEY, "openai/gpt-oss-20b");

    chooseModel(null);

    expect(localStorage.getItem(MODEL_KEY)).toBeNull();
    expect(chosenModel()).toBeNull();
  });

  it("updates every component that shows it when it is written", () => {
    const size = storedSize("test:shared");
    const first = renderHook(() => size.useValue());
    const second = renderHook(() => size.useValue());

    act(() => first.result.current[1]("large"));

    expect(second.result.current[0]).toBe("large");
  });

  it("keeps the value until the page closes when the browser refuses storage", () => {
    blockStorage();
    const size = storedSize("test:blocked");
    const { result } = renderHook(() => size.useValue());

    expect(result.current[0]).toBe("small");
    act(() => result.current[1]("large"));

    expect(result.current[0]).toBe("large");
    expect(size.read()).toBe("large");
  });

  it("forgets a value cleared while the browser refuses storage", () => {
    blockStorage();
    chooseChecker("local");

    expect(chosenChecker()).toBe("local");

    chooseChecker(null);
    expect(chosenChecker()).toBeNull();
  });
});

describe("the stored settings", () => {
  it("keep the formats saved before the shared helper", () => {
    const sidebar = renderHook(() => useSidebarExpanded());
    const language = renderHook(() => useLanguage());

    act(() => sidebar.result.current[1](true));
    act(() => language.result.current[1]("de"));
    act(() => chooseModel("openai/gpt-oss-20b"));
    act(() => chooseChecker("decision"));

    expect(localStorage.getItem(SIDEBAR_KEY)).toBe("expanded");
    expect(localStorage.getItem(LANGUAGE_KEY)).toBe("de");
    expect(localStorage.getItem(MODEL_KEY)).toBe("openai/gpt-oss-20b");
    expect(localStorage.getItem(CHECKER_KEY)).toBe("decision");

    act(() => sidebar.result.current[1](false));
    expect(localStorage.getItem(SIDEBAR_KEY)).toBe("collapsed");
  });
});
