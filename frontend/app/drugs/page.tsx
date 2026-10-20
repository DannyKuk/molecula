import type { Metadata } from "next";
import Link from "next/link";

import { Disclaimer } from "@/components/disclaimer";

import { DrugPicker } from "./drug-picker";

export const metadata: Metadata = {
  title: "Supported drugs · Molecula",
  description: "The drugs Molecula can answer questions about.",
};

export default function DrugsPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6 sm:py-24">
      <Link href="/" className="self-start text-sm text-ink-2 underline-offset-4 hover:underline">
        ← Molecula
      </Link>
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">Supported drugs</h1>
        <p className="text-ink-2">
          Molecula answers only about the drugs on this list. Search by generic name, brand or
          another name.
        </p>
      </div>
      <DrugPicker />
      <footer className="mt-auto border-t border-rule pt-6">
        <Disclaimer />
      </footer>
    </main>
  );
}
