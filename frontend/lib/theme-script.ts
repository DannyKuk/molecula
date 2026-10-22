// Kept apart from `theme.ts`, whose hooks a server component such as the root layout can't import.

export const THEME_KEY = "molecula:theme";

export const SYSTEM_DARK = "(prefers-color-scheme: dark)";

/**
 * Sets `<html data-theme>` before the first paint, run inline from the root layout. The server
 * can't know the picked theme, and React only sets it after hydration, so without this a reader who
 * picked dark would see the light page flash on every load.
 */
export const THEME_SCRIPT = `(() => {
  let picked = null;
  try {
    picked = localStorage.getItem(${JSON.stringify(THEME_KEY)});
  } catch {}
  const dark = picked === "dark" || (picked !== "light" && matchMedia(${JSON.stringify(SYSTEM_DARK)}).matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
})();`;
