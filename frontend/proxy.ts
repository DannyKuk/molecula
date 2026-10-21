import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

import { LOGIN_ON } from "@/lib/login";

const LOGIN_PAGES = ["/sign-in", "/sign-up", "/waitlist"];

// Every page but the login's own needs a signed-in user. The backend checks the token on every
// request as well, so this only spares a signed-out visitor an app that can't load anything.
const loginGate = clerkMiddleware(
  async (auth, request) => {
    const { pathname } = request.nextUrl;
    if (!LOGIN_PAGES.some((page) => pathname.startsWith(page))) await auth.protect();
  },
  { signInUrl: "/sign-in", signUpUrl: "/sign-up" },
);

export default LOGIN_ON ? loginGate : () => NextResponse.next();

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
