import { fireEvent, render, screen, within } from "@testing-library/react";
import { useRouter } from "next/navigation";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getDrugs } from "@/lib/api";
import { memoryHistory } from "@/lib/test-fixtures";

import { DrugsPage } from "./drug-picker";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getDrugs: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: vi.fn(), usePathname: () => "/drugs" }));

const push = vi.fn();

beforeEach(() => {
  push.mockReset();
  localStorage.clear();
  vi.mocked(useRouter).mockReturnValue({ push } as unknown as ReturnType<typeof useRouter>);
  vi.mocked(getDrugs).mockResolvedValue([
    { cid: 5291, name: "imatinib", aliases: ["Gleevec"], has_3d: true },
  ]);
});

describe("DrugsPage", () => {
  it("opens the chat with the question about the clicked drug", async () => {
    render(<DrugsPage history={memoryHistory().history} />);
    fireEvent.click(await screen.findByRole("button", { name: "imatinib" }));

    expect(push).toHaveBeenCalledExactlyOnceWith("/?q=How%20does%20imatinib%20work%3F");
  });

  it("marks Supported drugs as the current page in the sidebar", async () => {
    render(<DrugsPage history={memoryHistory().history} />);

    const current = await screen.findByRole("link", { name: "Supported drugs" });
    expect(current.getAttribute("aria-current")).toBe("page");
  });

  it("asks a question from the help in the chat", async () => {
    render(<DrugsPage history={memoryHistory().history} />);

    fireEvent.click(screen.getByRole("button", { name: "How to use" }));
    const help = screen.getByRole("dialog", { name: "How to use Molecula" });
    fireEvent.click(within(help).getByRole("button", { name: "What does sildenafil bind to?" }));

    expect(push).toHaveBeenCalledExactlyOnceWith("/?q=What%20does%20sildenafil%20bind%20to%3F");
  });
});
