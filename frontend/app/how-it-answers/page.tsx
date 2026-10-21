import type { Metadata } from "next";

import { HowItAnswers } from "@/components/answer-flow/how-it-answers";

export const metadata: Metadata = {
  title: "How it answers · Molecula",
  description:
    "How Molecula gets from a question to a checked answer, step by step, with who does each step.",
};

export default function HowItAnswersPage() {
  return <HowItAnswers />;
}
