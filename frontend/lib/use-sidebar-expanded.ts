import { createStoredValue } from "./stored-value";

export const SIDEBAR_KEY = "molecula:sidebar";

const sidebarExpanded = createStoredValue<boolean>(SIDEBAR_KEY, {
  parse: (stored) => stored === "expanded",
  serialize: (expanded) => (expanded ? "expanded" : "collapsed"),
  server: false,
});

/**
 * Whether the chat list is expanded, kept in `localStorage` across reloads. It starts collapsed,
 * also on the server, and a browser that refuses storage keeps the setting until the page closes.
 */
export function useSidebarExpanded(): [boolean, (expanded: boolean) => void] {
  return sidebarExpanded.useValue();
}
