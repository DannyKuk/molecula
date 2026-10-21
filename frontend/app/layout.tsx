import type { Metadata } from "next";
import { Inter_Tight, JetBrains_Mono } from "next/font/google";

import { DocumentLanguage } from "@/components/language-switch";
import { LoginProvider } from "@/components/login-provider";

import "./globals.css";

// next/font downloads both at build time and serves them with the app, so nothing is fetched at
// runtime and the app works offline.
const interTight = Inter_Tight({
  variable: "--font-inter-tight",
  subsets: ["latin"],
});

const jetBrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Molecula",
  description: "A medicines chatbot grounded in FDA drug labels and chemistry data.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${interTight.variable} ${jetBrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <LoginProvider>
          <DocumentLanguage />
          {children}
        </LoginProvider>
      </body>
    </html>
  );
}
