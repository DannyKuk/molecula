import { describe, expect, it } from "vitest";

import { didYouMeanOf, withName } from "./did-you-mean";
import { de } from "./messages/de";
import {
  COMPARISON_WITH_UNSUPPORTED,
  IBUPROFEN_PROPERTIES,
  IMATINIB_LABELS,
  TYLENOLL_NOT_SUPPORTED,
} from "./test-tool-results";
import type { Step } from "./tool-cards";

const NOVAMINSUFLON = {
  status: "not_supported",
  query: "Novaminsuflon",
  suggestions: [{ alias: "Novaminsulfon", cid: 3111, name: "metamizole" }],
};

function step(name: string, result?: unknown): Step {
  return { text: `Running ${name}`, tool: { id: name, name, args: {}, result } };
}

describe("withName", () => {
  it("replaces the name in any case, every time it occurs", () => {
    expect(
      withName(
        "Can you compare it to Novaminsuflon? Also show me novaminsuflon as a 3d model",
        "Novaminsuflon",
        "Novaminsulfon",
      ),
    ).toBe("Can you compare it to Novaminsulfon? Also show me Novaminsulfon as a 3d model");
  });

  it("replaces only the whole name, never part of a longer word", () => {
    expect(withName("Is para the same as paracetamol?", "para", "paracetamol")).toBe(
      "Is paracetamol the same as paracetamol?",
    );
  });

  it("asks about the suggested name on its own when the question spells the name differently", () => {
    expect(withName("Show me novaminsulfn in 3D", "Novaminsuflon", "Novaminsulfon")).toBe(
      "What is Novaminsulfon?",
    );
  });

  it("asks that in German for a German reader", () => {
    expect(withName("Zeig mir Sertralinn", "Sertralin", "Sertraline", de.turn.whatIs)).toBe(
      "Was ist Sertraline?",
    );
  });

  it("takes characters with a meaning in patterns literally", () => {
    expect(withName("What does L-thyroxin+ do?", "L-thyroxin+", "L-thyroxine")).toBe(
      "What does L-thyroxine do?",
    );
    expect(withName("What does Lxthyroxin do?", "L.thyroxin", "L-thyroxine")).toBe(
      "What is L-thyroxine?",
    );
  });
});

describe("didYouMeanOf", () => {
  it("offers each suggestion with the question asked again", () => {
    expect(
      didYouMeanOf("How does Tylenoll work?", [step("resolve_drug", TYLENOLL_NOT_SUPPORTED)]),
    ).toEqual([
      {
        suggestion: { alias: "Tylenol", cid: 1983, name: "acetaminophen" },
        question: "How does Tylenol work?",
      },
    ]);
  });

  it("finds names a comparison or a label search didn't find", () => {
    const comparison = {
      ...COMPARISON_WITH_UNSUPPORTED,
      drugs: [...COMPARISON_WITH_UNSUPPORTED.drugs, NOVAMINSUFLON],
    };
    const labels = { ...IMATINIB_LABELS, unsupported: [TYLENOLL_NOT_SUPPORTED] };

    const offers = didYouMeanOf("Compare Novaminsuflon and Tylenoll", [
      step("compare_drugs", comparison),
      step("search_labels", labels),
    ]);

    expect(offers.map((offer) => offer.question)).toEqual([
      "Compare Novaminsulfon and Tylenoll",
      "Compare Novaminsuflon and Tylenol",
    ]);
  });

  it("offers a suggestion once when several tools missed the same name", () => {
    const offers = didYouMeanOf("Show Novaminsuflon in 3D", [
      step("resolve_drug", NOVAMINSUFLON),
      step("get_complex", { ...NOVAMINSUFLON, query: "novaminsuflon" }),
    ]);

    expect(offers).toHaveLength(1);
  });

  it("offers nothing when every name was found, a name had no suggestion, or a tool is still running", () => {
    expect(
      didYouMeanOf("Ibuprofen and Vicodinx", [
        step("get_properties", IBUPROFEN_PROPERTIES),
        step("compare_drugs", COMPARISON_WITH_UNSUPPORTED),
        step("resolve_drug"),
      ]),
    ).toEqual([]);
  });
});
