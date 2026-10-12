import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { Disclaimer } from "@/components/disclaimer";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Molecula",
  description: "A medicines chatbot grounded in FDA drug labels and chemistry data.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        {children}
        <footer className="border-t border-zinc-200 dark:border-zinc-800">
          <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
            <Disclaimer />
          </div>
        </footer>
      </body>
    </html>
  );
}
