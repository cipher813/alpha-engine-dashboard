# marketing/ — Nous Ergon apex static site

Source for `nousergon.ai` (the public-facing marketing surface). Lives alongside
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
npm run build      # production build → dist/
npm run preview    # preview the production build locally
```

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
