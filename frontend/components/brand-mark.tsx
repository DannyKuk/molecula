import { cn } from "cn";

/**
 * Molecula's mark: a six-atom ring with one atom in signal orange. The ring takes the text colour,
 * so it follows light and dark. It is hidden from screen readers: the name beside it, or the label
 * of the button it sits in, says what it is.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 32 32" className={cn("size-[1.3em] shrink-0", className)}>
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

/** The mark and the name. Both take the font size of where they sit. */
export function Brand({
  className,
  markClassName,
}: {
  className?: string;
  markClassName?: string;
}) {
  return (
    <span className={cn("flex items-center gap-[0.45em] font-semibold tracking-tight", className)}>
      <BrandMark className={markClassName} />
      Molecula
    </span>
  );
}
