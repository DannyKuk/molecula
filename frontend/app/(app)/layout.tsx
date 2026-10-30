import type { Metadata } from "next";

import { LoginProvider } from "@/components/login-provider";

// The app and its login pages are for invited testers; only the landing page is for search (#463).
export const metadata: Metadata = { robots: { index: false, follow: false } };

// Clerk wraps only the app and its login pages, so the landing page outside this group loads no
// Clerk script and a visitor who only looks at it sends Clerk nothing (#458).
export default function AppLayout({ children }: LayoutProps<"/">) {
  return <LoginProvider>{children}</LoginProvider>;
}
