#!/usr/bin/env python3
"""Join public membership, dated source snapshots and published PyPI metadata.

Offline only. Run after the repository/kernel snapshot generators. All six
distribution types share the existing filter script, without changing its CSP.
No source revision is upgraded to current-head, runtime or package equivalence.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import sys

from build_estate_public_snapshot import ASSET_FIELDS, exact_revision, observed_datetime, replace_once, replace_region
from build_kernel_public_snapshot import validate_snapshot as validate_kernels
from build_pypi_public_snapshot import validate_snapshot as validate_packages

ROOT = Path(__file__).resolve().parents[1]
KINDS = ("GitHub", "HF Model", "HF Dataset", "HF Space", "HF Kernel", "PyPI")
INPUTS = ("public-snapshot.json", "kernel-distributions.json", "pypi-packages.json", "catalog-membership.json")
MEMBERSHIP_SCHEMA = "szl.public-catalog-membership/v1"
LIMITATIONS = [
    "MEASURED anonymous public membership enumeration and PyPI metadata reads; not a live monitor or independent witness.",
    "Repository and kernel source states retain their separate snapshot dates. They are not a fresh default-head CI or runtime claim.",
    "Kernel and PyPI distributions are separate surfaces, not additional trained models or unique projects.",
    "PyPI attribution and artifact hashes are DECLARED provider metadata. Package/source equivalence remains UNKNOWN; installation and imports NOT RUN.",
    "Model inference, training, dataset rows, numerical replay, performance, energy and independent evaluation NOT RUN.",
    "Models propose; the controller decides. The published Khipu abstention gate remains BLOCKED. No catalog entry grants tool execution or production authorization.",
]


def read_json(raw: bytes) -> dict:
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate catalog input key")
            value[key] = item
        return value
    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError("Catalog inputs must be objects")
    return value


def identity(kind: str, source_id: str) -> None:
    owner = "szl-holdings" if kind == "GitHub" else "SZLHOLDINGS"
    if (kind not in KINDS[:-1] or not isinstance(source_id, str)
            or not re.fullmatch(re.escape(owner) + r"/[A-Za-z0-9_.-]+", source_id)
            or source_id.split("/")[1] in {".", ".."}):
        raise ValueError("Catalog identity outside public canonical scope")


def plain(value: str, maximum: int = 4000) -> str:
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError("Catalog display text must be bounded plain text")
    return value


def past_observation(value: str) -> None:
    if observed_datetime(value) > datetime.now(timezone.utc):
        raise ValueError("Catalog observation cannot be in the future")


def membership_keys(membership: dict) -> set[tuple[str, str]]:
    if set(membership) != {"schema", "observed_at", "evidence_class", "scope", "assets"}:
        raise ValueError("Public membership field allowlist mismatch")
    if membership["schema"] != MEMBERSHIP_SCHEMA or membership["evidence_class"] != "MEASURED":
        raise ValueError("Unsupported public membership schema")
    past_observation(membership["observed_at"])
    plain(membership["scope"])
    if not isinstance(membership["assets"], list):
        raise ValueError("Public membership requires asset rows")
    keys = set()
    for row in membership["assets"]:
        if not isinstance(row, dict) or set(row) != {"kind", "id", "private"} or row["private"] is not False:
            raise ValueError("Membership requires closed literal-public rows")
        identity(row["kind"], row["id"])
        key = (row["kind"], row["id"])
        if key in keys:
            raise ValueError("Duplicate public membership")
        keys.add(key)
    return keys


def build_catalog(source: dict, kernels: dict, packages: dict, membership: dict,
                  hashes: dict[str, str]) -> dict:
    current = membership_keys(membership)
    if set(source) != {"schema", "observed_at", "counts", "limitations", "assets"} or source["schema"] != "szl.public-estate-snapshot/v1":
        raise ValueError("Unsupported dated repository snapshot")
    past_observation(source["observed_at"])
    validate_kernels(kernels)
    past_observation(kernels["observed_at"])
    public_sources = [dict(kind="GitHub", id=source_id, private=False)
                      for kind, source_id in sorted(current) if kind == "GitHub"]
    validate_packages(packages, public_sources)
    if set(hashes) != set(INPUTS) or any(not re.fullmatch(r"[0-9a-f]{64}", v) for v in hashes.values()):
        raise ValueError("Catalog requires exact input byte hashes")
    rows = []
    resolved = set()
    seen = set()
    for row in source["assets"]:
        if not isinstance(row, dict) or set(row) != ASSET_FIELDS or row["private"] is not False:
            raise ValueError("Source snapshot requires allowlisted public rows")
        kind, source_id = row["kind"], row["id"]
        identity(kind, source_id)
        if kind not in KINDS[:4]:
            raise ValueError("Repository snapshot has unsupported kind")
        key = (kind, source_id)
        if key in seen:
            raise ValueError("Duplicate source snapshot identity")
        seen.add(key)
        revision = exact_revision(row["revision"], source_id)
        prefix = {"GitHub": "https://github.com/", "HF Model": "https://huggingface.co/",
                  "HF Dataset": "https://huggingface.co/datasets/", "HF Space": "https://huggingface.co/spaces/"}[kind]
        base = prefix + source_id
        if row["url"] != base or row["sourceUrl"] != base + "/tree/" + revision:
            raise ValueError("Mutable or conflicting source link")
        if row["ciUrl"] and (kind != "GitHub" or not re.fullmatch(re.escape(base) + r"/actions/runs/[1-9][0-9]*", row["ciUrl"])):
            raise ValueError("Noncanonical CI link")
        if type(row["archived"]) is not bool:
            raise ValueError("Invalid archive metadata")
        for field in ("category", "state", "ci"):
            plain(row[field])
        if key not in current:
            continue
        resolved.add(key)
        rows.append({**{k: row[k] for k in ("id", "kind", "category", "revision", "sourceUrl", "url", "state", "ciUrl", "archived", "private")},
                     "summary": "Dated exact-source inventory record.", "installCommand": None,
                     "requiresPython": None, "sourcePackageBinding": None})
    if Counter(row["kind"] for row in source["assets"]) != source["counts"]:
        raise ValueError("Repository snapshot count conflict")
    for row in kernels["distributions"]:
        key = ("HF Kernel", row["id"])
        if key not in current:
            continue
        resolved.add(key)
        rows.append({"id": row["id"], "kind": "HF Kernel", "category": "Kernel distribution",
                     "revision": row["revision"], "sourceUrl": row["sourceUrl"], "url": row["url"],
                     "state": "UNKNOWN: runtime behavior and mirror byte parity; imports NOT RUN",
                     "ciUrl": "", "archived": False, "private": False,
                     "summary": "First-class Kernel Hub software distribution.", "installCommand": None,
                     "requiresPython": None, "sourcePackageBinding": None})
    if resolved != current:
        raise ValueError("Current public membership has identities without an exact dated source binding")
    for package in packages["packages"]:
        name, version = package["package_name"], package["version"]
        # The package validator checks shell-safe names/versions and public attribution.
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.!+_-]*", version):
            raise ValueError("Unsafe package version in install command")
        record = package["source_records"][0]
        source_id = record["repository"]
        installable = any(artifact["yanked"] is False for artifact in package["artifacts"])
        availability = "DECLARED: all artifacts yanked" if not installable else "DECLARED: unyanked artifacts available"
        rows.append({"id": name, "kind": "PyPI", "category": "Python package",
                     "revision": record["revision"],
                     "sourceUrl": "https://github.com/" + source_id + "/blob/" + record["revision"] + "/" + record["metadata_path"],
                     "url": package["pypi_url"],
                     "state": "MEASURED: published " + version + "; " + availability + "; source attribution DECLARED; source/package binding UNKNOWN; installation NOT RUN",
                     "ciUrl": "", "archived": False, "private": False,
                     "summary": plain(package["summary"] or "Published Python distribution."),
                     "installCommand": ("py -m pip install " + name + "==" + version) if installable else None,
                     "requiresPython": package["requires_python"], "sourcePackageBinding": "UNKNOWN"})
    rows.sort(key=lambda r: (KINDS.index(r["kind"]), r["id"].casefold(), r["id"]))
    if len({(r["kind"], r["id"]) for r in rows}) != len(rows):
        raise ValueError("Duplicate distribution identity")
    counts = Counter(r["kind"] for r in rows)
    return {"schema": "szl.public-software-catalog/v1", "observed_at": membership["observed_at"],
            "source_snapshot_observed_at": source["observed_at"], "kernel_snapshot_observed_at": kernels["observed_at"],
            "pypi_snapshot_observed_at": packages["generated_at"], "input_sha256": hashes,
            "counts": {k: counts[k] for k in KINDS}, "limitations": LIMITATIONS, "assets": rows}


def card(row: dict) -> str:
    esc = lambda value: html.escape(str(value), quote=True)
    search = " ".join(str(row[k]) for k in ("id", "kind", "category", "state", "summary")).lower()
    source_class = "source-link kernel-source" if row["kind"] == "HF Kernel" else "source-link"
    extra = ""
    if row["installCommand"]:
        extra += f'<p>Install published release (NOT RUN):<br><code>{esc(row["installCommand"])}</code></p>'
        extra += f'<p>DECLARED Python requirement: <code>{esc(row["requiresPython"] or "UNKNOWN")}</code></p>'
    visit = {"GitHub": "Repository and docs", "HF Model": "Model card and artifacts", "HF Dataset": "Dataset card",
             "HF Space": "Open Space", "HF Kernel": "Kernel package", "PyPI": "Published PyPI release"}[row["kind"]]
    run = (f'<a href="{esc(row["ciUrl"])}" target="_blank" rel="noopener noreferrer">Observed workflow</a>' if row["ciUrl"] else "")
    description_label = "DECLARED package description: " if row["kind"] == "PyPI" else ""
    revision_label = "Inspected source metadata revision" if row["kind"] == "PyPI" else "Source snapshot revision"
    return (f'<article class="asset" data-estate-asset data-kind="{esc(row["kind"])}" data-category="{esc(row["category"])}" '
            f'data-id="{esc(row["id"])}" data-search="{esc(search)}">\n'
            f'<p class="asset-kind">{esc(row["kind"])}' + (" · Archived source" if row["archived"] else "") + '</p>\n'
            f'<h2><a class="{source_class}" href="{esc(row["sourceUrl"])}" target="_blank" rel="noopener noreferrer">{esc(row["id"])}</a></h2>\n'
            f'<p class="asset-category">{esc(row["category"])}</p><p>{description_label}{esc(row["summary"])}</p>\n'
            f'<details><summary>Recorded evidence</summary><p class="asset-claim">{esc(row["state"])}</p></details>\n'
            f'<details><summary>{revision_label}</summary><code>{esc(row["revision"])}</code></details>\n{extra}\n'
            f'<p><a href="{esc(row["url"])}" target="_blank" rel="noopener noreferrer">{visit}</a> {run}</p>\n</article>')


def render_page(template: str, catalog: dict) -> str:
    esc = lambda value: html.escape(str(value), quote=True)
    labels = ("GitHub projects", "Model repositories", "Datasets", "Spaces", "Kernel distributions", "PyPI distributions")
    stats = '\n' + '\n'.join(f'<div class="stat"><strong>{catalog["counts"][kind]}</strong><span>{label}</span></div>'
                              for kind, label in zip(KINDS, labels)) + '\n'
    page = replace_once(template, r'<div class="stats" aria-label="[^"<>]+">.*?</div>\s*</div>',
                        '<div class="stats" aria-label="Public snapshot counts">' + stats + '</div>')
    page = replace_once(page, r'<select id="estate-kind">.*?</select>',
                        '<select id="estate-kind"><option value="">All types</option>' +
                        ''.join(f'<option value="{esc(k)}">{esc(k)}</option>' for k in KINDS) + '</select>')
    page = replace_once(page, r'<select id="estate-category">.*?</select>',
                        '<select id="estate-category"><option value="">All categories</option>' +
                        ''.join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in sorted({r['category'] for r in catalog['assets']}, key=str.casefold)) + '</select>')
    page = replace_region(page, '    <div class="grid" id="estate-grid">\n',
                          '    </div>\n    <noscript>',
                          '\n'.join(card(row) for row in catalog['assets']) + '\n')
    page = replace_once(page, r'<p class="count" id="estate-count" role="status" aria-live="polite">.*?</p>',
                        f'<p class="count" id="estate-count" role="status" aria-live="polite">{len(catalog["assets"])} matching public assets</p>')
    kernel_note = ('\n<section class="kernel-distributions" aria-labelledby="estate-kernels-title">'
                   '<h2 id="estate-kernels-title">Kernel Hub distributions</h2>'
                   '<p>The first-class kernel packages are included in the searchable catalog below. '
                   'Their revisions are separate from model mirrors; parity and execution remain UNKNOWN.</p>'
                   '<p><a href="kernel-distributions.json">Kernel source snapshot</a></p></section>\n')
    page = replace_region(page, '<!-- estate-kernels:start -->', '<!-- estate-kernels:end -->', kernel_note)
    return page


def generate(root: Path) -> tuple[dict, str]:
    raw = {name: (root / "estate" / name).read_bytes() for name in INPUTS}
    values = {name: read_json(value) for name, value in raw.items()}
    hashes = {name: hashlib.sha256(value).hexdigest() for name, value in raw.items()}
    catalog = build_catalog(*(values[name] for name in INPUTS), hashes)
    return catalog, render_page((root / "estate/index.html").read_text(encoding="utf-8"), catalog)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        catalog, page = generate(args.root)
        encoded = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
        target = args.root / "estate/public-catalog.json"
        if args.check:
            if target.read_text(encoding="utf-8") != encoded or (args.root / "estate/index.html").read_text(encoding="utf-8") != page:
                raise ValueError("Committed catalog/page differs from validated public inputs")
        else:
            target.write_text(encoded, encoding="utf-8", newline="\n")
            (args.root / "estate/index.html").write_text(page, encoding="utf-8", newline="\n")
        print(json.dumps({"counts": catalog["counts"], "total_distribution_surfaces": len(catalog["assets"]), "check": args.check}))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("Catalog error: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
