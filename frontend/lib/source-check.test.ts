import { describe, expect, it } from "vitest";

import type { CheckedClaim } from "./chat";
import { applyEvent, startTurn, stopTurn } from "./chat-turn";
import { de } from "./messages/de";
import {
  CHECKING_ANSWER,
  checkingAnswer,
  checkSummary,
  sourceCheckMarks,
  unbackedReason,
} from "./source-check";

function claim(
  text: string,
  label: CheckedClaim["label"],
  reason = "",
  held_by: number[] = [],
): CheckedClaim {
  return { text, refs: [], label, decided_by: "model", reason, held_by };
}

function marked(answer: string, claims: CheckedClaim[]): string[] {
  return sourceCheckMarks(answer, claims).unbacked.map(({ start, end }) =>
    answer.slice(start, end),
  );
}

/** The answer with each found chip written in as `{refs}`. */
function withFound(answer: string, claims: CheckedClaim[]): string {
  return sourceCheckMarks(answer, claims)
    .found.toReversed()
    .reduce(
      (text, { at, refs }) => `${text.slice(0, at)}{${refs.join(",")}}${text.slice(at)}`,
      answer,
    );
}

describe("sourceCheckMarks", () => {
  it("finds the sentence the sources don't back and nothing else", () => {
    const answer =
      "A 40 mg dose was like diazepam 20 mg [2]. The 40 mg dose is above the usual maximum. " +
      "Molecula's data don't compare them further.";
    const claims = [
      claim("A 40 mg dose was like diazepam 20 mg [2].", "supported"),
      claim("The 40 mg dose is above the usual maximum.", "unsupported"),
      claim("Molecula's data don't compare them further.", "not_a_claim"),
    ];

    expect(marked(answer, claims)).toEqual(["The 40 mg dose is above the usual maximum."]);
  });

  it("finds a sentence the splitter joined across a line break", () => {
    const answer = "It can cause low sodium\n  and hepatic coma [1].";

    expect(
      marked(answer, [claim("It can cause low sodium and hepatic coma [1].", "unsupported")]),
    ).toEqual(["It can cause low sodium\n  and hepatic coma [1]."]);
  });

  it("marks each item of an unbacked list but not the heading the splitter put in front", () => {
    const answer = "**Naproxen**  \n- **Uses** – pain【6】.  \n- **Side effects** – ulcers【8】.";
    const claims = [
      claim("**Naproxen**\n- **Uses** – pain【6】.", "supported"),
      claim("**Naproxen**\n- **Side effects** – ulcers【8】.", "unsupported"),
    ];

    expect(marked(answer, claims)).toEqual(["**Side effects** – ulcers【8】."]);
  });

  it("marks the later of two equal sentences when the earlier one is backed", () => {
    const answer = "It is an NSAID [1]. It is an NSAID.";
    const claims = [
      claim("It is an NSAID [1].", "supported"),
      claim("It is an NSAID.", "unsupported"),
    ];

    expect(sourceCheckMarks(answer, claims).unbacked).toEqual([{ start: 20, end: 35, claim: 1 }]);
  });

  it("skips a claim it can't find instead of marking the wrong text", () => {
    expect(
      sourceCheckMarks("Something else entirely.", [claim("Not here.", "unsupported")]),
    ).toEqual({ unbacked: [], found: [] });
  });
});

describe("found citations", () => {
  it("go before the closing punctuation of a claim another result holds", () => {
    const answer = "It is an NSAID [1]. It reduces fever. Ask a doctor.";
    const claims = [
      claim("It is an NSAID [1].", "held_elsewhere", "", [2]),
      claim("It reduces fever.", "held_elsewhere", "", [2, 3]),
      claim("Ask a doctor.", "not_a_claim"),
    ];

    expect(withFound(answer, claims)).toBe(
      "It is an NSAID [1]{2}. It reduces fever{2,3}. Ask a doctor.",
    );
    expect(marked(answer, claims)).toEqual([]);
  });

  it("go after the last item of a list claim", () => {
    const answer = "**Uses**\n- pain [1]\n- fever";

    expect(
      withFound(answer, [claim("**Uses**\n- pain [1]\n- fever", "held_elsewhere", "", [4])]),
    ).toBe("**Uses**\n- pain [1]\n- fever{4}");
  });
});

describe("checkSummary", () => {
  it("says every fact is backed when the check passed", () => {
    expect(
      checkSummary({
        checked: true,
        claims: [claim("a", "supported"), claim("b", "supported"), claim("c", "not_a_claim")],
      }),
    ).toEqual({
      kind: "backed",
      title: "Checked against the sources",
      detail: "Every fact is backed by the source it cites.",
    });
  });

  it("counts the facts and the sentences the sources don't back", () => {
    expect(
      checkSummary({
        checked: true,
        claims: [claim("a", "supported"), claim("b", "unsupported"), claim("c", "not_a_claim")],
      }),
    ).toEqual({
      kind: "unbacked",
      title: "Checked against the sources",
      detail: "1 of 2 facts backed · 1 sentence isn't in Molecula's sources (underlined).",
    });
    expect(
      checkSummary({
        checked: true,
        claims: [claim("a", "unsupported"), claim("b", "unsupported")],
      })?.detail,
    ).toBe("0 of 2 facts backed · 2 sentences aren't in Molecula's sources (underlined).");
  });

  it("says every fact is in Molecula's sources when some were found in an uncited result", () => {
    expect(
      checkSummary({
        checked: true,
        claims: [claim("a", "supported"), claim("b", "held_elsewhere", "", [2])],
      })?.detail,
    ).toBe("Every fact is in Molecula's sources.");
  });

  it("says the answer wasn't checked when the check failed", () => {
    expect(checkSummary({ checked: false, claims: [] })).toEqual({
      kind: "unchecked",
      title: "Not checked against the sources",
    });
  });

  it("says nothing about an answer that states no facts", () => {
    expect(
      checkSummary({ checked: true, claims: [claim("Ask your doctor.", "not_a_claim")] }),
    ).toBeNull();
    expect(checkSummary({ checked: true, claims: [] })).toBeNull();
  });
});

describe("checkSummary in German", () => {
  it("counts the facts and the sentences the sources don't back", () => {
    expect(
      checkSummary(
        { checked: true, claims: [claim("a", "supported"), claim("b", "unsupported")] },
        de,
      ),
    ).toEqual({
      kind: "unbacked",
      title: "Anhand der Quellen geprüft",
      detail: "1 von 2 Fakten belegt · 1 Satz steht nicht in Moleculas Quellen (unterstrichen).",
    });
    expect(checkSummary({ checked: false, claims: [] }, de)?.title).toBe(
      "Nicht anhand der Quellen geprüft",
    );
  });

  it("says why a claim has no reason of the check's own", () => {
    expect(unbackedReason({ ...claim("a", "unsupported"), decided_by: "no_verdict" }, de)).toBe(
      "Die Prüfung hat dazu kein Urteil abgegeben.",
    );
  });
});

describe("checkingAnswer", () => {
  const streamed = applyEvent(startTurn("Q"), { type: "token", text: "It blocks BCR-ABL." });
  const checking = applyEvent(streamed, { type: "status", message: CHECKING_ANSWER });

  it("is true from the guard's status until the verdict arrives", () => {
    expect(checkingAnswer(streamed)).toBe(false);
    expect(checkingAnswer(checking)).toBe(true);
    expect(
      checkingAnswer(applyEvent(checking, { type: "source_check", checked: false, claims: [] })),
    ).toBe(false);
  });

  it("is false once the answer was stopped", () => {
    expect(checkingAnswer(stopTurn(checking))).toBe(false);
  });
});

describe("unbackedReason", () => {
  it("gives the check's reason, or says why there is none", () => {
    expect(unbackedReason(claim("a", "unsupported", "No source cited."))).toBe("No source cited.");
    expect(unbackedReason({ ...claim("a", "unsupported"), decided_by: "unknown_refs" })).toBe(
      "It cites a source Molecula didn't look up.",
    );
    expect(unbackedReason({ ...claim("a", "unsupported"), decided_by: "no_verdict" })).toBe(
      "The check gave no verdict on it.",
    );
  });
});
