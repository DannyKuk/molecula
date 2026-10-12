import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Disclaimer } from "./disclaimer";

afterEach(cleanup);

describe("Disclaimer", () => {
  it("says that answers come from an AI and are not medical advice", () => {
    const { container } = render(<Disclaimer />);

    expect(container.textContent).toBe(
      "Molecula is an AI assistant and can make mistakes. It is not medical advice. " +
        "Check the official label on DailyMed and ask a pharmacist or doctor before acting on " +
        "anything here.",
    );
  });

  it("links to DailyMed in a new tab without giving it access to this page", () => {
    render(<Disclaimer />);

    const link = screen.getByRole("link", { name: "DailyMed" });
    expect(link.getAttribute("href")).toBe("https://dailymed.nlm.nih.gov/");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
  });
});
