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
| [`estate/index.html`](./estate/index.html) | Searchable 5 October 2026 public snapshot: 127 GitHub repositories, 47 model repositories, 37 datasets and 34 Spaces; exact source links and declared gates |
| [`scripts/build_estate_public_snapshot.py`](./scripts/build_estate_public_snapshot.py) | Offline rebuild from an explicit completed audit and UTC collection timestamp; excludes private or unknown-privacy rows and rejects missing source revisions |
| [`frontier/index.html`](./frontier/index.html) | Dated public math and model atlas: 39 selected software projects and all 47 public Hub model repositories in the captured snapshot |
| [`frontier/showcase-public.html`](./frontier/showcase-public.html) | Searchable 244-asset public organization inventory: 127 GitHub repositories, 47 Hub model-type repositories, 36 datasets, and 34 Spaces; private assets are excluded |
| [`frontier/audit-data/hf-public-overlay.json`](./frontier/audit-data/hf-public-overlay.json) | Revision-pinned public Hub additions and `szl-formulas` software mirror refresh checked after the base census; the new ReceiptAgent ID is labeled as a one-file repository scaffold, and `SZLHOLDINGS/README` is an organization card represented by a static Space |
| [`frontier/proof-to-code-matrix.csv`](./frontier/proof-to-code-matrix.csv) | Revision-pinned 21-callable formula inventory; proof-to-code mappings remain unverified |
| [`frontier/build_proof_code_matrix.py`](./frontier/build_proof_code_matrix.py) | Source-only matrix rebuild script; requires clean formula and Lean checkouts at the recorded SHAs |
| [`styles.css`](./styles.css) | Site layout on the KANCHAY light marketing surface; no runtime CDN, no webfonts |
| [`assets/szl/`](./assets/szl/) | Vendored SZL KANCHAY v1.1.0 (founder direction): `szl-design-system.css`, the orbit logo and favicons, `SOURCE.json` digests. Byte-for-byte; never edit |
| [`app.js`](./app.js) | Progressive front-end interactions |
| [`assets/hero.png`](./assets/hero.png) | Open Graph / Twitter card: the vendored `szl_logo_primary.svg` rendered unmodified on `--color-space-900`, 1200×630 |
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

The frontier bundle includes a [public source receipt](./frontier/audit-data/public-source-receipt.json) and a separate [proof-to-code review](./frontier/PROOF_TO_CODE.md). It shows repository metadata and reported source status; it does not claim model qualification, deployment, or a proof that Python implementations refine Lean statements. The public boundary is checked by `python3 tests/test_frontier_public_assets.py` in the link workflow.

The `szl-formulas` software entry now pins the public [model mirror](https://huggingface.co/SZLHOLDINGS/szl-formulas/tree/d3f2dbbb7c59bef13cf1b755edf487bfb2960653) at `d3f2dbbb7c59bef13cf1b755edf487bfb2960653` and the separate [kernel package](https://huggingface.co/kernels/SZLHOLDINGS/szl-formulas/tree/04082bd2f7ca43ce7c00d47069cb5a25d662116c) at `04082bd2f7ca43ce7c00d47069cb5a25d662116c`. Their byte-identical public source bindings name [GitHub source `a3f9dcab6e3564ce384bd3c095f64cc2121059f9`](https://github.com/szl-holdings/szl-formulas/tree/a3f9dcab6e3564ce384bd3c095f64cc2121059f9); all 32 managed-file hash readbacks matched the bindings. This establishes the observed mirror bytes, not runtime behavior, scientific validity, or a proof-to-code refinement. The proof-to-code review remains pinned to its separately inspected source revision.

## Refreshing the public estate snapshot

Keep the raw audit outside this publication repository. The generator accepts only
literal `private: false` records in `szl-holdings` and `SZLHOLDINGS`, constructs
canonical links at exact revisions, and retains bounded CI and model promotion
limits. A missing public revision stops generation. The current snapshot was
generated from the completed 5 October audit at `2026-10-05T12:43:48.724254+00:00`.
The earlier `/frontier/` inventory retains its own separately recorded scope.

The CLI requires a private `public-source-binding.json` at the **audit root**,
beside `audit-receipt.json`, `execution-source-binding.json`, `execution/`,
`github-request-ledger.jsonl` and `audit-data/`. It accepts the root or its
`audit-data/` directory. The binding contract is:

- Schema `szl.estate-audit-source-binding/v1`, literal `signed: false`, canonical
  `scope` (`github: ["szl-holdings"]`, `huggingface: ["SZLHOLDINGS"]`).
- `observed_at` must exactly equal `estate-summary.json.generated_at` and
  `audit-receipt.json.generated_at`. The receipt must bind the summary SHA-256.
  A future date is refused. Optional `--observed-at` asserts that exact value;
  it cannot override the collected date.
- `input_sha256` maps normalized audit-root-relative paths to exact byte hashes:
  both repository lists, every GitHub source report (including private reports),
  the summary, audit receipt, execution source binding, request ledger, and all
  eight execution files named by the collector source binding. The generator
  hashes each input once and parses those same cached bytes.
- `counts.raw` and `counts.public` contain all four repository-kind counts.
  They must match the census lists; raw counts must also match the receipt and
  summary coverage, including full GitHub inspection coverage.
- `completion.collector` requires `completed: true`, `exit_code: 0`,
  `evidence_class: "DECLARED"` and `command: "estate_agent.py all --output ."`.
  `completion.github` requires complete enumeration and inspection plus
  `pagination` (`per_page: 100`, terminal page, terminal short-page row count).
  The bound ledger must record every successful page in order before the audit
  date. `completion.huggingface` requires complete enumeration and
  `iterators_exhausted: ["model", "dataset", "space"]`.

Create the completion declaration only from an observed successful collector
exit and terminal pagination/iterator exhaustion, never from counts alone. The
binding is unsigned local evidence, not authentication or an independent witness.
Hash/count validation is MEASURED locally; completion remains an unsigned
DECLARED observation. Keep the binding and raw audit private. The public snapshot
retains its closed field allowlist and includes neither private identifiers nor
private counts or paths. Provider repository/runtime metadata is DECLARED; the
published owner report of Khipu's 2/6 abstention remains REPORTED and BLOCKED.

```bash
python3 scripts/build_estate_public_snapshot.py --audit-dir /path/to/completed-audit
python3 scripts/bind_browser_policy.py --check
python3 -m unittest discover -s tests -p 'test*estate*py'
```

The dated snapshot test pins its timestamp and public counts. Update those
assertions with the regenerated snapshot, then keep the homepage count consistent.
The generator's independent tests cover privacy exclusion, invalid revision
rejection, incomplete/hash-mismatched bindings, date conflicts, future dates,
untrusted HTML escaping and exact-source CI failures. Its code preserves
the existing page styles, scripts and browser policy. See the
[source validation receipt](./estate/snapshot-receipt.json) for this refresh's local
checks; publication and live readback require separate evidence.

## Browser policy

Every HTML document in this repository carries an early meta Content Security
Policy and `no-referrer`. Scripts are restricted to exact SHA-256 hashes of
reviewed external files and inline blocks; scriptless pointer pages
deny scripts. The company site currently denies fetch/WebSocket connections,
frames, plugins, workers and native form submission. Live concierge endpoints
remain disabled in `app.js`; this policy does not enable or certify a backend.

After reviewing HTML/script changes or regenerating the Frontier inventory, run:

```bash
python3 scripts/bind_browser_policy.py --write
python3 scripts/bind_browser_policy.py --check
python3 -m unittest discover -s tests -p test_browser_policy.py
```

CI only checks; it never rewrites policy to accept changed code. Inline hashes use
UTF-8 script text with browser-style newline normalization, without trimming.
External scripts carry one matching `integrity` attribute: the browser must verify
the fetched bytes, not just the script's origin. The three published JavaScript
files are LF-bound through `.gitattributes`; the generator accounts for pre-existing
Windows CRLF text checkouts, while served bodies must match the actual LF source
blobs. Never hash an edge-transformed or minified body as if it were the reviewed
source. The Flow materializer refuses non-LF JavaScript input before writing.
Inline styles remain permitted for the existing layout and generated charts;
this is not a claim that all inline content is forbidden. There is no `script-src
'self'` or `strict-dynamic` fallback: a newly inserted same-origin script without
an authorized integrity hash is denied. Hashes authorize exact content, not a
particular filename or origin; they cannot protect a policy document that an
attacker can rewrite.

After either asset generator runs, repeat the browser-policy commands above so
both external pins and the document's allowed hashes agree. A changed asset with
stale HTML intentionally fails closed. Keep asset URLs immutable across content
changes or verify deployment/cache coherence; this release changes no JavaScript
body. The hosted Chrome suite tests approved interactions, missing/wrong integrity,
unapproved same-origin scripts, and modified response bodies. It is not a claim of
browser execution coverage for Firefox or Safari. External CSP hashes require
Chrome 59+, Firefox 116+, or Safari 15.6+ (conservative compatibility floor);
older browsers may retain static content but lose progressive interactions.
See [CSP external hash sources](https://www.w3.org/TR/CSP/#external-hash)
and [Subresource Integrity](https://www.w3.org/TR/SRI/).

This is an HTML meta policy, not an HTTP response-header change. It cannot
provide `frame-ancestors`, sandbox or report-only enforcement through meta.
Delivery-layer scripts absent from the reviewed hash list are not allowlisted,
even when same-origin, and may be blocked;
it is not needed by the source UI. No DNS/edge settings are changed. The separate
`/docs-site/` project publishes its own HTML and is **not** covered by this
repository's policy. See the [CSP meta delivery specification](https://www.w3.org/TR/CSP/#meta-element).

## Related

- **Company and portfolio:** [holdings.a-11-oy.com](https://holdings.a-11-oy.com)
- **Developer docs:** [holdings.a-11-oy.com/docs-site](https://holdings.a-11-oy.com/docs-site/)
- **A11oy product/runtime:** [a-11-oy.com](https://a-11-oy.com)
- **Provider twin:** [szlholdings-a11oy.hf.space](https://szlholdings-a11oy.hf.space/)
- **Proof:** [a11oy.net](https://a11oy.net)
- **Source organization:** [github.com/szl-holdings](https://github.com/szl-holdings)

## License

[Apache-2.0](./LICENSE) © SZL Holdings.
