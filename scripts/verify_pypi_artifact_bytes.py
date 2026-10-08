#!/usr/bin/env python3
"""Stream pinned public PyPI archives as opaque bytes; never install or extract."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from build_pypi_public_snapshot import parse_json, validate_snapshot

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "estate" / "pypi-packages.json"
REPORT = ROOT / "estate" / "pypi-artifact-byte-readback.json"
SOURCE_REVISION = "7623a44f51af3c07a41e2f8dea81753a95a7edee"
MANIFEST_SHA256 = "ff80979ded90364bc3122cc7b98c2fa51ec6578e6b5f98c4f973b17e119cc2a4"
MAX_ARTIFACT_BYTES = 5_000_000
MAX_TOTAL_BYTES = 20_000_000
SCHEMA = "szl.public-pypi-artifact-byte-readback/v1"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_blob(path: str) -> bytes:
    result = subprocess.run(["git", "-C", str(ROOT), "show", f"{SOURCE_REVISION}:{path}"],
                            capture_output=True, timeout=20, check=True)
    return result.stdout


def pinned_manifest() -> dict:
    # This is a historical, immutable input. A newer public catalog may carry
    # different PyPI metadata without invalidating this dated byte observation.
    raw = git_blob("estate/pypi-packages.json")
    if sha(raw) != MANIFEST_SHA256:
        raise ValueError("PyPI input differs from pinned source bytes")
    # Source attribution is historical. A later catalog refresh must not
    # silently rewrite this byte-readback's 7 October input scope.
    source_raw = git_blob("estate/public-snapshot.json")
    manifest = parse_json(raw, "snapshot")
    sources = parse_json(source_raw, "GitHub source inventory")
    if not isinstance(sources, dict) or not isinstance(sources.get("assets"), list):
        raise ValueError("public source inventory is missing assets")
    validate_snapshot(manifest, sources["assets"])
    return manifest


def expected_rows(manifest: dict) -> list[dict]:
    rows = []
    for package in manifest["packages"]:
        for artifact in package["artifacts"]:
            if artifact["bytes"] > MAX_ARTIFACT_BYTES:
                raise ValueError("artifact exceeds bounded opaque byte read")
            rows.append({
                "package_name": package["package_name"], "version": package["version"],
                "filename": artifact["filename"], "url": artifact["url"],
                "declared_sha256": artifact["sha256"], "declared_bytes": artifact["bytes"],
            })
    rows.sort(key=lambda row: (row["package_name"], row["filename"]))
    if sum(row["declared_bytes"] for row in rows) > MAX_TOTAL_BYTES:
        raise ValueError("total opaque byte read exceeds bound")
    return rows


class RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def open_exact(request: Request):
    return build_opener(RejectRedirect).open(request, timeout=20)


def stream_one(row: dict) -> dict:
    """A URL check and streaming digest only. No archive parser is invoked."""
    request = Request(row["url"], headers={"User-Agent": "szl-pypi-byte-readback/1",
                                           "Accept-Encoding": "identity"})
    with open_exact(request) as response:
        if response.status != 200 or response.url != row["url"]:
            raise ValueError("artifact response target or status changed")
        declared_length = response.headers.get("Content-Length")
        if declared_length is not None and int(declared_length) != row["declared_bytes"]:
            raise ValueError("artifact response length differs from pinned declaration")
        measured = hashlib.sha256()
        count = 0
        while block := response.read(65536):
            count += len(block)
            if count > row["declared_bytes"] or count > MAX_ARTIFACT_BYTES:
                raise ValueError("artifact stream exceeded pinned byte bound")
            measured.update(block)
    return {**row, "measured_sha256": measured.hexdigest(), "measured_bytes": count,
            "http_status": 200,
            "status": "MATCH" if count == row["declared_bytes"] and measured.hexdigest() == row["declared_sha256"] else "MISMATCH"}


def collect(manifest: dict) -> dict:
    expected = expected_rows(manifest)
    results = []
    for row in expected:
        try:
            results.append(stream_one(row))
        except (HTTPError, URLError, OSError, TimeoutError) as error:
            results.append({**row, "measured_sha256": None, "measured_bytes": None,
                            "http_status": getattr(error, "code", None), "status": "UNAVAILABLE"})
        except (ValueError, OverflowError):
            results.append({**row, "measured_sha256": None, "measured_bytes": None,
                            "http_status": None, "status": "BLOCKED"})
    matched = sum(row["status"] == "MATCH" for row in results)
    state = "MEASURED" if matched == len(expected) else ("BLOCKED" if any(row["status"] in {"MISMATCH", "BLOCKED"} for row in results) else "UNAVAILABLE")
    return {
        "schema": SCHEMA, "observed_at": datetime.now(timezone.utc).isoformat(),
        "evidence_class": state, "scope": "PINNED_2026_10_07_PUBLIC_PYPI_ARTIFACTS_ONLY",
        "source_revision": SOURCE_REVISION, "source_manifest_sha256": MANIFEST_SHA256,
        "source_manifest_observed_at": manifest["generated_at"],
        "package_count": len(manifest["packages"]), "artifact_count": len(expected),
        "matched_count": matched, "declared_total_bytes": sum(row["declared_bytes"] for row in expected),
        "measured_total_bytes": sum(row["measured_bytes"] or 0 for row in results),
        "source_package_binding": "UNKNOWN", "attestation_signature_verification": "UNKNOWN",
        "installation": "NOT RUN", "extraction": "NOT RUN", "independent_replay": "NOT RUN",
        "artifacts": results,
    }


def validate_report(report: dict, manifest: dict) -> None:
    fields = {"schema", "observed_at", "evidence_class", "scope", "source_revision",
              "source_manifest_sha256", "source_manifest_observed_at", "package_count",
              "artifact_count", "matched_count", "declared_total_bytes", "measured_total_bytes",
              "source_package_binding", "attestation_signature_verification", "installation",
              "extraction", "independent_replay", "artifacts"}
    if not isinstance(report, dict) or set(report) != fields or report["schema"] != SCHEMA:
        raise ValueError("PyPI byte-readback report schema mismatch")
    observed = datetime.fromisoformat(report["observed_at"].replace("Z", "+00:00"))
    source_observed = datetime.fromisoformat(manifest["generated_at"].replace("Z", "+00:00"))
    if (observed.tzinfo is None or observed.utcoffset() != timezone.utc.utcoffset(observed)
            or observed < source_observed or observed > datetime.now(timezone.utc)):
        raise ValueError("invalid readback observation time")
    if (report["evidence_class"] != "MEASURED" or report["scope"] != "PINNED_2026_10_07_PUBLIC_PYPI_ARTIFACTS_ONLY"
            or report["source_revision"] != SOURCE_REVISION or report["source_manifest_sha256"] != MANIFEST_SHA256
            or report["source_manifest_observed_at"] != manifest["generated_at"]
            or report["source_package_binding"] != "UNKNOWN"
            or report["attestation_signature_verification"] != "UNKNOWN"
            or any(report[key] != "NOT RUN" for key in ("installation", "extraction", "independent_replay"))):
        raise ValueError("PyPI byte-readback boundary mismatch")
    expected = expected_rows(manifest)
    actual = report["artifacts"]
    if not isinstance(actual, list) or len(actual) != len(expected):
        raise ValueError("PyPI byte-readback artifact coverage mismatch")
    for observed_row, expected_row in zip(actual, expected):
        if (not isinstance(observed_row, dict) or set(observed_row) != set(expected_row) | {"measured_sha256", "measured_bytes", "http_status", "status"}
                or any(observed_row[key] != value for key, value in expected_row.items())
                or observed_row["measured_sha256"] != expected_row["declared_sha256"]
                or observed_row["measured_bytes"] != expected_row["declared_bytes"]
                or observed_row["http_status"] != 200 or observed_row["status"] != "MATCH"):
            raise ValueError("PyPI byte-readback artifact differs from pinned declaration")
    total = sum(row["declared_bytes"] for row in expected)
    if (type(report["package_count"]) is not int or report["package_count"] != len(manifest["packages"])
            or type(report["artifact_count"]) is not int or report["artifact_count"] != len(expected)
            or type(report["matched_count"]) is not int or report["matched_count"] != len(expected)
            or type(report["declared_total_bytes"]) is not int or report["declared_total_bytes"] != total
            or type(report["measured_total_bytes"]) is not int or report["measured_total_bytes"] != total):
        raise ValueError("PyPI byte-readback totals mismatch")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate committed report offline")
    parser.add_argument("--output", type=Path, help="Fresh output path for a live provider read; --check defaults to the committed report")
    args = parser.parse_args()
    manifest = pinned_manifest()
    if args.check:
        report = parse_json((args.output or REPORT).read_bytes(), "artifact byte readback")
        validate_report(report, manifest)
        print(f"offline report matches {len(manifest['packages'])} packages and {len(report['artifacts'])} pinned artifacts")
        return 0
    if args.output is None:
        parser.error("a fresh --output path is required for live provider reads")
    output = args.output.resolve()
    if output in {MANIFEST.resolve(), Path(__file__).resolve()}:
        raise ValueError("readback output cannot overwrite a source input")
    if output.exists():
        raise ValueError("readback output already exists; preserve it and choose a fresh path")
    report = collect(manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        handle.write((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: report[key] for key in ("evidence_class", "package_count", "artifact_count", "matched_count", "measured_total_bytes")}))
    return 0 if report["evidence_class"] == "MEASURED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
