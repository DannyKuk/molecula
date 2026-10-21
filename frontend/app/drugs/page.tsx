import type { Metadata } from "next";

import { DrugsPage } from "./drug-picker";

export const metadata: Metadata = {
  title: "Supported drugs · Molecula",
  description: "The drugs Molecula can answer questions about.",
};

export default function Page() {
  return <DrugsPage />;
}
