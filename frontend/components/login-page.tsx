import { notFound } from "next/navigation";
import { type ReactNode, Suspense } from "react";

import { LOGIN_ON } from "@/lib/login";

import { Brand } from "./brand-mark";

/** A page of the login (sign-in, sign-up, waitlist): Clerk's form in a narrow column under the
 * app's name. Not found while the login is off. */
export function LoginPage({ children }: { children: ReactNode }) {
  if (!LOGIN_ON) notFound();
  return (
    <main className="flex min-h-screen items-center justify-center bg-page px-4 py-10">
      <div className="w-full max-w-sm">
        <Brand className="mb-8 text-[17px]" />
        {/* Clerk's forms read the URL, which is only known when the page is requested. */}
        <Suspense>{children}</Suspense>
      </div>
    </main>
  );
}
