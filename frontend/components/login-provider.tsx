import { ClerkProvider } from "@clerk/nextjs";
import type { ReactNode } from "react";

import { LoginToken } from "@/components/login";
import { LOGIN_ON } from "@/lib/login";

// Clerk's sign-in, sign-up and profile drawn like the app: no card box, left-aligned text,
// thin rules, the flat signal orange of Send for the one action, and the app's fonts. The colours
// are the app's tokens (globals.css), so the dark ones follow the system as the app does.
//
// Clerk draws outlines as box shadows in its own rules, which win over these and fade
// colorBorder to a few percent, hence the !important.
const RULE = "inset 0 0 0 1px var(--rule-2) !important";

// Clerk's root box is fit-content and caps the card at 100vw - 2.5rem, so on a phone the form
// shrank to its text and sat at the left of the column. The login pages fill their column instead.
const FILL_COLUMN = {
  elements: { rootBox: { width: "100%" }, cardBox: { maxWidth: "none" } },
};

const appearance = {
  signIn: FILL_COLUMN,
  signUp: FILL_COLUMN,
  variables: {
    colorPrimary: "var(--signal)",
    colorPrimaryForeground: "#ffffff",
    colorBackground: "var(--page)",
    colorForeground: "var(--ink)",
    colorMutedForeground: "var(--ink-2)",
    colorMuted: "var(--panel)",
    colorNeutral: "var(--ink)",
    colorInput: "var(--card)",
    colorInputForeground: "var(--ink)",
    colorBorder: "var(--rule-2)",
    colorRing: "var(--ink-3)",
    colorDanger: "var(--destructive)",
    colorShadow: "transparent",
    fontFamily: "var(--font-inter-tight)",
    fontFamilyButtons: "var(--font-inter-tight)",
    fontFamilyMono: "var(--font-jetbrains-mono)",
    borderRadius: "0",
  },
  elements: {
    cardBox: { boxShadow: "none", border: "none", width: "100%" },
    // Clerk sets the card 1px wider than its box on each side, which clipped the outlines.
    card: {
      background: "transparent",
      boxShadow: "none",
      border: "none",
      padding: "0",
      margin: "0",
    },
    header: { alignItems: "flex-start", textAlign: "left" },
    headerTitle: { fontSize: "20px", fontWeight: 600 },
    headerSubtitle: { color: "var(--ink-2)" },
    socialButtonsBlockButton: { background: "transparent", boxShadow: RULE },
    // Clerk hangs the badge past the button's corner, outside the card, which cuts it off.
    lastAuthenticationStrategyBadge: { right: "0", transform: "translateY(-50%)" },
    dividerLine: { background: "var(--rule)" },
    formFieldInput: { boxShadow: RULE },
    formButtonPrimary: {
      boxShadow: "none !important",
      fontWeight: 600,
      "&::after": { display: "none" },
    },
    footer: {
      background: "transparent",
      borderTop: "1px solid var(--rule)",
      marginTop: "24px",
      "& > *": { background: "transparent", justifyContent: "flex-start", padding: "12px 0 0" },
    },
    footerActionLink: { color: "var(--signal)", fontWeight: 600 },
    userButtonPopoverCard: { border: "1px solid var(--rule-2)" },
    userButtonPopoverFooter: { background: "var(--page)", borderTop: "1px solid var(--rule)" },
  },
};

/** The Clerk login around the app when the build has a publishable key; the app alone without
 * one. Its own pages are /sign-in and /sign-up, where an invitation link lets the invited person
 * set a password (sign-up is invite only). */
export function LoginProvider({ children }: { children: ReactNode }) {
  if (!LOGIN_ON) return children;
  return (
    <ClerkProvider appearance={appearance} signInUrl="/sign-in" signUpUrl="/sign-up">
      <LoginToken />
      {children}
    </ClerkProvider>
  );
}
