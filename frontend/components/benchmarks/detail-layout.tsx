"use client";

import { cn } from "cn";
import { X } from "lucide-react";
import { type ReactNode, type Ref, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogTitle } from "@/components/ui/dialog";
import { SheetContent } from "@/components/ui/sheet";
import { useMediaQuery } from "@/lib/use-media-query";

export const MUTED = "text-ink-2";

/** A decision record on GitHub, where each benchmark's full write-up lives. */
export function decisionUrl(file: string): string {
  return `https://github.com/DannyKuk/molecula/blob/main/docs/decisions/${file}`;
}

export type DetailPanel<View> = {
  view: View;
  /** Shows `next` in the detail panel, or in the sheet on a phone. */
  show: (next: View) => void;
  /** Whether the panel sits beside the content; else the detail opens in a bottom sheet. */
  wide: boolean;
  sheetOpen: boolean;
  setSheetOpen: (open: boolean) => void;
};

/** What a benchmark's detail panel shows, and whether its sheet is open on a phone. */
export function useDetailPanel<View>(initial: () => View): DetailPanel<View> {
  const [view, setView] = useState<View>(initial);
  const [sheetOpen, setSheetOpen] = useState(false);
  const wide = useMediaQuery("(min-width: 1024px)");

  function show(next: View) {
    setView(next);
    if (!wide) setSheetOpen(true);
  }

  return { view, show, wide, sheetOpen, setSheetOpen };
}

type DetailLayoutProps<View> = {
  panel: DetailPanel<View>;
  /** The detail for `panel.view`. */
  detail: ReactNode;
  /** The sheet's title on a phone. */
  title: ReactNode;
  /** Buttons that step through the views, above the detail and in the sheet's header. Their row
   * keeps its place while a view has none (`false`); leave them out for no row at all. */
  steps?: ReactNode;
  ref?: Ref<HTMLDivElement>;
  className?: string;
  children: ReactNode;
};

/** The benchmark's content with the detail panel sticking beside it, or in a bottom sheet on a
 * phone. The panel starts at the top for every new view. */
export function DetailLayout<View>({
  panel,
  detail,
  title,
  steps,
  ref,
  className,
  children,
}: DetailLayoutProps<View>) {
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (panelRef.current) panelRef.current.scrollTop = 0;
  }, [panel.view]);

  return (
    <>
      <div
        ref={ref}
        className={cn("grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_420px]", className)}
      >
        <div className="flex min-w-0 flex-col gap-3">{children}</div>
        <aside
          ref={panelRef}
          aria-label="Details"
          className="sticky top-4 hidden max-h-[calc(100vh-2rem)] overflow-auto border-l border-rule-2 pl-5 lg:block"
        >
          {steps !== undefined && <div className="mb-2 flex justify-end">{steps}</div>}
          {detail}
        </aside>
      </div>

      <Dialog open={panel.sheetOpen && !panel.wide} onOpenChange={panel.setSheetOpen}>
        <SheetContent side="bottom" className="bg-background">
          <header className="flex items-center gap-2 border-b px-4 py-2.5">
            <DialogClose render={<Button variant="outline" size="icon-sm" aria-label="Close" />}>
              <X />
            </DialogClose>
            <DialogTitle className="min-w-0 flex-1 truncate text-sm font-semibold">
              {title}
            </DialogTitle>
            {steps}
          </header>
          <div className="flex-1 overflow-auto p-4">{detail}</div>
        </SheetContent>
      </Dialog>
    </>
  );
}
