/** The search parameter on the home page that carries a question to ask the chat. */
export const QUESTION_PARAM = "q";

/** A link to the home page that asks the chat the given question. */
export function chatLink(question: string): string {
  return `/?${QUESTION_PARAM}=${encodeURIComponent(question)}`;
}
