import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getModels, type ModelChoices } from "@/lib/api";
import { chooseModel, chosenModel } from "@/lib/use-chosen-model";

import { ModelPicker, ModelSettings } from "./model-settings";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getModels: vi.fn(),
}));

const CHOICES: ModelChoices = {
  models: [
    { name: "openai/gpt-oss-20b", local: true },
    { name: "google/gemma-4-31b", local: true },
    { name: "anthropic/claude-haiku-5.5", local: false },
  ],
  default: "openai/gpt-oss-20b",
};

beforeEach(() => {
  chooseModel(null);
  vi.mocked(getModels).mockResolvedValue(CHOICES);
});

function option(name: string): HTMLInputElement {
  return screen.getByRole("radio", { name: new RegExp(`^${name}`) });
}

describe("ModelSettings", () => {
  it("opens from its button and lists the models, the default marked as tested", async () => {
    render(<ModelSettings trigger={<button type="button" />}>Settings</ModelSettings>);

    fireEvent.click(screen.getByRole("button", { name: "Settings" }));

    expect(await screen.findByRole("radio", { name: /^gpt-oss-20b/ })).toBeDefined();
    expect(
      screen.getAllByRole("radio").map((radio) => radio.closest("label")?.textContent),
    ).toEqual(["gpt-oss-20blocal · default, tested", "gemma-4-31blocal", "claude-haiku-5.5cloud"]);
  });
});

describe("ModelPicker", () => {
  it("checks the default until the user picks another model", async () => {
    render(<ModelPicker />);

    expect(
      (await screen.findByRole("radio", { name: /^gpt-oss-20b/ })) as HTMLInputElement,
    ).toHaveProperty("checked", true);
    expect(chosenModel()).toBeNull();
  });

  it("keeps the picked model for the next question and says the default is the tested one", async () => {
    render(<ModelPicker />);
    await screen.findByRole("radio", { name: /^gpt-oss-20b/ });

    fireEvent.click(option("claude-haiku-5.5"));

    expect(chosenModel()).toBe("anthropic/claude-haiku-5.5");
    expect(option("claude-haiku-5.5").checked).toBe(true);
    expect(screen.getByText(/developed and tested with gpt-oss-20b/)).toBeDefined();
  });

  it("warns that a local model loads first and must fit next to the default", async () => {
    render(<ModelPicker />);
    await screen.findByRole("radio", { name: /^gpt-oss-20b/ });

    fireEvent.click(option("gemma-4-31b"));

    expect(screen.getByText(/loads on the local server when it is first asked/)).toBeDefined();
  });

  it("forgets the choice when the user goes back to the default", async () => {
    chooseModel("google/gemma-4-31b");
    render(<ModelPicker />);
    await screen.findByRole("radio", { name: /^gpt-oss-20b/ });

    fireEvent.click(option("gpt-oss-20b"));

    expect(chosenModel()).toBeNull();
  });

  it("drops a picked model the backend no longer lists and falls back to the default", async () => {
    chooseModel("qwen/qwen3.8-27b");
    render(<ModelPicker />);

    expect(
      (await screen.findByRole("radio", { name: /^gpt-oss-20b/ })) as HTMLInputElement,
    ).toHaveProperty("checked", true);
    expect(chosenModel()).toBeNull();
  });

  it("says there is nothing to pick while the chat is off", async () => {
    vi.mocked(getModels).mockRejectedValue(new Error("503"));

    render(<ModelPicker />);

    expect(await screen.findByText(/The chat is off/)).toBeDefined();
  });
});
