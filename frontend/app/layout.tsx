import type { Metadata } from "next";
import { Inter_Tight, JetBrains_Mono } from "next/font/google";

import { DocumentLanguage } from "@/components/language-switch";
import { DocumentTheme } from "@/components/theme-switch";
import { SITE_URL } from "@/lib/site";
import { THEME_SCRIPT } from "@/lib/theme-script";

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

const DESCRIPTION =
  "A medicines chatbot that answers from FDA drug labels and shows drugs binding in 3D.";

// The preview card a shared link shows (#461). Its picture comes from `opengraph-image.tsx` beside
// this file, and its address starts with SITE_URL.
export const metadata: Metadata = {
  metadataBase: SITE_URL,
  title: "Molecula",
  description: DESCRIPTION,
  openGraph: { title: "Molecula", description: DESCRIPTION, siteName: "Molecula", type: "website" },
  twitter: { card: "summary_large_image", title: "Molecula", description: DESCRIPTION },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // The inline script sets data-theme before React hydrates, which React would report as a mismatch.
    <html
      lang="en"
      className={`${interTight.variable} ${jetBrainsMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="min-h-full flex flex-col">
        <DocumentLanguage />
        <DocumentTheme />
        {children}
      </body>
    </html>
  );
}
