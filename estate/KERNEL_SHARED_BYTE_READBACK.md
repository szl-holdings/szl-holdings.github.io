# Kernel Hub shared-path byte readback

The [report](kernel-shared-byte-readback.json) is a dated, anonymous read of 14
Kernel Hub distributions and their same-ID model mirrors. Pair identities and
revisions came from the [public distribution manifest](kernel-distributions.json)
at site commit `dccee6aeda928aa24f40a8a1e568ad58bb925e67` (manifest SHA-256
`298466da9f5d8102e65017bbc9919f5de308c025e4cb164522181a063c6190f7`).
The complete report SHA-256 is
`11e13d26297287644a71153c13a3d9265d0930ed4b0241473a0e34108c8777ed`.

The collector read complete, terminal-paginated file trees at those immutable
revisions. For each path present in both trees, it downloaded both raw files,
checked each length and Git blob OID against that tree, and compared SHA-256
and length. It fetched 1,616,218 bytes across 125 measurable shared paths in
13 pairs: **61 equal, 64 different**. The trees expose 158 shared paths in all.
The remaining 33 are in one pair whose model mirror, `szl-lambda-gate`, was
marked `gated: manual` by the public model API. Anonymous byte comparison for
that pair is **UNAVAILABLE**; the report retains its tree metadata and makes
no byte-match claim for those paths.

The comparison is limited to *identically named files* at the pinned revisions.
Kernel-only and model-only paths are listed separately. No whole repository or
artifact equivalence was established: **UNKNOWN**. Imports, numerical replay,
timing, energy, model evaluation, and independent replay were **NOT RUN**.
The per-file hashes are unsigned local observations. The source manifest and
report hashes bind the published exhibit but do not authenticate an independent
witness or authorize production use (**BLOCKED**).

The report records SHA-256 of each tree's length-framed HTTP response pages,
along with page counts and terminal pagination. Tree-response digests can
change if the Hub changes response formatting; the per-file length, Git blob
OID, and measured SHA-256 are the byte comparison. Current model API metadata
is recorded only to explain public access. It does not replace the manifest's
pinned mirror revision.

To check the committed report without network access:

```sh
python scripts/verify_kernel_shared_bytes.py --check
python -m unittest discover -s tests -p test_verify_kernel_shared_bytes.py -v
```

`--check` binds the complete report bytes to the SHA-256 above, validates its
source and internal scope, and does **not** re-download files. To collect a new
anonymous observation, use a *new* output path:

```sh
python scripts/verify_kernel_shared_bytes.py --output path/to/new-readback.json
```

The collector limits response sizes, same-host redirects, tree pagination, and
per-file downloads. It does not load or execute Hub code. A new observation has
a new timestamp and report digest and needs a new review before replacing this
public exhibit.
