# marketing/ — Crucible product site

Source for `crucible.nousergon.ai` (the Crucible experiment-harness product site; the apex lab landing lives in `marketing-apex/`). Lives alongside
the Streamlit live console at `live/`; the two surfaces share this repo but ship
through different deploy paths.

## Stack

- **Astro 6** static-site generator (`output: "static"`). Zero JS shipped to the
  browser by default; React/Vue/Svelte islands available via `astro add` if a
  page needs interactivity later.
- **Tailwind 4** via `@tailwindcss/vite`. Stylesheet at `src/styles/global.css`
  is imported once from `src/layouts/Base.astro`.
- **TypeScript strict** for `.astro` component frontmatter.

## Project layout

```text
marketing/
├── src/
│   ├── layouts/Base.astro       header + footer + meta tags
│   ├── pages/
│   │   ├── index.astro          home: hero + 4 pillars
│   │   ├── about.astro          origin + thesis + built-by + contact
│   │   └── architecture.astro   six modules / three pipelines / feedback loop
│   └── styles/global.css        Tailwind import
├── public/                       static assets (favicon, og images)
├── astro.config.mjs              tailwind integration wired in
└── package.json
```

## Commands

```sh
cd marketing/
npm install        # idempotent, first-time setup
npm run dev        # local dev at http://localhost:4321
npm run check      # astro check (TS + Astro template diagnostics)
npm run lint       # biome lint (JS/TS/JSON; .astro out of scope, see below)
npm run format     # biome format --write
npm run format:check  # biome format check (CI mode, no writes)
npm run build      # astro check && astro build → dist/
npm run preview    # preview the production build locally
```

## Hygiene baseline

Institutional-default tooling so the SOTA discipline doesn't drift over time:

- **`astro check`** runs as part of `npm run build` — TS + Astro template
  diagnostics are hard failures, can't ship with type errors.
- **Biome** handles format + lint for JS/TS/JSON files. `.astro` files are
  excluded from Biome's lint scope because Biome's parser doesn't yet
  understand `.astro` template references to frontmatter variables (would
  false-positive on every component's main data export). Astro's own
  `astro check` covers `.astro` linting.
- **`@astrojs/sitemap`** auto-generates `sitemap-index.xml` + `sitemap-0.xml`
  at build time from declared routes. `astro.config.mjs` sets `site:` to the
  canonical URL.
- **`public/robots.txt`** allows everything, advertises the sitemap.
- **JSON-LD structured data** is rendered into `<head>` by `Base.astro` —
  defaults to a WebSite + Organization graph; pages can override via the
  `jsonLd` prop for Article / AboutPage / BreadcrumbList etc.
- **Canonical `<link rel="canonical">`** is generated per-page from `Astro.url`.
- **Skip-to-main-content link** at the top of `<body>` for keyboard
  navigation (WCAG 2.1 baseline).
- **`.github/workflows/marketing-ci.yml`** runs `npm ci && biome lint &&
  biome format --check && astro check && astro build` on PRs touching
  `marketing/**`, plus verifies `sitemap-index.xml` and `robots.txt` made it
  into `dist/`. Per the [[reference_live_disable_without_source_fix_antipattern]]
  discipline — the build can't silently regress.

## Deploy plan (current state: scaffold only, not yet wired to apex)

The site is **not yet served from `nousergon.ai`** as of this commit. Apex
nousergon.ai still proxies to the Streamlit live console on port 8502; this
will flip in a follow-up PR after Cloudflare Pages is configured and the
content layer is filled in further.

Sequencing:
1. **This PR (scaffold)**: Astro project + three placeholder pages buildable
   locally; no production deploy.
2. **Follow-up: content port**: bring About / Architecture / Stack / Retros
   up to parity with the existing Streamlit equivalents in `live/pages/`.
3. **Follow-up: Cloudflare Pages**: connect the repo to Cloudflare Pages with
   build command `cd marketing && npm install && npm run build` and output
   directory `marketing/dist`. Custom domain configured to `nousergon.ai`.
4. **Follow-up: nginx + DNS swap**: at cutover, point Cloudflare Pages at
   apex `nousergon.ai`, move the Streamlit live console to
   `live.nousergon.ai` (nginx already serves it on port 8502 — just need the
   DNS record + a new nginx `server_name`). After verification, remove the
   apex Streamlit nginx block.

## Why a static site instead of staying in Streamlit?

The 2026-05-21 architectural decision (see ROADMAP "Strategic Framing —
Two Products, Not One"): the harness is the durable product, the alpha
generator is the first experiment inside it. A static marketing surface
fits the harness identity (declarative, fast-loading, no widget churn);
the live data console stays in Streamlit because that's what Streamlit
is good at. Split-by-purpose, not split-by-tech-preference.

See the dashboard root `README.md` for the broader context.
