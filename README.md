# szl-holdings.github.io
<!-- szl:header v1 -->
[![org: szl-holdings](https://img.shields.io/badge/org-szl--holdings-black)](https://github.com/szl-holdings)
[![doctrine](https://img.shields.io/badge/doctrine-control%20before%20action%20%C2%B7%20evidence%20after-blue)](https://a-11-oy.com)

**Control before action. Evidence after.**

Part of the [szl-holdings](https://github.com/szl-holdings) estate ·
Product: [a-11-oy.com](https://a-11-oy.com) ·
Proof: [a11oy.net](https://a11oy.net)
<!-- /szl:header -->

Source contract for the **SZL Holdings** company front door. The committed
[`CNAME`](./CNAME) binds the Pages publication to
**[holdings.a-11-oy.com](https://holdings.a-11-oy.com)**. A merge, a successful
Pages deployment, and a public HTTP readback remain separate evidence steps.

The live A11oy product/runtime is separately published at
**[a-11-oy.com](https://a-11-oy.com)**. This repository does not imitate the
product console, verifier, or API, and a Pages HTTP 200 is not Command Center
health.

> **SZL Holdings — governed AI you can prove.**
> `receipts.in ≡ receipts.out` · Doctrine v11 LOCKED · Λ = Conjecture 1

## What's here

| File | Purpose |
|---|---|
| [`index.html`](./index.html) | Static company, investor, portfolio, and developer landing |
| [`products/index.html`](./products/index.html) | Source-declared product catalog; not live health |
| [`styles.css`](./styles.css) | KANCHAY palette; no runtime CDN |
| [`app.js`](./app.js) | Progressive front-end interactions |
| [`console/index.html`](./console/index.html) | Honest pointer to the separate A11oy console |
| [`verify/index.html`](./verify/index.html) | Honest pointer to the separate A11oy verifier |
| [`api/a11oy/v1/honest.json`](./api/a11oy/v1/honest.json) | Static source document, not runtime doctrine |
| [`origin-authority.json`](./origin-authority.json) | Source contract for company, product, and proof origins |
| [`origin-status.json`](./origin-status.json) | Dated hosting observation; may precede the current source contract |
| [`CNAME`](./CNAME) | Company custom domain: `holdings.a-11-oy.com` |
| [`robots.txt`](./robots.txt) · [`sitemap.xml`](./sitemap.xml) | Crawl and route inventory |
| `.nojekyll` | Serve committed files as-is |

## Serving

GitHub Pages publishes this tree from `main`. Previewing the source is
network-free:

```bash
python3 -m http.server 8000
```

## Related

- **Company and portfolio:** [holdings.a-11-oy.com](https://holdings.a-11-oy.com)
- **Developer docs:** [holdings.a-11-oy.com/docs-site](https://holdings.a-11-oy.com/docs-site/)
- **A11oy product/runtime:** [a-11-oy.com](https://a-11-oy.com)
- **Provider twin:** [szlholdings-a11oy.hf.space](https://szlholdings-a11oy.hf.space/)
- **Proof:** [a11oy.net](https://a11oy.net)
- **Source organization:** [github.com/szl-holdings](https://github.com/szl-holdings)

## License

[Apache-2.0](./LICENSE) © SZL Holdings.
