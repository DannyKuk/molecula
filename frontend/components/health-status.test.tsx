import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiError, getHealth } from "@/lib/api";

import { HealthStatus } from "./health-status";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getHealth: vi.fn(),
}));

describe("HealthStatus", () => {
  it("shows that it is checking until the backend answers", () => {
    vi.mocked(getHealth).mockReturnValue(new Promise(() => {}));

    render(<HealthStatus />);

    expect(screen.getByRole("status").textContent).toBe("Checking the backend…");
  });

  it("shows that the backend is up when /health answers", async () => {
    vi.mocked(getHealth).mockResolvedValue({ status: "ok" });

    render(<HealthStatus />);

    expect(await screen.findByText("Backend is up")).toBeDefined();
  });

  it("shows that the backend is unreachable when /health fails", async () => {
    vi.mocked(getHealth).mockRejectedValue(new ApiError("/health", 503));

    render(<HealthStatus />);

    expect(await screen.findByText("Backend is unreachable")).toBeDefined();
  });
});
