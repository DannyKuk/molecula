import type { ReactNode } from "react";

export type TipAt = { x: number; y: number };

/** A tooltip that follows the pointer, flipped away from the window's right and bottom edges. */
export function FloatingTip({ at, children }: { at: TipAt; children: ReactNode }) {
  const { innerWidth, innerHeight } = window;
  return (
    <div
      role="status"
      style={{
        ...(at.x > innerWidth - 340 ? { right: innerWidth - at.x + 14 } : { left: at.x + 14 }),
        ...(at.y > innerHeight - 160 ? { bottom: innerHeight - at.y + 14 } : { top: at.y + 14 }),
      }}
      className="pointer-events-none fixed z-50 max-w-[min(320px,calc(100vw-16px))] rounded-lg border bg-popover px-2.5 py-2 text-xs/[1.1rem] text-popover-foreground shadow-lg"
    >
      {children}
    </div>
  );
}
