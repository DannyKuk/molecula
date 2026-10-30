import type { MetadataRoute } from "next";

import { LANDING_URL } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  return [{ url: LANDING_URL }];
}
