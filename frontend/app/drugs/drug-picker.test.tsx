import { fireEvent, render, screen } from "@testing-library/react";
import { useRouter } from "next/navigation";
import { describe, expect, it, vi } from "vitest";

import { getDrugs } from "@/lib/api";

import { DrugPicker } from "./drug-picker";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getDrugs: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: vi.fn() }));

describe("DrugPicker", () => {
  it("opens the chat with the question about the clicked drug", async () => {
    const push = vi.fn();
    vi.mocked(useRouter).mockReturnValue({ push } as unknown as ReturnType<typeof useRouter>);
    vi.mocked(getDrugs).mockResolvedValue([
      { cid: 5291, name: "imatinib", aliases: ["Gleevec"], has_3d: true },
    ]);

    render(<DrugPicker />);
    fireEvent.click(await screen.findByRole("button", { name: "imatinib" }));

    expect(push).toHaveBeenCalledExactlyOnceWith("/?q=How%20does%20imatinib%20work%3F");
  });
});
