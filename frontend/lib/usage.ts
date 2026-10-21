import type { Turn } from "./chat-turn";
import { en, type Messages } from "./messages/en";

/**
 * What an answer's model calls used: tokens and cost in US dollars (`Usage` in
 * `backend/src/molecula/schemas/usage.py`). Null means a call didn't report it, so the sum isn't
 * known; a local model costs 0.
 */
export type Usage = {
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  cost_usd: number | null;
};

/** The usage of every answered turn added up; null when no turn has one. Turns saved before
 * usage was sent, and answers that stopped or failed, have none and count for nothing. */
export function conversationUsage(turns: Turn[]): Usage | null {
  const used = turns.flatMap((turn) => (turn.usage ? [turn.usage] : []));
  if (used.length === 0) return null;
  return used.reduce((total, usage) => ({
    input_tokens: sum(total.input_tokens, usage.input_tokens),
    output_tokens: sum(total.output_tokens, usage.output_tokens),
    total_tokens: sum(total.total_tokens, usage.total_tokens),
    cost_usd: sum(total.cost_usd, usage.cost_usd),
  }));
}

function sum(left: number | null, right: number | null): number | null {
  return left === null || right === null ? null : left + right;
}

/** Tokens and cost as one line, such as "4,210 tokens · $0.0031". */
export function formatUsage(usage: Usage, t: Messages = en): string {
  const tokens =
    usage.total_tokens === null
      ? t.usage.tokensUnknown
      : t.usage.tokens(usage.total_tokens.toLocaleString(t.locale));
  const cost = usage.cost_usd === null ? t.usage.costUnknown : costFormat(t).format(usage.cost_usd);
  return `${tokens} · ${cost}`;
}

function costFormat(t: Messages): Intl.NumberFormat {
  return new Intl.NumberFormat(t.locale, {
    style: "currency",
    currency: "USD",
    maximumSignificantDigits: 2,
  });
}
