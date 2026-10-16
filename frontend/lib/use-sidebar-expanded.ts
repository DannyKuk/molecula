import { useSyncExternalStore } from "react";

export const SIDEBAR_KEY = "molecula:sidebar";

const listeners = new Set<() => void>();
let unsaved = false;

/**
 * Whether the chat list is expanded, kept in `localStorage` across reloads. It starts collapsed,
 * also on the server, and a browser that refuses storage keeps the setting until the page closes.
 */
export function useSidebarExpanded(): [boolean, (expanded: boolean) => void] {
  const expanded = useSyncExternalStore(subscribe, readExpanded, () => false);
  return [expanded, writeExpanded];
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

function readExpanded(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === "expanded";
  } catch {
    return unsaved;
  }
}

function writeExpanded(expanded: boolean) {
  try {
    localStorage.setItem(SIDEBAR_KEY, expanded ? "expanded" : "collapsed");
  } catch {
    unsaved = expanded;
  }
  listeners.forEach((notify) => notify());
}
