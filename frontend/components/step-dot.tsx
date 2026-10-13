/** The dot before a progress step; it pulses on the step Molecula is working on. */
export function StepDot({ current }: { current: boolean }) {
  return (
    <span
      aria-hidden
      className={`size-1.5 shrink-0 rounded-full ${current ? "animate-pulse bg-sky-500" : "bg-zinc-400"}`}
    />
  );
}
