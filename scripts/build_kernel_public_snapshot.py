#!/usr/bin/env python3
"""Project the separately enumerated public Kernel Hub namespace, entirely offline.

Requires a hash-pinned private enumeration receipt, complete terminal pagination,
and the exact namespace/model inventory bytes bound by that receipt. Raw paths,
private records, diagnostics, files and principals never enter the public result.
The output counts distribution surfaces separately; it does not create model SKUs
or attest byte parity, execution, quality, timing, energy or scientific validity.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "szl.public-kernel-distributions/v1"
RECEIPT_SCHEMA = "szl.hf-public-kernel-enumeration-receipt/v1"
REQUEST_URL = "https://huggingface.co/api/kernels?author=SZLHOLDINGS&limit=100&full=true"
ID = re.compile(r"SZLHOLDINGS/[A-Za-z0-9_.-]+\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
FIELDS = frozenset({"id", "revision", "private", "sourceUrl", "url", "modelMirrorRevision",
                    "modelMirrorSourceUrl", "parity"})
LIMITATIONS = (
    "MEASURED enumeration and source-byte validation are metadata observations; kernel imports, numerical replay, timing, energy, quality and independent evaluation NOT RUN.",
    "Public Kernel Hub distribution surfaces are counted separately from model repositories. Same-ID distribution and model surfaces are not additional model SKUs.",
    "Kernel and model mirror revisions are separate metadata. Revision agreement does not establish byte parity; parity remains UNKNOWN without a separate byte attestation.",
    "Anonymous public namespace enumeration excludes private distributions. Missing or nonpublic model mirror links remain unset.",
    "Unsigned local receipt and hash validation do not authenticate the collector or provide an independent witness.",
)


def observed_datetime(value: object) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", value):
        raise ValueError("Kernel observation requires an explicit ISO 8601 UTC timestamp")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.utcoffset() != timedelta(0):
        raise ValueError("Kernel observation must use UTC")
    return stamp


def canonical_id(value: object) -> str:
    if (not isinstance(value, str) or not ID.fullmatch(value)
            or value.split("/")[1] in {".", ".."}):
        raise ValueError("Kernel source ID must belong to canonical SZLHOLDINGS namespace")
    return value


def exact_revision(value: object) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError("Kernel and model revisions require exact 40-character lowercase source SHAs")
    return value


def parse_json(raw: bytes, label: str) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key in bound {label}")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid bound {label} JSON") from error


def build_snapshot(kernels: list[dict], mirrors: list[dict], observed_at: str) -> dict:
    """Construct only public immutable links; matching SHAs do not attest parity."""
    observed_datetime(observed_at)
    if not isinstance(kernels, list) or not all(isinstance(row, dict) for row in kernels):
        raise ValueError("Kernel namespace inventory must be a list of objects")
    if not isinstance(mirrors, list) or not all(isinstance(row, dict) for row in mirrors):
        raise ValueError("Model mirror inventory must be a list of objects")
    model_by_id = {}
    for row in mirrors:
        if row.get("private") is not False or row.get("kind") != "HF Model":
            continue
        source_id = canonical_id(row.get("id"))
        if source_id in model_by_id:
            raise ValueError("Duplicate public model mirror identity")
        model_by_id[source_id] = exact_revision(row.get("revision"))
    distributions = []
    seen = set()
    for row in kernels:
        if row.get("private") is not False:
            continue
        source_id = canonical_id(row.get("id"))
        if source_id in seen:
            raise ValueError("Duplicate public Kernel Hub distribution identity")
        seen.add(source_id)
        revision = exact_revision(row.get("sha"))
        model_revision = model_by_id.get(source_id)
        url = "https://huggingface.co/kernels/" + source_id
        distributions.append({
            "id": source_id, "revision": revision, "private": False,
            "url": url, "sourceUrl": url + "/tree/" + revision,
            "modelMirrorRevision": model_revision,
            "modelMirrorSourceUrl": ("https://huggingface.co/" + source_id + "/tree/" + model_revision
                                     if model_revision is not None else None),
            "parity": "UNKNOWN",
        })
    distributions.sort(key=lambda row: (row["id"].casefold(), row["id"]))
    return {"schema": SCHEMA, "observed_at": observed_at, "limitations": list(LIMITATIONS),
            "distributions": distributions}


def load_bound_namespace(audit_dir: Path, *, receipt_path: Path | None = None,
                         receipt_sha256: str, now: datetime | None = None) -> dict:
    """Verify each input once and parse those verified bytes, without network IO."""
    audit_root = audit_dir.resolve()
    receipt_path = (receipt_path if receipt_path is not None else
                    audit_root / "execution" / "hf-contract-preflight" / "kernel-enumeration-receipt.json").resolve()
    if not receipt_path.is_relative_to(audit_root):
        raise ValueError("Kernel enumeration receipt must stay within the named audit root")
    if not isinstance(receipt_sha256, str) or not DIGEST.fullmatch(receipt_sha256):
        raise ValueError("Explicit kernel receipt SHA-256 is required")
    receipt_bytes = receipt_path.read_bytes()
    if hashlib.sha256(receipt_bytes).hexdigest() != receipt_sha256:
        raise ValueError("Kernel enumeration receipt SHA-256 mismatch")
    receipt = parse_json(receipt_bytes, "kernel enumeration receipt")
    if (not isinstance(receipt, dict) or receipt.get("schema") != RECEIPT_SCHEMA
            or receipt.get("evidence_class") != "MEASURED" or receipt.get("authentication") != "ANONYMOUS"
            or receipt.get("request_url") != REQUEST_URL
            or type(receipt.get("http_status")) is not int or receipt["http_status"] != 200
            or receipt.get("pagination_complete") is not True
            or "terminal_link_header" not in receipt or receipt["terminal_link_header"] is not None
            or "next" not in receipt or receipt["next"] is not None):
        raise ValueError("Complete canonical anonymous Kernel Hub enumeration and terminal pagination required")
    observed_at = receipt.get("observed_at")
    if observed_datetime(observed_at) > (now if now is not None else datetime.now(timezone.utc)):
        raise ValueError("Kernel observation timestamp is in the future")
    used_paths = {receipt_path}

    def verified_input(path_key: str, digest_key: str) -> bytes:
        name, digest = receipt.get(path_key), receipt.get(digest_key)
        if not isinstance(name, str) or not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            raise ValueError("Bound kernel input path and SHA-256 required")
        path = Path(name)
        target = (path if path.is_absolute() else audit_root / path).resolve()
        if not target.is_relative_to(audit_root) or target in used_paths:
            raise ValueError("Kernel input paths must be distinct and stay within the named audit root")
        used_paths.add(target)
        raw = target.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Bound kernel input SHA-256 mismatch")
        return raw

    raw_bytes = verified_input("raw_inventory_path", "raw_inventory_sha256")
    mirror_bytes = verified_input("model_mirror_inventory_path", "model_mirror_inventory_sha256")
    if type(receipt.get("raw_inventory_bytes")) is not int or receipt["raw_inventory_bytes"] != len(raw_bytes):
        raise ValueError("Bound Kernel Hub inventory byte length mismatch")
    kernels = parse_json(raw_bytes, "kernel namespace")
    raw_mirrors = parse_json(mirror_bytes, "model mirror inventory")
    if (not isinstance(kernels, list) or not all(isinstance(row, dict) for row in kernels)
            or not isinstance(raw_mirrors, list) or not all(isinstance(row, dict) for row in raw_mirrors)):
        raise ValueError("Bound namespace and mirror inventories must be object lists")
    if type(receipt.get("rows")) is not int or receipt["rows"] != len(kernels) or not 0 <= len(kernels) <= 100:
        raise ValueError("Bound kernel count conflicts with the recorded terminal request")
    mirrors = [{"id": row.get("id"), "kind": "HF Model", "private": row.get("private"),
                "revision": row.get("sha")} for row in raw_mirrors if row.get("type") == "model"]
    snapshot = build_snapshot(kernels, mirrors, observed_at)
    mappings = receipt.get("same_id_revision_mapping")
    if not isinstance(mappings, list) or not all(isinstance(row, dict) for row in mappings):
        raise ValueError("Kernel and model revision mapping observation required")
    mapping_by_id = {}
    for row in mappings:
        source_id = canonical_id(row.get("id"))
        if source_id in mapping_by_id:
            raise ValueError("Duplicate observed kernel/model mapping identity")
        mapping_by_id[source_id] = row
    model_rows = {row.get("id"): row for row in raw_mirrors if row.get("type") == "model"
                  and isinstance(row.get("id"), str)}
    if set(mapping_by_id) != {row["id"] for row in snapshot["distributions"]}:
        raise ValueError("Observed kernel/model mapping coverage conflicts with public namespace")
    for row in snapshot["distributions"]:
        mapping = mapping_by_id[row["id"]]
        mirror = model_rows.get(row["id"])
        expected_mirror_revision = mirror.get("sha") if mirror else None
        expected_mirror_private = mirror.get("private") if mirror else None
        if (mapping.get("kernel_revision") != row["revision"] or mapping.get("private") is not False
                or mapping.get("model_mirror_revision") != expected_mirror_revision
                or mapping.get("model_mirror_private") is not expected_mirror_private
                or mapping.get("parity") != "UNKNOWN"):
            raise ValueError("Observed kernel/model mapping does not match verified inventory bytes")
    return snapshot


def validate_snapshot(snapshot: dict) -> None:
    if not isinstance(snapshot, dict) or set(snapshot) != {"schema", "observed_at", "limitations", "distributions"}:
        raise ValueError("Public kernel snapshot field allowlist mismatch")
    rows = snapshot["distributions"]
    if not isinstance(rows, list) or not all(isinstance(row, dict) and set(row) == FIELDS for row in rows):
        raise ValueError("Public kernel distribution field allowlist mismatch")
    if any(row["private"] is not False for row in rows):
        raise ValueError("Public kernel distributions require literal public visibility")
    kernels = [{"id": row["id"], "sha": row["revision"], "private": False} for row in rows]
    mirrors = [{"id": row["id"], "kind": "HF Model", "revision": row["modelMirrorRevision"],
                "private": False} for row in rows if row["modelMirrorRevision"] is not None]
    if snapshot != build_snapshot(kernels, mirrors, snapshot["observed_at"]):
        raise ValueError("Public kernel links, revisions, metadata limits or UNKNOWN parity conflict")


def render_distributions(snapshot: dict) -> str:
    validate_snapshot(snapshot)
    escape = lambda value: html.escape(value, quote=True)
    rows = snapshot["distributions"]
    cards = []
    for row in rows:
        mirror = (f'<a href="{escape(row["modelMirrorSourceUrl"])}" target="_blank" rel="noopener noreferrer">Same-ID model mirror source</a>'
                  f' <code>{escape(row["modelMirrorRevision"])}</code>'
                  if row["modelMirrorSourceUrl"] is not None else 'Model mirror source UNKNOWN or nonpublic; link unset.')
        cards.append(
            '<article class="asset kernel-distribution">\n'
            f'  <h3><a class="kernel-source" href="{escape(row["sourceUrl"])}" target="_blank" rel="noopener noreferrer">{escape(row["id"])}</a></h3>\n'
            f'  <p>Kernel distribution revision <code>{escape(row["revision"])}</code></p>\n'
            f'  <p>{mirror}</p>\n  <p>Byte parity: <strong>UNKNOWN</strong>. Runtime behavior NOT RUN.</p>\n'
            '</article>'
        )
    limits = "".join(f'<li>{escape(limit)}</li>' for limit in snapshot["limitations"])
    stamp = escape(snapshot["observed_at"])
    return ('\n<section class="kernel-distributions" aria-labelledby="estate-kernels-title">\n'
            '  <h2 id="estate-kernels-title">Kernel Hub distributions</h2>\n'
            f'  <p>{len(rows)} public Kernel Hub distribution' + ('' if len(rows) == 1 else 's') +
            f' in a separate surface census, observed <time datetime="{stamp}">{stamp}</time>.</p>\n'
            '  <p><a href="kernel-distributions.json">Download the public kernel distribution snapshot</a></p>\n'
            f'  <ul class="limits">{limits}</ul>\n  <div class="grid">\n' + '\n'.join(cards) +
            '\n  </div>\n</section>\n')


def render_page(template: str, snapshot: dict) -> str:
    start, end = '<!-- estate-kernels:start -->', '<!-- estate-kernels:end -->'
    if template.count(start) != 1 or template.count(end) != 1:
        raise ValueError("Kernel page template requires unique start/end generation markers")
    content = render_distributions(snapshot)
    start_index = template.index(start) + len(start)
    end_index = template.index(end, start_index)
    return template[:start_index] + content + template[end_index:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True, help="Private audit root containing bound input files")
    parser.add_argument("--namespace-receipt", type=Path, help="Private enumeration receipt within audit root")
    parser.add_argument("--receipt-sha256", required=True, help="Explicit SHA-256 of the reviewed private receipt")
    parser.add_argument("--site-dir", type=Path, default=ROOT, help="Site checkout containing estate/index.html")
    args = parser.parse_args(argv)
    try:
        snapshot = load_bound_namespace(args.audit_dir, receipt_path=args.namespace_receipt,
                                        receipt_sha256=args.receipt_sha256)
        page_path = args.site_dir / "estate" / "index.html"
        page = render_page(page_path.read_text(encoding="utf-8"), snapshot)
        serialized = json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        # Validate every bound input and generation boundary before output writes.
        (args.site_dir / "estate" / "kernel-distributions.json").write_text(serialized, encoding="utf-8", newline="\n")
        page_path.write_text(page, encoding="utf-8", newline="\n")
    except (ValueError, OSError) as error:
        print(f"Public kernel snapshot build stopped: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"observed_at": snapshot["observed_at"], "public_kernel_distributions": len(snapshot["distributions"]),
                      "byte_parity": "UNKNOWN", "kernel_runtime": "NOT RUN"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
