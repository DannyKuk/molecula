import type { Metadata } from "next";

import { Dashboard } from "@/components/dashboard/dashboard";

export const metadata: Metadata = {
  title: "Dashboard · Molecula",
  description: "What Molecula answers from, and how the chat is used.",
};

export default function DashboardPage() {
  return <Dashboard />;
}
