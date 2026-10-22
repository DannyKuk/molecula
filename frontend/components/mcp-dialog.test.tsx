import { readFileSync } from "node:fs";
import path from "node:path";

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  CHECKOUT_PLACEHOLDER,
  CLAUDE_DESKTOP_CONFIG,
  McpGuide,
  START_COMMANDS,
  TOOLS,
} from "./mcp-dialog";

// A Windows checkout may have CRLF line endings.
const setupPath = path.join(__dirname, "../../docs/setup.md");
const doc = readFileSync(setupPath, "utf8").replace(/\r\n/g, "\n");

function stubClipboard(writeText: (text: string) => Promise<void>) {
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
}

afterEach(() => {
  Reflect.deleteProperty(navigator, "clipboard");
});

describe("McpGuide", () => {
  it("shows the setup doc's config, commands and tools", () => {
    expect(doc).toContain(CLAUDE_DESKTOP_CONFIG);
    for (const { command } of START_COMMANDS) {
      expect(doc).toContain(command);
    }
    expect(doc).toContain("http://localhost:8001/mcp");
    for (const { name } of TOOLS) {
      expect(doc).toContain(`\`${name}\``);
    }
  });

  it("lists the six tools, marks the path to replace and says the server is local only", () => {
    const { container } = render(<McpGuide />);
    const text = container.textContent ?? "";

    expect(TOOLS).toHaveLength(6);
    for (const { name } of TOOLS) {
      expect(screen.getByText(name)).toBeDefined();
    }
    const marked = Array.from(container.querySelectorAll("mark"), (mark) => mark.textContent);
    expect(marked).toEqual([CHECKOUT_PLACEHOLDER, CHECKOUT_PLACEHOLDER]);
    expect(text).toContain("answers only requests addressed to localhost");
  });

  it("copies the Claude Desktop config with one click", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    stubClipboard(writeText);
    render(<McpGuide />);

    fireEvent.click(screen.getByRole("button", { name: "Copy config" }));

    expect(await screen.findByRole("button", { name: "Copied" })).toBeTruthy();
    expect(writeText).toHaveBeenCalledWith(CLAUDE_DESKTOP_CONFIG);
  });

  it("copies each start command", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    stubClipboard(writeText);
    render(<McpGuide />);

    fireEvent.click(screen.getByRole("button", { name: "Copy the Streamable HTTP command" }));

    await screen.findByRole("button", { name: "Copied" });
    expect(writeText).toHaveBeenCalledWith(
      "uv run python -m molecula.mcp --transport streamable-http",
    );
  });

  it("says when the copy failed", async () => {
    stubClipboard(() => Promise.reject(new Error("denied")));
    render(<McpGuide />);

    fireEvent.click(screen.getByRole("button", { name: "Copy config" }));

    expect(await screen.findByRole("button", { name: "Copy failed" })).toBeTruthy();
  });
});
