import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site";

// Only the landing page is public. The app's pages send a signed-out crawler to the sign-in page,
// so keeping crawlers off the login pages keeps them off the app as well.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/sign-in", "/sign-up"] },
    sitemap: new URL("/sitemap.xml", SITE_URL).href,
  };
}
