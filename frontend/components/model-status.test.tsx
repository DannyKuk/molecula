import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getModels } from "@/lib/api";
import { chooseModel } from "@/lib/use-chosen-model";

import { modelLabel, ModelStatus } from "./model-status";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getModels: vi.fn(),
}));

beforeEach(() => {
  chooseModel(null);
  vi.mocked(getModels).mockResolvedValue({
    models: [
      { name: "openai/gpt-oss-20b", local: true },
      { name: "openai/gpt-6-luna", local: false },
    ],
    default: "openai/gpt-oss-20b",
    checkers: [{ id: "local", name: "openai/gpt-oss-20b", local: true }],
    default_checker: "local",
  });
});

describe("modelLabel", () => {
  it("names a local model without its provider and says it runs locally", () => {
    expect(modelLabel({ name: "openai/gpt-oss-20b", local: true })).toBe("gpt-oss-20b · local");
  });

  it("names a cloud model alone", () => {
    expect(modelLabel({ name: "openai/gpt-6-luna", local: false })).toBe("gpt-6-luna");
  });
});

describe("ModelStatus", () => {
  it("shows the default model once the backend names it", async () => {
    render(<ModelStatus />);

    expect(await screen.findByText("gpt-oss-20b · local")).toBeDefined();
  });

  it("shows the model the user picked", async () => {
    chooseModel("openai/gpt-6-luna");

    render(<ModelStatus />);

    expect(await screen.findByText("gpt-6-luna")).toBeDefined();
  });

  it("shows nothing while the chat is off", async () => {
    vi.mocked(getModels).mockRejectedValue(new Error("503"));

    const { container } = render(<ModelStatus />);

    await vi.waitFor(() => expect(getModels).toHaveBeenCalled());
    expect(container.textContent).toBe("");
  });
});
