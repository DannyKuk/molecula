import { cn } from "cn";

/**
 * Molecula's mark: a six-atom ring with one atom in signal orange. The ring takes the text colour,
 * so it follows light and dark. With a `label` it is an image of its own (the rail shows it alone);
 * without one it is hidden from screen readers, because the name beside it says the same.
 */
export function BrandMark({ label, className }: { label?: string; className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      {...(label ? { role: "img", "aria-label": label } : { "aria-hidden": true })}
      className={cn("size-[1.3em] shrink-0", className)}
    >
      <polygon
        points="16,4.5 26,10.25 26,21.75 16,27.5 6,21.75 6,10.25"
        fill="none"
        stroke="currentColor"
        strokeWidth={2.6}
        strokeLinejoin="round"
      />
      <circle cx="26" cy="10.25" r="4.2" className="fill-signal" />
    </svg>
  );
}

/** The mark and the name. It takes the font size of where it sits. */
export function Brand({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-[0.45em] font-semibold tracking-tight", className)}>
      <BrandMark />
      Molecula
    </span>
  );
}
