// @ts-check
// Touched 2026-05-22 to retrigger Cloudflare Pages deploy after a wedged
// production build for 6f23d00 left nousergon.ai serving HTTP 500.
import { defineConfig } from 'astro/config';

import tailwindcss from '@tailwindcss/vite';

import sitemap from '@astrojs/sitemap';

// https://astro.build/config
export default defineConfig({
  // `site` is the canonical origin for absolute URLs in sitemap, canonical
  // <link> tags, and OG meta. Required for @astrojs/sitemap to emit
  // sitemap-index.xml.
  site: 'https://metron.nousergon.ai',

  vite: {
    plugins: [tailwindcss()],
  },

  integrations: [sitemap()],
});
