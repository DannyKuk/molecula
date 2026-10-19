import { describe, expect, it } from "vitest";

import { CHAT_PARAM, QUESTION_PARAM, chatLink, savedChatLink } from "./chat-link";

describe("chatLink", () => {
  it("puts the encoded question into the home page's query string", () => {
    expect(chatLink("How does imatinib work?")).toBe("/?q=How%20does%20imatinib%20work%3F");
  });

  it("round-trips through URLSearchParams", () => {
    const question = "What is 5-FU & how does it work?";
    const params = new URL(chatLink(question), "http://localhost").searchParams;

    expect(params.get(QUESTION_PARAM)).toBe(question);
  });
});

describe("savedChatLink", () => {
  it("names the saved chat in the home page's query string", () => {
    const params = new URL(savedChatLink("c 1"), "http://localhost").searchParams;

    expect(params.get(CHAT_PARAM)).toBe("c 1");
  });
});
