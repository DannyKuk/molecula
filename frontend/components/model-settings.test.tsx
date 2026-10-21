import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getModels, type ModelChoices } from "@/lib/api";
import { chooseChecker, chooseModel, chosenChecker, chosenModel } from "@/lib/use-chosen-model";

import { ModelPicker, ModelSettings } from "./model-settings";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getModels: vi.fn(),
}));

const OFFLINE: ModelChoices = {
  models: [
    { name: "openai/gpt-oss-20b", local: true },
    { name: "google/gemma-4-31b", local: true },
    { name: "anthropic/claude-haiku-5.5", local: false },
  ],
  default: "openai/gpt-oss-20b",
  checkers: [{ id: "local", name: "openai/gpt-oss-20b", local: true }],
  default_checker: "local",
};

const ONLINE: ModelChoices = {
  models: [
    { name: "openai/gpt-6-luna", local: false },
    { name: "openai/gpt-oss-20b", local: true },
    { name: "google/gemma-4-31b", local: true },
  ],
  default: "openai/gpt-6-luna",
  checkers: [
    { id: "decision", name: "jev-1.13", local: false },
    { id: "local", name: "openai/gpt-oss-20b", local: true },
  ],
  default_checker: "decision",
};

beforeEach(() => {
  chooseModel(null);
  chooseChecker(null);
  vi.mocked(getModels).mockResolvedValue(OFFLINE);
});

function group(name: string) {
  return within(screen.getByRole("group", { name }));
}

function model(name: string): HTMLInputElement {
  return group("Model that writes the answers").getByRole("radio", {
    name: new RegExp(`^${name}`),
  });
}

function checker(name: string): HTMLInputElement {
  return group("Model that checks the message").getByRole("radio", {
    name: new RegExp(`^${name}`),
  });
}

function labels(name: string): (string | null | undefined)[] {
  return group(name)
    .getAllByRole("radio")
    .map((radio) => radio.closest("label")?.textContent);
}

async function loaded() {
  await screen.findByRole("group", { name: "Model that writes the answers" });
}

describe("ModelSettings", () => {
  it("opens from its button and lists the checkers, then the models, tested and default marked", async () => {
    render(<ModelSettings trigger={<button type="button" />}>Settings</ModelSettings>);

    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    await loaded();

    expect(labels("Model that checks the message")).toEqual([
      "gpt-oss-20blocal · tested · default",
      "The model that writes the answer",
    ]);
    expect(labels("Model that writes the answers")).toEqual([
      "gpt-oss-20blocal · tested · default",
      "gemma-4-31blocal",
      "claude-haiku-5.5cloud",
    ]);
  });
});

describe("ModelPicker", () => {
  it("offers Jev online as the default checker, gpt-6-luna as the default model", async () => {
    vi.mocked(getModels).mockResolvedValue(ONLINE);

    render(<ModelPicker />);
    await loaded();

    expect(labels("Model that checks the message")).toEqual([
      "jev-1.13cloud · tested · default",
      "gpt-oss-20blocal · tested",
      "The model that writes the answer",
    ]);
    expect(checker("jev-1.13").checked).toBe(true);
    expect(model("gpt-6-luna").closest("label")?.textContent).toBe(
      "gpt-6-lunacloud · tested · default",
    );
  });

  it("checks the defaults until the user picks others", async () => {
    render(<ModelPicker />);
    await loaded();

    expect(model("gpt-oss-20b").checked).toBe(true);
    expect(checker("gpt-oss-20b").checked).toBe(true);
    expect(chosenModel()).toBeNull();
    expect(chosenChecker()).toBeNull();
  });

  it("keeps the picked model for the next question and names the tested models", async () => {
    render(<ModelPicker />);
    await loaded();

    fireEvent.click(model("claude-haiku-5.5"));

    expect(chosenModel()).toBe("anthropic/claude-haiku-5.5");
    expect(model("claude-haiku-5.5").checked).toBe(true);
    expect(screen.getByText(/developed with gpt-oss-20b.*gpt-6-luna was measured/)).toBeDefined();
  });

  it("keeps the picked checker and forgets it when the user goes back to the default", async () => {
    vi.mocked(getModels).mockResolvedValue(ONLINE);
    render(<ModelPicker />);
    await loaded();

    fireEvent.click(checker("gpt-oss-20b"));
    expect(chosenChecker()).toBe("local");
    expect(checker("gpt-oss-20b").checked).toBe(true);

    fireEvent.click(checker("jev-1.13"));
    expect(chosenChecker()).toBeNull();
  });

  it("says the checks are unmeasured when an untested model checks its own answer", async () => {
    chooseModel("google/gemma-4-31b");
    render(<ModelPicker />);
    await loaded();

    expect(screen.getByText(/stay on the models they were tested with/)).toBeDefined();

    fireEvent.click(checker("The model that writes the answer"));

    expect(chosenChecker()).toBe("answer");
    expect(screen.getByText(/gemma-4-31b then also checks the message/).textContent).toMatch(
      /measured only on gpt-oss-20b and Jev/,
    );
  });

  it("doesn't call the checks unmeasured when gpt-oss checks its own answer", async () => {
    chooseChecker("answer");
    render(<ModelPicker />);
    await loaded();

    expect(screen.getByText(/stay on the models they were tested with/)).toBeDefined();
  });

  it("warns that a local model loads first and must fit next to the default", async () => {
    render(<ModelPicker />);
    await loaded();

    fireEvent.click(model("gemma-4-31b"));

    expect(
      screen.getByText(/loads on the local server when it is first asked/).textContent,
    ).toMatch(/fit in memory next to gpt-oss-20b/);
  });

  it("forgets the model when the user goes back to the default", async () => {
    chooseModel("google/gemma-4-31b");
    render(<ModelPicker />);
    await loaded();

    fireEvent.click(model("gpt-oss-20b"));

    expect(chosenModel()).toBeNull();
  });

  it("drops a model or checker the backend no longer offers and falls back to the defaults", async () => {
    chooseModel("qwen/qwen3.8-27b");
    chooseChecker("decision");
    render(<ModelPicker />);
    await loaded();

    expect(model("gpt-oss-20b").checked).toBe(true);
    expect(checker("gpt-oss-20b").checked).toBe(true);
    expect(chosenModel()).toBeNull();
    expect(chosenChecker()).toBeNull();
  });

  it("says there is nothing to pick while the chat is off", async () => {
    vi.mocked(getModels).mockRejectedValue(new Error("503"));

    render(<ModelPicker />);

    expect(await screen.findByText(/The chat is off/)).toBeDefined();
  });
});
