import type { Metadata } from "next";

import { LandingPage } from "@/components/landing/landing-page";

export const metadata: Metadata = {
  title: "Molecula · a medicines chatbot that shows drugs binding in 3D",
};

/** The landing page, which `/` shows a visitor who isn't signed in (`proxy.ts`). */
export default function AboutPage() {
  return <LandingPage />;
}
