"use client";

import { Dialog as DialogPrimitive } from "@base-ui/react/dialog";
import { cn } from "cn";

import { DialogOverlay, DialogPortal } from "@/components/ui/dialog";

const SIDES = {
  left: "inset-y-0 left-0 w-75 max-w-[85%] data-open:slide-in-from-left data-closed:slide-out-to-left",
  right:
    "inset-y-0 right-0 w-105 max-w-full data-open:slide-in-from-right data-closed:slide-out-to-right",
  bottom: "inset-0 data-open:slide-in-from-bottom data-closed:slide-out-to-bottom",
};

/** A dialog that slides in from an edge: from the left as a drawer, from the right as a side
 * sheet beside the page, from the bottom as a full-screen sheet on a phone. */
function SheetContent({
  className,
  side = "left",
  ...props
}: DialogPrimitive.Popup.Props & { side?: keyof typeof SIDES }) {
  return (
    <DialogPortal>
      {/* The side sheet keeps the page beside it readable. */}
      <DialogOverlay
        className={cn(
          side === "right" && "bg-transparent supports-backdrop-filter:backdrop-blur-none",
        )}
      />
      <DialogPrimitive.Popup
        data-slot="sheet-content"
        className={cn(
          "fixed z-50 flex flex-col bg-popover text-sm text-popover-foreground shadow-lg ring-1 ring-foreground/10 outline-none duration-200 data-open:animate-in data-closed:animate-out",
          SIDES[side],
          className,
        )}
        {...props}
      />
    </DialogPortal>
  );
}

export { SheetContent };
