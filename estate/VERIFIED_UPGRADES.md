# Measured upgrade cards

The [estate page](index.html) contains a static section built from
[verified-upgrades.json](verified-upgrades.json). The JSON is a **closed public
projection**. Each row requires literal `private: false`; allowed fields, source
identities, immutable revisions, denominators, artifact bytes, digests and status
boundaries are checked before rendering. The renderer escapes links and adds no
browser script, network request or new catalog asset row.

The receipt entry names the merged `szl-receipt` source commit and main CI run
that passed 535 tests, 12 subtests and 12 SAMPLE verifier cases with zero
mismatches. Its fixture signer remains REPO_DECLARED and its production
authorization remains BLOCKED.

The optional ReceiptAgent v2 entry is admitted only for the exact immutable
Hub adapter digest and size plus a source revision, with three checked custom
Ed25519 receipts. The local snapshot's provider origin is DECLARED. That gate
measures adapter and receipt integrity; it does not
rerun held-out evaluations, establish independent signer identity, authorize
autonomous action or certify model quality. Its model remains proposal-only.

The PyPI archive card binds a dated public package manifest to a per-file
[byte readback](pypi-artifact-byte-readback.json). The verifier streamed all 40
listed wheel and source archives as opaque bytes and matched their PyPI-declared
SHA-256 and lengths (1,632,195 bytes in total). The [replay scope](PYPI_ARTIFACT_READBACK.md)
keeps GitHub source-to-package binding and attestation signature verification
UNKNOWN; installation, extraction and independent replay were NOT RUN. This
does not authorize production use or establish package behavior.

Regenerate and check the committed page:

```sh
python scripts/build_verified_upgrades.py
python scripts/build_verified_upgrades.py --check
python -m unittest discover -s tests -p test_verified_upgrades.py -v
```

The source snapshot catalogs keep their separately dated revisions. A card's
fresh measurement does not rewrite old catalog observations or claim all models,
kernels or packages were replayed. The local research census and private rows
remain outside this public site.
