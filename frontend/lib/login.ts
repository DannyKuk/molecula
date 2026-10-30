/** The Clerk login is on when the build has a publishable key (#343); without one the app and
 * the backend run open, as in development and the evals. */
export const LOGIN_ON = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);

/** The landing page, which `/` shows a visitor who isn't signed in (#455). */
export const LANDING_PAGE = "/about";

/** The picture of the preview card a shared link shows (#461), which the apps fetch signed out. */
const PREVIEW_CARD = "/opengraph-image";

const LOGIN_PAGES = ["/sign-in", "/sign-up"];

/** Whether a visitor who isn't signed in may open `pathname`: the landing page, the preview card's
 * picture and the login's own pages, whose catch-all routes go deeper. */
export function isPublicPage(pathname: string): boolean {
  return (
    pathname === LANDING_PAGE ||
    pathname === PREVIEW_CARD ||
    LOGIN_PAGES.some((page) => pathname === page || pathname.startsWith(`${page}/`))
  );
}

type GetToken = () => Promise<string | null>;

let registerGetToken: (getToken: GetToken) => void = () => {};
// Requests can start before the component inside ClerkProvider hands over its getToken, so they
// wait for it.
const tokenGetter = new Promise<GetToken>((resolve) => {
  registerGetToken = resolve;
});

/** Called once by the component inside ClerkProvider that owns Clerk's getToken. */
export function setGetToken(getToken: GetToken): void {
  registerGetToken(getToken);
}

/**
 * `fetch` with the signed-in user's session token as `Authorization`, which every backend route
 * but /health checks. Clerk's tokens live a minute, so each request asks for one; Clerk hands
 * back a cached token until it is about to expire. While the login is off it is plain `fetch`,
 * started at once.
 */
export function fetchWithLogin(url: string, init: RequestInit): Promise<Response> {
  if (!LOGIN_ON) return fetch(url, init);
  return withToken(init).then((signedIn) => fetch(url, signedIn));
}

async function withToken(init: RequestInit): Promise<RequestInit> {
  const token = await (await tokenGetter)();
  if (!token) return init;
  return { ...init, headers: { ...init.headers, Authorization: `Bearer ${token}` } };
}
