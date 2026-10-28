"use client";

import { cn } from "cn";

import { useLanguage } from "@/lib/language";
import { useMessages } from "@/lib/messages";

// dkwebsite.de's legal notice and privacy policy cover this site too (#457), so the postal address
// stays out of this repo. Its German pages sit under /de.
const LEGAL_SITE = "https://dkwebsite.de";

/** "Legal notice · Privacy", linking dkwebsite.de's pages in the reader's language. */
export function LegalLinks({ className }: { className?: string }) {
  const t = useMessages();
  const [language] = useLanguage();
  const base = language === "de" ? `${LEGAL_SITE}/de` : LEGAL_SITE;
  return (
    <p className={cn("text-xs text-ink-3", className)}>
      <LegalLink href={`${base}/imprint`}>{t.legal.notice}</LegalLink> ·{" "}
      <LegalLink href={`${base}/privacy`}>{t.legal.privacy}</LegalLink>
    </p>
  );
}

function LegalLink({ href, children }: { href: string; children: string }) {
  return (
    <a href={href} className="underline-offset-4 hover:text-foreground hover:underline">
      {children}
    </a>
  );
}
