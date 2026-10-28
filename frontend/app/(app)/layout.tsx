import { LoginProvider } from "@/components/login-provider";

// Clerk wraps only the app and its login pages, so the landing page outside this group loads no
// Clerk script and a visitor who only looks at it sends Clerk nothing (#458).
export default function AppLayout({ children }: LayoutProps<"/">) {
  return <LoginProvider>{children}</LoginProvider>;
}
