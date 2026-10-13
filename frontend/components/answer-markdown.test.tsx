import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnswerMarkdown } from "./answer-markdown";

describe("AnswerMarkdown", () => {
  it("renders bold text", () => {
    const { container } = render(<AnswerMarkdown text="Imatinib is a **kinase inhibitor**." />);

    expect(container.querySelector("strong")?.textContent).toBe("kinase inhibitor");
    expect(container.textContent).toBe("Imatinib is a kinase inhibitor.");
  });

  it("renders a list in either style the models write", () => {
    render(<AnswerMarkdown text={"Common side effects:\n\n* nausea\n* edema\n- rash"} />);

    const items = screen.getAllByRole("listitem").map((item) => item.textContent);
    expect(items).toEqual(["nausea", "edema", "rash"]);
  });

  it("renders a table with its header and cells", () => {
    const text = [
      "| Drug | Target |",
      "|------|--------|",
      "| imatinib | ABL1 |",
      "| gefitinib | EGFR |",
    ].join("\n");
    render(<AnswerMarkdown text={text} />);

    const table = screen.getByRole("table");
    const headers = within(table)
      .getAllByRole("columnheader")
      .map((cell) => cell.textContent);
    const cells = within(table)
      .getAllByRole("cell")
      .map((cell) => cell.textContent);
    expect(headers).toEqual(["Drug", "Target"]);
    expect(cells).toEqual(["imatinib", "ABL1", "gefitinib", "EGFR"]);
  });

  it("shows raw HTML as text instead of rendering it", () => {
    const text =
      'Label text: <img src=x onerror="alert(1)"> and <b>bold</b>\n\n<script>alert(2)</script>';
    const { container } = render(<AnswerMarkdown text={text} />);

    expect(container.querySelector("img, b, script")).toBeNull();
    expect(container.textContent).toContain('<img src=x onerror="alert(1)">');
    expect(container.textContent).toContain("<b>bold</b>");
    expect(container.textContent).toContain("<script>alert(2)</script>");
  });

  it("keeps citations as written, in both bracket styles", () => {
    const { container } = render(
      <AnswerMarkdown text="Imatinib blocks BCR-ABL [1][2], also [3, 4] and 【5】." />,
    );

    expect(container.textContent).toBe("Imatinib blocks BCR-ABL [1][2], also [3, 4] and 【5】.");
    expect(container.querySelector("a")).toBeNull();
  });

  it("opens links in a new tab without giving them access to this page", () => {
    render(
      <AnswerMarkdown text="See [DailyMed](https://dailymed.nlm.nih.gov/dailymed/) for the label." />,
    );

    const link = screen.getByRole("link", { name: "DailyMed" });
    expect(link.getAttribute("href")).toBe("https://dailymed.nlm.nih.gov/dailymed/");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("drops a javascript: link target", () => {
    const { container } = render(<AnswerMarkdown text="[click](javascript:alert(1))" />);

    expect(container.querySelector("a")?.getAttribute("href")).toBeFalsy();
  });

  it("shows a half-streamed bold marker as written until it closes", () => {
    const { container, rerender } = render(<AnswerMarkdown text="Imatinib is a **kinase" />);

    expect(container.textContent).toBe("Imatinib is a **kinase");
    expect(container.querySelector("strong")).toBeNull();

    rerender(<AnswerMarkdown text="Imatinib is a **kinase inhibitor**" />);

    expect(container.querySelector("strong")?.textContent).toBe("kinase inhibitor");
  });
});
