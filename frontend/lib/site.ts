/** The frontend's own address, which absolute links in the preview card, the robots file and the
 * sitemap start with. It is a build argument because those are built before any request; without
 * it they point at localhost, as Next's own default does. */
export const SITE_URL = new URL(process.env.SITE_URL ?? "http://localhost:3000");

/** The landing page's address for search engines: `/`, which shows it signed out, not `/about`,
 * where it lives (#463). */
export const LANDING_URL = new URL("/", SITE_URL).href;
