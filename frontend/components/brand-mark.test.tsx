import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Brand, BrandMark } from "./brand-mark";

describe("BrandMark", () => {
  it("is an image named by its label when it stands alone", () => {
    render(<BrandMark label="Molecula" />);
    expect(screen.getByRole("img", { name: "Molecula" })).toBeDefined();
  });

  it("is hidden from screen readers next to the name, which says the same", () => {
    const { container } = render(<Brand />);
    expect(screen.queryByRole("img")).toBeNull();
    expect(container.textContent).toBe("Molecula");
  });
});
