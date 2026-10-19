"use client";

import { Dialog as DialogPrimitive } from "@base-ui/react/dialog";
import { cn } from "cn";

import { DialogOverlay, DialogPortal } from "@/components/ui/dialog";

const SIDES = {
  left: "inset-y-0 left-0 w-75 max-w-[85%] data-open:slide-in-from-left data-closed:slide-out-to-left",
  bottom: "inset-0 data-open:slide-in-from-bottom data-closed:slide-out-to-bottom",
};

/** A dialog that slides in from an edge: from the left as a drawer, from the bottom as a
 * full-screen sheet on a phone. */
function SheetContent({
  className,
  side = "left",
  ...props
}: DialogPrimitive.Popup.Props & { side?: keyof typeof SIDES }) {
  return (
    <DialogPortal>
      <DialogOverlay />
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
