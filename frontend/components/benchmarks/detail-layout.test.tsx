import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DetailLayout, useDetailPanel } from "./detail-layout";

afterEach(() => vi.unstubAllGlobals());

function screenWidth(wide: boolean) {
  vi.stubGlobal("matchMedia", () => ({
    matches: wide,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

function Drugs({ steps }: { steps?: boolean }) {
  const panel = useDetailPanel(() => "imatinib");
  return (
    <DetailLayout
      panel={panel}
      detail={<p>About {panel.view}</p>}
      title={panel.view}
      steps={steps === undefined ? undefined : steps && <button type="button">Next</button>}
    >
      <button type="button" onClick={() => panel.show("aspirin")}>
        Aspirin
      </button>
    </DetailLayout>
  );
}

describe("DetailLayout", () => {
  it("shows the picked view in the panel beside the content on a wide screen", () => {
    screenWidth(true);
    render(<Drugs />);

    fireEvent.click(screen.getByRole("button", { name: "Aspirin" }));

    expect(screen.getByRole("complementary", { name: "Details" }).textContent).toBe(
      "About aspirin",
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("opens the picked view in a sheet titled for it on a phone", async () => {
    screenWidth(false);
    render(<Drugs />);

    fireEvent.click(screen.getByRole("button", { name: "Aspirin" }));

    const sheet = await screen.findByRole("dialog", { name: "aspirin" });
    expect(sheet.textContent).toContain("About aspirin");
  });

  it("keeps the steps' row while a view has none, and leaves it out when there are no steps", () => {
    screenWidth(true);
    const { rerender } = render(<Drugs steps={false} />);
    const details = () => screen.getByRole("complementary", { name: "Details" });

    expect(details().children).toHaveLength(2);
    rerender(<Drugs />);
    expect(details().children).toHaveLength(1);
  });
});
