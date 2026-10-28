import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

import { isPublicPage, LANDING_PAGE, LOGIN_ON } from "@/lib/login";

// Every page but the landing page and the login's own needs a signed-in user. At `/` a visitor who
// isn't signed in gets the landing page instead of the sign-in form, with the address left as it
// is. The backend checks the token on every request as well, so this only spares a signed-out
// visitor an app that can't load anything.
const loginGate = clerkMiddleware(
  async (auth, request) => {
    const { pathname } = request.nextUrl;
    if (pathname === "/" && !(await auth()).userId) {
      return NextResponse.rewrite(new URL(LANDING_PAGE, request.url));
    }
    if (!isPublicPage(pathname)) await auth.protect();
  },
  { signInUrl: "/sign-in", signUpUrl: "/sign-up" },
);

export default LOGIN_ON ? loginGate : () => NextResponse.next();

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|mp4|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
