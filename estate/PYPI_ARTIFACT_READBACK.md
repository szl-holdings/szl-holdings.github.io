# Opaque PyPI archive byte readback

The [public report](pypi-artifact-byte-readback.json) records a **MEASURED**
stream of the 40 wheel and source archives listed for 20 public distributions
in the 7 October [PyPI metadata snapshot](pypi-packages.json). That snapshot is
bound to site source commit
`7623a44f51af3c07a41e2f8dea81753a95a7edee` and SHA-256
`ff80979ded90364bc3122cc7b98c2fa51ec6578e6b5f98c4f973b17e119cc2a4`.
On 8 October, all 40 exact `files.pythonhosted.org` URLs returned HTTP 200 and
the streamed **1,632,195 bytes** matched their declared per-file SHA-256 and
size. No downloaded archive was saved, opened, imported, extracted or installed.

The provider hash is a **DECLARED** PyPI metadata value; this readback measures
consistency with the bytes served at the pinned URLs. PyPI provenance
attestation signatures remain **UNKNOWN**, GitHub source/package equivalence
remains **UNKNOWN**, and independent replay was **NOT RUN**. The result says
nothing about package behavior, current default branch parity or production
authorization. It also does not claim that this dated list covers every future
PyPI release.

The verifier accepts only the pinned manifest bytes and a previously committed
literal-public source inventory. It enforces the existing closed PyPI metadata
validator, a first-party file host, exact URLs after response, no HTTP redirects,
20-second request timeouts, per-file and total byte caps, and streamed hashing.
Provider reads carry no credential. A failed or incomplete run writes a local
report with `BLOCKED` or `UNAVAILABLE`; it cannot pass the offline publication
check. Live runs require a fresh output path so a retry cannot replace an earlier
result.

From the site repository root:

```powershell
py -3 -B -X utf8 scripts/verify_pypi_artifact_bytes.py --check
py -3 -B -X utf8 -m unittest discover -s tests -p test_verify_pypi_artifact_bytes.py -v
py -3 -B -X utf8 scripts/verify_pypi_artifact_bytes.py --output C:\path\to\fresh-pypi-readback.json
```

The first two commands are offline and run in CI. The third makes bounded GET
requests and must be reviewed before any new report is published. Regenerating
the wider catalog or discovering newer versions is a separate observation.
