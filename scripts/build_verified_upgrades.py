#!/usr/bin/env python3
"""Render a closed, public-only measured-upgrade section into static estate HTML."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "estate" / "verified-upgrades.json"
PAGE = ROOT / "estate" / "index.html"
START = "<!-- verified-upgrades:start -->"
END = "<!-- verified-upgrades:end -->"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
RECEIPT_REPO = "szl-holdings/szl-receipt"
FORGE_REPO = "szl-holdings/szl-forge"
FORGE_SOURCE_REVISION = "3a0c073bd8e46d40980254d37c608be8d16f07bd"
MODEL_REPO = "SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2"
MODEL_REVISION = "bd642c7ff18736248e84fd83dace7ab368fc2288"
MODEL_SHA256 = "885fc29fcb4cf55c280dc085fdb0a40f40d6b946fee400dd5e4ed3459fe6334f"
PYPI_SOURCE_REVISION = "7623a44f51af3c07a41e2f8dea81753a95a7edee"
PYPI_MANIFEST_SHA256 = "ff80979ded90364bc3122cc7b98c2fa51ec6578e6b5f98c4f973b17e119cc2a4"
PYPI_REPORT_SHA256 = "aac6abfffcafaf5ebf1b6d892926b7bac9adc0489b63c68159ee0e47a5d2a6da"
PYPI_REPORT = ROOT / "estate" / "pypi-artifact-byte-readback.json"


def _read_json(raw: bytes) -> dict:
    def unique(pairs: list[tuple[str, object]]) -> dict:
        result: dict = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate public evidence key")
            result[key] = value
        return result
    result = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(result, dict):
        raise ValueError("public evidence must be an object")
    return result


def _sha(value: object, width: int) -> str:
    pattern = SHA40 if width == 40 else SHA64
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError("expected immutable hexadecimal digest")
    return value


def _nonnegative(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("count must be a nonnegative integer")
    return value


def validate(document: dict) -> list[dict]:
    if set(document) != {"schema", "observed_at", "entries"} or document["schema"] != "szl.public-verified-upgrades/v1":
        raise ValueError("public evidence schema mismatch")
    observed = document["observed_at"]
    if not isinstance(observed, str):
        raise ValueError("missing observation time")
    when = datetime.fromisoformat(observed.replace("Z", "+00:00"))
    if when.tzinfo is None or when > datetime.now(timezone.utc):
        raise ValueError("invalid observation time")
    entries = document["entries"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 3:
        raise ValueError("unexpected evidence count")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("private") is not False:
            raise ValueError("only literal public evidence is allowed")
        kind = entry.get("kind")
        if kind == "receipt":
            fields = {"private", "id", "kind", "evidence_class", "source_repository", "source_revision",
                      "ci_run_id", "test_count", "subtest_count", "sample_case_count", "mismatch_count",
                      "key_trust", "production_authorization"}
            if set(entry) != fields or entry["id"] != "receipt-verifier" or entry["source_repository"] != RECEIPT_REPO:
                raise ValueError("receipt public field allowlist mismatch")
            _sha(entry["source_revision"], 40)
            if (entry["source_revision"] != "2761f9eaedde02de540a7aecf182290695affe4d"
                    or entry["ci_run_id"] != 37722208933):
                raise ValueError("receipt evidence source/run binding mismatch")
            for field in ("ci_run_id", "test_count", "subtest_count", "sample_case_count", "mismatch_count"):
                _nonnegative(entry[field])
            if (entry["test_count"], entry["subtest_count"], entry["sample_case_count"], entry["mismatch_count"]) != (535, 12, 12, 0):
                raise ValueError("receipt measured denominator mismatch")
        elif kind == "adapter":
            fields = {"private", "id", "kind", "evidence_class", "source_repository", "source_revision",
                      "hub_repository", "hub_revision", "adapter_bytes", "adapter_sha256",
                      "signed_receipts_verified", "signature_algorithm", "snapshot_origin", "key_trust",
                      "production_authorization", "publication_eligible", "held_out_evaluation_replay"}
            if set(entry) != fields or entry["id"] != "receipt-agent-v2-adapter" or entry["source_repository"] != FORGE_REPO:
                raise ValueError("adapter public field allowlist mismatch")
            _sha(entry["source_revision"], 40)
            _sha(entry["hub_revision"], 40)
            _sha(entry["adapter_sha256"], 64)
            if (entry["source_revision"] != FORGE_SOURCE_REVISION
                    or entry["hub_repository"] != MODEL_REPO or entry["hub_revision"] != MODEL_REVISION
                    or entry["adapter_sha256"] != MODEL_SHA256 or entry["adapter_bytes"] != 43346432
                    or entry["signed_receipts_verified"] != 3 or entry["signature_algorithm"] != "Ed25519"
                    or entry["snapshot_origin"] != "DECLARED"
                    or entry["publication_eligible"] is not False or entry["held_out_evaluation_replay"] != "NOT RUN"):
                raise ValueError("adapter measured byte/profile binding mismatch")
        elif kind == "pypi":
            fields = {"private", "id", "kind", "evidence_class", "source_repository", "source_revision",
                      "source_manifest_sha256", "readback_sha256", "package_count", "artifact_count",
                      "matched_count", "measured_total_bytes", "source_package_binding",
                      "attestation_signature_verification", "installation", "extraction", "independent_replay",
                      "production_authorization"}
            if (set(entry) != fields or entry["id"] != "pypi-archive-byte-readback"
                    or entry["source_repository"] != "szl-holdings/szl-holdings.github.io"):
                raise ValueError("PyPI public field allowlist mismatch")
            _sha(entry["source_revision"], 40)
            _sha(entry["source_manifest_sha256"], 64)
            _sha(entry["readback_sha256"], 64)
            if (entry["source_revision"] != PYPI_SOURCE_REVISION
                    or entry["source_manifest_sha256"] != PYPI_MANIFEST_SHA256
                    or entry["readback_sha256"] != PYPI_REPORT_SHA256
                    or hashlib.sha256(PYPI_REPORT.read_bytes()).hexdigest() != PYPI_REPORT_SHA256):
                raise ValueError("PyPI readback source or report bytes differ")
            report = _read_json(PYPI_REPORT.read_bytes())
            if any(entry[field] != report[field] for field in ("package_count", "artifact_count", "matched_count", "measured_total_bytes",
                                                                  "source_package_binding", "attestation_signature_verification",
                                                                  "installation", "extraction", "independent_replay")):
                raise ValueError("PyPI public summary differs from measured report")
            if (entry["package_count"], entry["artifact_count"], entry["matched_count"], entry["measured_total_bytes"]) != (20, 40, 40, 1632195):
                raise ValueError("PyPI byte-readback denominator mismatch")
            if (entry["source_package_binding"] != "UNKNOWN" or entry["attestation_signature_verification"] != "UNKNOWN"
                    or any(entry[field] != "NOT RUN" for field in ("installation", "extraction", "independent_replay"))):
                raise ValueError("PyPI byte-readback boundary mismatch")
        else:
            raise ValueError("unsupported public evidence kind")
        if (entry["id"] in seen or entry["evidence_class"] != "MEASURED"
                or (kind != "pypi" and entry["key_trust"] != "REPO_DECLARED")
                or entry["production_authorization"] != "BLOCKED"):
            raise ValueError("public evidence boundary mismatch")
        seen.add(entry["id"])
    if "receipt-verifier" not in seen:
        raise ValueError("receipt evidence missing")
    return entries


def render(entries: list[dict]) -> str:
    lines = [
        '<section class="research-exhibits" aria-labelledby="verified-upgrades-title">',
        '  <p class="eyebrow">Measured upgrades · exact source links</p>',
        '  <h2 id="verified-upgrades-title">Recheck the bytes behind the work</h2>',
        '  <p class="intro">These results cover named tests and artifacts at fixed revisions. Each card names what was measured and the authority it does not grant. <a href="verified-upgrades.json">Read the public evidence data</a> and <a href="VERIFIED_UPGRADES.md">its replay scope</a>.</p>',
        '  <div class="grid">',
    ]
    for row in entries:
        source = "https://github.com/" + row["source_repository"] + "/tree/" + row["source_revision"]
        if row["kind"] == "receipt":
            evidence = f"https://github.com/{RECEIPT_REPO}/actions/runs/{row['ci_run_id']}"
            lines += [
                '    <article class="asset" id="upgrade-receipt-verifier">',
                '      <p class="asset-kind">Receipt verification · MEASURED on SAMPLE inputs</p>',
                '      <h3>12 cases across signature, artifact and source checks</h3>',
                f'      <p>At the merged source revision, {row["test_count"]} tests and {row["subtest_count"]} subtests passed. The strict benchmark recorded {row["sample_case_count"]} SAMPLE cases and {row["mismatch_count"]} mismatches. Downloaded CI artifacts were checked against their provider digests.</p>',
                f'      <p><a href="{html.escape(source, quote=True)}">Source at commit</a> · <a href="{html.escape(evidence, quote=True)}">Main CI run</a> · <a href="https://github.com/{RECEIPT_REPO}/blob/{row["source_revision"]}/conformance/README.md">Replay instructions</a></p>',
                '      <p class="exhibit-limit">Fixture key trust: REPO_DECLARED. Production authorization: BLOCKED. Independent external replay NOT RUN.</p>',
                '    </article>',
            ]
        elif row["kind"] == "adapter":
            hub = f"https://huggingface.co/{MODEL_REPO}/tree/{row['hub_revision']}"
            lines += [
                '    <article class="asset" id="upgrade-receipt-agent-v2-adapter">',
                '      <p class="asset-kind">Proposal-only model artifact · MEASURED bytes</p>',
                '      <h3>ReceiptAgent v2 adapter: exact byte check</h3>',
                f'      <p>{row["adapter_bytes"]:,} opaque adapter bytes matched SHA-256 <code>{row["adapter_sha256"]}</code>. Three Ed25519 receipt signatures and their declared links verified with Forge and OpenSSL at the pinned release revision.</p>',
                f'      <p><a href="{html.escape(source, quote=True)}">Forge source at commit</a> · <a href="{html.escape(hub, quote=True)}">Immutable Hub files</a> · <a href="https://github.com/{FORGE_REPO}/blob/{row["source_revision"]}/docs/published-artifact-byte-verification.md">Replay instructions</a></p>',
                '      <p class="exhibit-limit">Snapshot origin: DECLARED; key trust: REPO_DECLARED. Held-out evaluation replay NOT RUN. Publication eligibility false; production authorization BLOCKED. This check covers one adapter and its declared receipts.</p>',
                '    </article>',
            ]
        else:
            manifest = f"https://github.com/{row['source_repository']}/blob/{row['source_revision']}/estate/pypi-packages.json"
            lines += [
                '    <article class="asset" id="upgrade-pypi-archive-byte-readback">',
                '      <p class="asset-kind">Public PyPI archives · MEASURED bytes</p>',
                '      <h3>40 archive files matched the dated PyPI manifest</h3>',
                f'      <p>All {row["matched_count"]} listed wheel and source archives across {row["package_count"]} packages matched their provider-declared SHA-256 and byte lengths. The streamed opaque files totaled {row["measured_total_bytes"]:,} bytes.</p>',
                f'      <p><a href="{html.escape(manifest, quote=True)}">Pinned public manifest</a> · <a href="pypi-artifact-byte-readback.json">Per-file readback</a> · <a href="PYPI_ARTIFACT_READBACK.md">Replay scope</a></p>',
                '      <p class="exhibit-limit">GitHub source-to-package binding: UNKNOWN. PyPI attestation signature verification: UNKNOWN. Install, extract and independent replay: NOT RUN. Production authorization: BLOCKED.</p>',
                '    </article>',
            ]
    lines += ['  </div>', '</section>']
    return "\n".join(lines)


def generate(page: str, document: dict) -> str:
    entries = validate(document)
    if page.count(START) != 1 or page.count(END) != 1:
        raise ValueError("page must contain exactly one generated evidence region")
    prefix, rest = page.split(START, 1)
    _old, suffix = rest.split(END, 1)
    rendered = render(entries)
    if "\r\n" in page:
        rendered = rendered.replace("\n", "\r\n")
        newline = "\r\n"
    else:
        newline = "\n"
    return prefix + START + newline + rendered + newline + END + suffix


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    page = PAGE.read_bytes().decode("utf-8")
    updated = generate(page, _read_json(DATA.read_bytes()))
    if args.check:
        if updated != page:
            raise SystemExit("verified upgrade section differs from public evidence; rebuild")
        print("public evidence section matches closed source")
        return 0
    if updated != page:
        PAGE.write_bytes(updated.encode("utf-8"))
    print("public evidence section built")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
