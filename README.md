# szl-holdings.github.io
<!-- szl:header v1 -->
<!-- badges: add this repo's CI / release / status badges here -->
[![org: szl-holdings](https://img.shields.io/badge/org-szl--holdings-black)](https://github.com/szl-holdings)
[![doctrine](https://img.shields.io/badge/doctrine-control%20before%20action%20%C2%B7%20evidence%20after-blue)](https://a-11-oy.com)

**Control before action. Evidence after.**

Part of the [szl-holdings](https://github.com/szl-holdings) estate ·
Product: [a-11-oy.com](https://a-11-oy.com) ·
Proof: [a11oy.net](https://a11oy.net)
<!-- /szl:header -->

Source for the **SZL Holdings** front-door website, served via GitHub Pages at
**[holdings.a-11-oy.com](https://holdings.a-11-oy.com)** (custom domain set in
[`CNAME`](./CNAME); also reachable at
[szl-holdings.github.io](https://szl-holdings.github.io/)).

> **SZL Holdings — Proof infrastructure for consequential AI.**
> Sovereign inference · DSSE-signed receipts · machine-checked in Lean 4.
> `receipts.in ≡ receipts.out`

This is a static marketing / landing site — the company front door that funnels
to the flagship product at **[a-11-oy.com](https://a-11-oy.com)**. It does not
duplicate product or console content.

## What's here

| File | Purpose |
|---|---|
| [`index.html`](./index.html) | The single-page site (hero, five-organ anatomy, open standards, concierge, thesis) |
| [`styles.css`](./styles.css) | Site styles (KANCHAY palette; no runtime CDN for layout) |
| [`app.js`](./app.js) | Front-end interactions |
| [`assets/hero.png`](./assets/hero.png) | Open Graph / Twitter social-preview image |
| [`CNAME`](./CNAME) | Custom domain: `holdings.a-11-oy.com` |
| [`robots.txt`](./robots.txt) · [`sitemap.xml`](./sitemap.xml) | Crawl + indexing hints |
| `.nojekyll` | Serve files as-is (skip Jekyll processing) |

## Serving

GitHub Pages builds this repo from the default branch (`main`) and serves it at
the domain in `CNAME`. There is no build step — the committed HTML/CSS/JS is
published as-is.

To preview locally, serve the repo root with any static file server:

```bash
python3 -m http.server 8000
# then open http://localhost:8000
```

## CI

A single lightweight workflow,
[`.github/workflows/link-check.yml`](./.github/workflows/link-check.yml),
parses the HTML and verifies that every local link and asset (including the
Open Graph image and `sitemap.xml`) resolves. It uses only the runtime already
on the runner — no external link-checking service.

## Related

- **Flagship product:** [a-11-oy.com](https://a-11-oy.com)
- **Docs:** [szl-holdings.github.io/docs-site](https://szl-holdings.github.io/docs-site/)
- **Org:** [github.com/szl-holdings](https://github.com/szl-holdings)

## License

[Apache-2.0](./LICENSE) © SZL Holdings.
