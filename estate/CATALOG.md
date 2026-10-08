# Public software catalog

The estate page joins six public namespaces: GitHub repositories, Hugging Face
models, datasets, Spaces and kernels, and published PyPI distributions. The
committed catalog contains 283 surfaces: 128 GitHub, 48 model repositories, 37 datasets,
36 Spaces, 14 kernels and 20 PyPI packages. A project can have several surfaces.

## Evidence and limits

- **MEASURED:** public membership enumeration on 2026-10-08; PyPI metadata
  retains its 2026-10-07 observation. The public projection admitted only
  literal `private: false` rows. The public `SZLHOLDINGS/README` Space was
  confirmed by direct API readback after the anonymous author list omitted it.
- Repository and kernel states retain separate 2026-10-08 and 2026-10-06
  observation dates and immutable revisions. A kernel's dated model-mirror
  revision can differ from the newer model repository snapshot. This join does
  not refresh CI or runtime state beyond the recorded source observation.
- **DECLARED:** PyPI versions, descriptions, file hashes and provenance links are
  provider metadata. Inspected source metadata revisions establish attribution;
  package/source equivalence remains **UNKNOWN**.
- Pinned installation recipes are examples; installation and imports were
  **NOT RUN**. Releases whose artifacts are all yanked do not get a recipe.
- Kernel/model-mirror equivalence is **UNKNOWN**. A distribution is not another
  trained model. Inference, training, numerical replay and independent evaluation
  were **NOT RUN**. Published failed gates remain visible.
- `SZLHOLDINGS/oac-ops-health-v2` is model-hosted software with a Python
  kernel and JSON coefficients, not a transformer checkpoint. Its card reports
  a synthetic operational advisory only. Its receipt is unsigned; the
  canonical Forge publishing manifest has no binding for this ID. No clinical
  or production authority follows from its listing.

The joined [public-catalog.json](./public-catalog.json) binds the exact bytes of
[public-snapshot.json](./public-snapshot.json),
[kernel-distributions.json](./kernel-distributions.json),
[pypi-packages.json](./pypi-packages.json) and
[catalog-membership.json](./catalog-membership.json) with SHA-256 hashes. Raw
authenticated inventories and audit workspaces are excluded from publication.

## Offline checks

From the repository root, with Python 3 and Node available:

```powershell
py -3 -X utf8 -m unittest discover -s tests -p 'test_*.py' -v
py -3 -X utf8 scripts/build_pypi_public_snapshot.py --check
py -3 -X utf8 scripts/build_public_catalog.py --check
py -3 -X utf8 scripts/bind_browser_policy.py --check
py -3 -X utf8 scripts/verify_site_links.py
node --check tests/browser_policy_smoke.js
```

`--check` validates committed public inputs and deterministic output without
network requests. New membership without a matching immutable source row fails.
The byte-bound JSON inputs require LF line endings on every platform; the
generator rejects CRLF before hashing, and Git attributes retain LF on checkout.
Unknown fields, duplicate identities, private rows, future dates, mutable source
links and malformed artifact hashes fail instead of producing partial output.

## Regeneration order

Refresh and review the public source, kernel, membership and PyPI inputs first.
Run the repository and kernel generators through their documented privacy and
revision gates. Those generators render their own intermediate estate sections.
Then run `py -3 -X utf8 scripts/build_public_catalog.py` last to rebuild the joined
JSON and six-namespace HTML from the reviewed public inputs. Commit the inputs
and generated outputs together. Never feed a raw private inventory to this join.

The Linux GitHub Actions runner executes
`python3 tests/browser_policy_smoke.py` against all seven site routes. It checks
each namespace, combined search, pinned package recipes, narrow-screen layout,
and browser policy enforcement. The harness intentionally rejects local Windows
Chrome execution; local unit success does not establish that CI browser result.

Publication needs exact-head CI, a normal merge, Pages completion and hosted
artifact readback. None of these establish model qualification or certification.
