import { createStoredValue } from "./stored-value";
import { SYSTEM_DARK, THEME_KEY } from "./theme-script";
import { useMediaQuery } from "./use-media-query";

export type Theme = "system" | "light" | "dark";

export const THEMES: Theme[] = ["system", "light", "dark"];

const pickedTheme = createStoredValue<Theme>(THEME_KEY, {
  parse: (picked) => (picked === "light" || picked === "dark" ? picked : "system"),
  serialize: (theme) => (theme === "system" ? null : theme),
  server: "system",
});

/** The theme picked with the switch, kept in `localStorage` across reloads; "system" by default. */
export function useTheme(): [Theme, (theme: Theme) => void] {
  return pickedTheme.useValue();
}

/** The picked theme as stored now, read outside rendering. */
export const readTheme = pickedTheme.read;

/** The theme the screen shows: the picked one, or the system's while "system" is picked. */
export function shownTheme(theme: Theme, systemDark: boolean): "light" | "dark" {
  if (theme !== "system") return theme;
  return systemDark ? "dark" : "light";
}

export function useShownTheme(): "light" | "dark" {
  const [theme] = useTheme();
  return shownTheme(theme, useMediaQuery(SYSTEM_DARK));
}
