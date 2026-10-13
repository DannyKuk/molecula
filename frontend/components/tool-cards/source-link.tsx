import type { ReactNode } from "react";

/** A link to the page a result comes from, opened in a new tab. */
export function SourceLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium underline underline-offset-4"
    >
      {children}
    </a>
  );
}
