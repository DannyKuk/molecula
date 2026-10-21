import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Brand } from "./brand-mark";

describe("Brand", () => {
  it("reads as the name alone, because the mark beside it is hidden from screen readers", () => {
    const { container } = render(<Brand />);
    expect(screen.queryByRole("img")).toBeNull();
    expect(container.textContent).toBe("Molecula");
  });
});
