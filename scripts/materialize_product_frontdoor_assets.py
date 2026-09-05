#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Materialize A11oy's governed visual shell into the static company origin.

The custom-domain front door is a separate GitHub Pages deployment rail from
A11oy's Hugging Face runtime. This tool copies the current source-controlled
Spectral/Flow assets into that static rail, binds them to an exact source SHA and
SHA-256 digest, and injects one idempotent local-only asset block into the root
HTML document. It performs no DNS, Cloudflare, provider-secret, or runtime API
mutation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "szl.product-frontdoor-assets/v1"
START = "<!-- SZL-PRODUCT-FRONTDOOR-ASSETS-V2:START -->"
END = "<!-- SZL-PRODUCT-FRONTDOOR-ASSETS-V2:END -->"
BLOCK = "\n".join(
    (
        START,
        '<link rel="stylesheet" href="/assets/szl-spectral-v2.css" data-szl-product-asset="spectral-v2" />',
        '<script src="/assets/szl-flow-v2.js" defer data-szl-product-asset="flow-v2"></script>',
        END,
    )
)
CSS_DEST = Path("assets/szl-spectral-v2.css")
JS_DEST = Path("assets/szl-flow-v2.js")
MANIFEST = Path("assets/szl-product-frontdoor-assets-v2.json")
TARGET_ORIGIN = "https://holdings.a-11-oy.com"
CSS_CANDIDATES = (
    Path("console/assets/szl-spectral-v2.css"),
    Path("console/assets/szl-holo-v2.css"),
    Path("console/assets/szl-flow.css"),
)
JS_CANDIDATES = (
    Path("console/assets/szl-flow-v2.js"),
    Path("console/assets/szl-flow.js"),
    Path("static/shared/szl-holo-v2.js"),
    Path("console/assets/szl-holo-v2.js"),
)


class MaterializeError(RuntimeError):
    """Materialization or verification failed closed."""


def sha256(source: bytes) -> str:
    return hashlib.sha256(source).hexdigest()


def exact_source(root: Path, candidates: tuple[Path, ...], kind: str) -> Path:
    found = [path for path in candidates if (root / path).is_file()]
    if not found:
        raise MaterializeError(
            f"A11oy source contains no reviewed {kind} candidate: "
            + ", ".join(path.as_posix() for path in candidates)
        )
    return found[0]


def strip_existing_block(text: str) -> str:
    # Consume indentation inserted with the prior block as well as its trailing
    # line break. Leaving that indentation behind adds two spaces per apply.
    pattern = re.compile(
        r"[ \t]*" + re.escape(START) + r".*?" + re.escape(END) + r"[ \t]*(?:\r?\n)?",
        re.DOTALL,
    )
    return pattern.sub("", text)


def bind_index(index: Path) -> None:
    text = index.read_text(encoding="utf-8")
    if text.count(START) > 1 or text.count(END) > 1:
        raise MaterializeError("root document contains duplicate asset-block markers")
    text = strip_existing_block(text)
    head = text.lower().rfind("</head>")
    if head < 0:
        raise MaterializeError("root document has no closing head element")
    text = text[:head] + "  " + BLOCK + "\n" + text[head:]
    index.write_text(text, encoding="utf-8", newline="\n")


def materialize(target: Path, source: Path, source_sha: str) -> dict[str, object]:
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise MaterializeError("source SHA must be an exact 40-character hexadecimal commit")
    index = target / "index.html"
    if not index.is_file():
        raise MaterializeError("target static origin has no root index.html")

    css_source = exact_source(source, CSS_CANDIDATES, "Spectral CSS")
    js_source = exact_source(source, JS_CANDIDATES, "Flow JavaScript")
    css = (source / css_source).read_bytes()
    javascript = (source / js_source).read_bytes()
    if not css.strip() or not javascript.strip():
        raise MaterializeError("governed visual asset source is empty")
    if b"http://" in css or b"https://cdn" in css or b"unpkg.com" in css or b"jsdelivr" in css:
        raise MaterializeError("Spectral CSS introduces an external runtime dependency")
    if b"https://cdn" in javascript or b"unpkg.com" in javascript or b"jsdelivr" in javascript:
        raise MaterializeError("Flow JavaScript introduces an external runtime dependency")

    css_target = target / CSS_DEST
    js_target = target / JS_DEST
    css_target.parent.mkdir(parents=True, exist_ok=True)
    css_target.write_bytes(css)
    js_target.write_bytes(javascript)
    bind_index(index)

    manifest = {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_repository": "szl-holdings/a11oy",
        "source_revision": source_sha,
        "target_origin": TARGET_ORIGIN,
        "assets": {
            "/assets/szl-spectral-v2.css": {
                "source_path": css_source.as_posix(),
                "sha256": sha256(css),
                "bytes": len(css),
            },
            "/assets/szl-flow-v2.js": {
                "source_path": js_source.as_posix(),
                "sha256": sha256(javascript),
                "bytes": len(javascript),
            },
        },
        "claims": {
            "static_asset_materialized": True,
            "runtime_health": "NOT_CLAIMED",
            "dns_or_edge_changed": False,
            "token_value_recorded": False,
        },
    }
    (target / MANIFEST).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def validate(target: Path) -> dict[str, object]:
    manifest_path = target / MANIFEST
    if not manifest_path.is_file():
        raise MaterializeError("front-door asset manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA:
        raise MaterializeError("front-door asset manifest schema drifted")
    if manifest.get("target_origin") != TARGET_ORIGIN:
        raise MaterializeError(
            f"front-door asset manifest target origin must be {TARGET_ORIGIN}"
        )
    index = (target / "index.html").read_text(encoding="utf-8")
    if index.count(START) != 1 or index.count(END) != 1:
        raise MaterializeError("root document must contain one exact asset block")
    for url, metadata in (manifest.get("assets") or {}).items():
        relative = Path(str(url).lstrip("/"))
        path = target / relative
        if not path.is_file():
            raise MaterializeError(f"manifest asset is absent: {url}")
        source = path.read_bytes()
        if sha256(source) != metadata.get("sha256"):
            raise MaterializeError(f"manifest digest mismatch: {url}")
        if len(source) != metadata.get("bytes"):
            raise MaterializeError(f"manifest byte count mismatch: {url}")
        if str(url) not in index:
            raise MaterializeError(f"root document does not reference manifest asset: {url}")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=Path("."))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--source-sha")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    try:
        if args.check:
            manifest = validate(args.target)
            mode = "CHECK"
        else:
            if args.source is None or args.source_sha is None:
                raise MaterializeError("apply mode requires --source and --source-sha")
            manifest = materialize(args.target, args.source, args.source_sha)
            validate(args.target)
            mode = "APPLY"
        report = {
            "schema": SCHEMA,
            "mode": mode,
            "status": "PASS",
            "source_revision": manifest.get("source_revision"),
            "target_origin": manifest.get("target_origin"),
            "assets": manifest.get("assets"),
            "token_value_recorded": False,
        }
    except Exception as exc:
        report = {
            "schema": SCHEMA,
            "mode": "CHECK" if args.check else "APPLY",
            "status": "FAIL",
            "error": str(exc),
            "token_value_recorded": False,
        }
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True), file=sys.stderr)
        return 1

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
