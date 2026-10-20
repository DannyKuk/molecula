import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { getChatModel } from "@/lib/api";

import { modelLabel, ModelStatus } from "./model-status";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getChatModel: vi.fn(),
}));

describe("modelLabel", () => {
  it("names a local model without its provider and says it runs locally", () => {
    expect(modelLabel({ name: "openai/gpt-oss-20b", local: true })).toBe("gpt-oss-20b · local");
  });

  it("names a cloud model alone", () => {
    expect(modelLabel({ name: "openai/gpt-6-luna", local: false })).toBe("gpt-6-luna");
  });
});

describe("ModelStatus", () => {
  it("shows the model once the backend names it", async () => {
    vi.mocked(getChatModel).mockResolvedValue({ name: "openai/gpt-oss-20b", local: true });

    render(<ModelStatus />);

    expect(await screen.findByText("gpt-oss-20b · local")).toBeDefined();
  });

  it("shows nothing while the chat is off", async () => {
    vi.mocked(getChatModel).mockRejectedValue(new Error("503"));

    const { container } = render(<ModelStatus />);

    await vi.waitFor(() => expect(getChatModel).toHaveBeenCalled());
    expect(container.textContent).toBe("");
  });
});
