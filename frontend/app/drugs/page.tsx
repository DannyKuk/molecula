import type { Metadata } from "next";
import { Disclaimer } from "@/components/disclaimer";

import { DrugPicker, DrugsIntro } from "./drug-picker";

export const metadata: Metadata = {
  title: "Supported drugs · Molecula",
  description: "The drugs Molecula can answer questions about.",
};

export default function DrugsPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6 sm:py-24">
      <DrugsIntro />
      <DrugPicker />
      <footer className="mt-auto border-t border-rule pt-6">
        <Disclaimer />
      </footer>
    </main>
  );
}
