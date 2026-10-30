import type { Metadata } from "next";

import { LandingPage } from "@/components/landing/landing-page";
import { LANDING_URL } from "@/lib/site";

const DESCRIPTION =
  "Ask how a medicine works: Molecula answers from FDA drug labels, cites every passage it used, and shows the drug bound to its target protein in 3D.";

// Search engines see the page at `/`, where a signed-out visitor gets it, so `/about` points
// there instead of counting as a second copy (#463).
export const metadata: Metadata = {
  title: "Molecula · a medicines chatbot that shows drugs binding in 3D",
  description: DESCRIPTION,
  alternates: { canonical: "/" },
};

/** What the page is, for search engines: https://schema.org/WebApplication */
const STRUCTURED_DATA = {
  "@context": "https://schema.org",
  "@type": "WebApplication",
  name: "Molecula",
  url: LANDING_URL,
  description: DESCRIPTION,
  applicationCategory: "EducationalApplication",
  operatingSystem: "Web",
  author: { "@type": "Person", name: "Danny Kukic", url: "https://dkwebsite.de" },
};

/** The landing page, which `/` shows a visitor who isn't signed in (`proxy.ts`). */
export default function AboutPage() {
  return (
    <>
      <script
        type="application/ld+json"
        // `<` is escaped so no text in it can close the script tag.
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(STRUCTURED_DATA).replace(/</g, "\\u003c"),
        }}
      />
      <LandingPage />
    </>
  );
}
