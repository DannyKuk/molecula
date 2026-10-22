"use client";

import { cn } from "cn";
import { Monitor, Moon, Sun } from "lucide-react";
import { useEffect } from "react";

import { useMessages } from "@/lib/messages";
import { readTheme, shownTheme, THEMES, type Theme, useTheme } from "@/lib/theme";
import { SYSTEM_DARK } from "@/lib/theme-script";

export const THEME_ICONS: Record<Theme, typeof Sun> = { system: Monitor, light: Sun, dark: Moon };

/** System, light or dark: the colours of the screen. Print stays dark on white whatever is picked. */
export function ThemeSwitch({ className }: { className?: string }) {
  const [theme, setTheme] = useTheme();
  const t = useMessages();
  return (
    <div
      role="group"
      aria-label={t.theme.switch}
      className={cn("inline-flex rounded-full border border-rule-2 p-0.5", className)}
    >
      {THEMES.map((option) => {
        const Icon = THEME_ICONS[option];
        return (
          <button
            key={option}
            type="button"
            aria-label={t.theme[option]}
            title={t.theme[option]}
            aria-pressed={option === theme}
            onClick={() => setTheme(option)}
            className={cn(
              "rounded-full px-1.5 py-0.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3",
              option === theme ? "bg-ink text-page" : "text-ink-2 hover:text-ink",
            )}
          >
            <Icon aria-hidden className="size-3.5" />
          </button>
        );
      })}
    </div>
  );
}

/**
 * Keeps `<html data-theme>` on the shown theme after the inline script in the layout set it first.
 * It reads the stored theme itself because while hydrating, `useTheme` still gives the server's
 * "system", which would flash the system's theme over a picked one.
 */
export function DocumentTheme() {
  const [theme] = useTheme();
  useEffect(() => {
    const system = window.matchMedia(SYSTEM_DARK);
    const apply = () => {
      document.documentElement.dataset.theme = shownTheme(readTheme(), system.matches);
    };
    apply();
    system.addEventListener("change", apply);
    return () => system.removeEventListener("change", apply);
  }, [theme]);
  return null;
}
