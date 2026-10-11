import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, getDrugs } from "@/lib/api";

import { SupportedDrugsLoader } from "./supported-drugs-loader";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getDrugs: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("SupportedDrugsLoader", () => {
  it("shows that it is loading until the backend answers", () => {
    vi.mocked(getDrugs).mockReturnValue(new Promise(() => {}));

    render(<SupportedDrugsLoader onAsk={vi.fn()} />);

    expect(screen.getByRole("status").textContent).toBe("Loading the supported drugs…");
  });

  it("shows the searchable list once /drugs answers", async () => {
    vi.mocked(getDrugs).mockResolvedValue([
      { cid: 5291, name: "imatinib", aliases: ["Gleevec"], has_3d: true },
    ]);

    render(<SupportedDrugsLoader onAsk={vi.fn()} />);

    expect(await screen.findByRole("button", { name: "imatinib" })).toBeDefined();
    expect(screen.getByRole("searchbox")).toBeDefined();
  });

  it("shows a readable error when /drugs fails", async () => {
    vi.mocked(getDrugs).mockRejectedValue(new ApiError("/drugs", 503));

    render(<SupportedDrugsLoader onAsk={vi.fn()} />);

    expect((await screen.findByRole("alert")).textContent).toContain(
      "Could not load the supported drugs.",
    );
  });

  it("shows the same error when the backend cannot be reached at all", async () => {
    vi.mocked(getDrugs).mockRejectedValue(new TypeError("Failed to fetch"));

    render(<SupportedDrugsLoader onAsk={vi.fn()} />);

    expect(await screen.findByRole("alert")).toBeDefined();
  });
});
