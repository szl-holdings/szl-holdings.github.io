#!/usr/bin/env python3
"""Build the dated /estate/ public projection from an explicit local raw audit.

Uses only the Python standard library and performs no network calls. Raw audit
data stays outside the site. Only literal private=False rows in the canonical
organizations enter the closed public field allowlist. Every included asset
must have an exact source SHA; missing revisions stop the complete build.

Example (the timestamp must come from the completed audit):
  py -3 scripts/build_estate_public_snapshot.py --audit-dir <audit-directory> \
      --observed-at 2026-10-05T12:45:00Z

The existing page is the visual template. Its CSS, JavaScript and CSP are kept
intact. Run scripts/bind_browser_policy.py --check after generation.
"""
from __future__ import annotations

import argparse
import calendar
from collections import Counter
from datetime import datetime, timedelta
import html
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "szl.public-estate-snapshot/v1"
KINDS = ("GitHub", "HF Model", "HF Dataset", "HF Space")
ASSET_FIELDS = frozenset({
    "id", "kind", "url", "revision", "archived", "category", "ci",
    "state", "sourceUrl", "ciUrl", "private",
})
SHA = re.compile(r"[0-9a-f]{40}\Z")
GITHUB_ID = re.compile(r"szl-holdings/[A-Za-z0-9_.-]+\Z")
HF_ID = re.compile(r"SZLHOLDINGS/[A-Za-z0-9_.-]+\Z")
LIMITATIONS = (
    "Dated public source and provider metadata snapshot; not a live monitor.",
    "GitHub CI summaries cover the bounded latest 100 default-branch runs, grouped by workflow. Only runs matching the collected SHA count; older runs and absent workflows remain UNKNOWN.",
    "Listed model files are artifact metadata, not evidence of trained weight quality, held-out evaluation, authorization, or production readiness.",
    "A provider revision or REPORTED RUNNING Space does not establish source/runtime parity; runtime behavior NOT RUN.",
    "Model inference, model weights and dataset rows NOT RUN in this inventory.",
    "DECLARED Khipu promotion gate remains BLOCKED: REPORTED 2/6 abstention; publication_eligible=false pending a fresh held-out gate.",
)


def observed_datetime(value: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", value):
        raise ValueError("--observed-at must be an explicit ISO 8601 UTC timestamp")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.utcoffset() != timedelta(0):
        raise ValueError("--observed-at must use UTC")
    return stamp


def exact_revision(value: object, asset_id: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError(f"Public asset {asset_id} lacks an exact 40-character lowercase source SHA")
    return value


def canonical_id(value: object, pattern: re.Pattern[str], owner: str) -> str | None:
    if not isinstance(value, str):
        raise ValueError("A public asset is missing its repository identifier")
    if not value.startswith(owner + "/"):
        return None
    if not pattern.fullmatch(value) or value.split("/")[1] in {".", ".."}:
        raise ValueError("A public canonical asset has an invalid repository identifier")
    return value


def load_audit(audit_dir: Path) -> tuple[list[dict], dict[str, dict], list[dict]]:
    data_dir = audit_dir if (audit_dir / "github-repositories.json").is_file() else audit_dir / "audit-data"

    def read_rows(name: str) -> list[dict]:
        try:
            value = json.loads((data_dir / name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Required raw audit file unavailable or invalid: {name}") from error
        if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
            raise ValueError(f"Raw audit file must contain a list of objects: {name}")
        return value

    github = read_rows("github-repositories.json")
    hf = read_rows("huggingface-repositories.json")
    reports = {}
    for row in github:
        if row.get("private") is not False:
            continue
        name = canonical_id(row.get("full_name"), GITHUB_ID, "szl-holdings")
        if name is None:
            continue
        path = data_dir / ("repo--" + name.replace("/", "--") + ".json")
        if not path.is_file():
            continue  # build_snapshot rejects its missing source revision.
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Raw source report invalid for public asset {name}") from error
        if not isinstance(report, dict) or report.get("full_name") != name:
            raise ValueError(f"Raw source report identity mismatch for public asset {name}")
        reports[name] = report
    return github, reports, hf


def summarize_ci(asset_id: str, revision: str, report: dict) -> tuple[str, str]:
    """Describe collected exact-head metadata without turning it into a release."""
    window = report.get("workflow_history_window")
    suffix = "bounded latest 100 default-branch runs"
    if isinstance(window, int) and not isinstance(window, bool) and 0 <= window <= 100:
        suffix += f" ({window} returned)"
    suffix += "; absent workflows UNKNOWN"
    runs = report.get("latest_by_workflow")
    if not isinstance(runs, list):
        return "UNAVAILABLE: exact-source CI metadata not collected; " + suffix, ""
    current = [run for run in runs if isinstance(run, dict) and run.get("head_sha") == revision]
    older = sum(isinstance(run, dict) and run.get("head_sha") != revision for run in runs)
    statuses = Counter()
    conclusions = {"success", "failure", "cancelled", "timed_out", "action_required",
                   "neutral", "skipped", "startup_failure", "stale"}
    pending = {"queued", "in_progress", "waiting", "pending", "requested"}
    for run in current:
        status, conclusion = run.get("status"), run.get("conclusion")
        if status == "completed" and conclusion in conclusions:
            statuses[conclusion.upper()] += 1
        elif status in pending:
            statuses[status.upper()] += 1
        else:
            statuses["UNKNOWN"] += 1
    if current:
        summary = "; ".join(f"{count} {status}" for status, count in sorted(statuses.items()))
        summary += " matching collected SHA"
    else:
        summary = "UNKNOWN at collected SHA; no matching observed workflow run"
    if older:
        summary += f"; {older} older run(s) UNKNOWN at collected SHA"
    url_pattern = re.compile(re.escape("https://github.com/" + asset_id) + r"/actions/runs/[1-9][0-9]*\Z")
    ci_url = next((run["html_url"] for run in current
                   if isinstance(run.get("html_url"), str) and url_pattern.fullmatch(run["html_url"])), "")
    return summary + "; " + suffix, ci_url


def model_category(row: dict, revision: str) -> str:
    if row.get("files_coverage") in (None, "UNKNOWN") or row.get("files_revision") != revision:
        return "Artifact inventory UNKNOWN"
    files = [value for value in row.get("files", []) if isinstance(value, str)]
    if row.get("is_kernel") is True:
        return "Kernel / software"
    if any(value.endswith((".safetensors", ".bin", ".gguf", ".pt", ".pth", ".onnx")) for value in files):
        return "Tensor / GGUF artifact"
    if any(value.endswith((".npz", ".npy")) for value in files):
        return "Numeric archive / fixture"
    if any(value.startswith(("train", "scripts/train")) for value in files):
        return "Training recipe"
    return "Other artifact / documentation"


def provider_state(row: dict, asset_id: str) -> str:
    card = row.get("card") if isinstance(row.get("card"), dict) else {}
    szl = card.get("szl") if isinstance(card.get("szl"), dict) else {}
    named = szl.get("named_n") if isinstance(szl.get("named_n"), dict) else {}
    gate = ""
    if szl.get("publication_eligible") is False:
        gate = "DECLARED publication_eligible=false; promotion BLOCKED; "
    if str(named.get("gate", "")).lower() == "fail":
        gate += "DECLARED named-N gate FAIL; promotion BLOCKED; "
    if asset_id == "SZLHOLDINGS/SZL-Khipu-1.5B":
        return "DECLARED promotion gate BLOCKED; REPORTED 2/6 abstention; publication_eligible=false; fresh held-out replay UNKNOWN"
    if row["type"] == "space":
        runtime = row.get("runtime") if isinstance(row.get("runtime"), dict) else {}
        stage = runtime.get("stage") or "UNKNOWN"
        hardware = runtime.get("hardware")
        hardware_note = f"; {hardware}" if isinstance(hardware, str) and hardware not in {"", "None", "UNKNOWN"} else ""
        return gate + f"REPORTED {stage}{hardware_note}; source/runtime parity UNKNOWN; runtime behavior NOT RUN"
    if row["type"] == "dataset":
        return gate + "UNKNOWN: dataset suitability and evaluation; rows NOT RUN"
    return gate + "UNKNOWN: artifact quality and held-out evaluation; listed files do not establish trained weights"


def build_snapshot(github: list[dict], reports: dict[str, dict], hf: list[dict], observed_at: str) -> dict:
    observed_datetime(observed_at)
    assets = []
    seen = set()

    def add(asset: dict) -> None:
        key = (asset["kind"], asset["id"])
        if key in seen:
            raise ValueError("Duplicate public asset in raw audit")
        seen.add(key)
        if set(asset) != ASSET_FIELDS:
            raise ValueError("Public projection field allowlist mismatch")
        assets.append(asset)

    for row in github:
        if row.get("private") is not False:
            continue
        asset_id = canonical_id(row.get("full_name"), GITHUB_ID, "szl-holdings")
        if asset_id is None:
            continue
        report = reports.get(asset_id, {})
        revision = exact_revision(report.get("commit_sha"), asset_id)
        ci, ci_url = summarize_ci(asset_id, revision, report)
        base = "https://github.com/" + asset_id
        add({"id": asset_id, "kind": "GitHub", "url": base, "revision": revision,
             "archived": row.get("archived") is True, "category": row.get("language") or "Unclassified",
             "ci": ci, "state": ci, "sourceUrl": base + "/tree/" + revision,
             "ciUrl": ci_url, "private": False})
    for row in hf:
        if row.get("private") is not False:
            continue
        asset_id = canonical_id(row.get("id"), HF_ID, "SZLHOLDINGS")
        if asset_id is None:
            continue
        revision = exact_revision(row.get("sha"), asset_id)
        kind = {"model": "HF Model", "dataset": "HF Dataset", "space": "HF Space"}.get(row.get("type"))
        if kind is None:
            raise ValueError("A public HF asset has an unsupported repository type")
        prefix = {"model": "", "dataset": "datasets/", "space": "spaces/"}[row["type"]]
        base = "https://huggingface.co/" + prefix + asset_id
        category = model_category(row, revision) if kind == "HF Model" else "Dataset repository" if kind == "HF Dataset" else row.get("sdk") or "Space repository"
        add({"id": asset_id, "kind": kind, "url": base, "revision": revision,
             "archived": False, "category": category,
             "ci": "UNKNOWN: GitHub source CI not bound by this provider inventory",
             "state": provider_state(row, asset_id), "sourceUrl": base + "/tree/" + revision,
             "ciUrl": "", "private": False})
    assets.sort(key=lambda asset: (KINDS.index(asset["kind"]), asset["id"].casefold(), asset["id"]))
    counts = Counter(asset["kind"] for asset in assets)
    return {"schema": SCHEMA, "observed_at": observed_at,
            "counts": {kind: counts[kind] for kind in KINDS},
            "limitations": list(LIMITATIONS), "assets": assets}


def render_card(asset: dict) -> str:
    escape = lambda value: html.escape(str(value), quote=True)
    search = " ".join(str(asset[key]) for key in ("id", "kind", "category", "state", "ci")).lower()
    label = "MEASURED exact-source CI metadata:" if asset["kind"] == "GitHub" else "REPORTED provider repository metadata:"
    archived = " · Archived source" if asset["archived"] else ""
    run = (f'  <a href="{escape(asset["ciUrl"])}" target="_blank" rel="noopener noreferrer">Observed workflow run</a>'
           if asset["ciUrl"] else "")
    return f'''<article class="asset" data-estate-asset data-kind="{escape(asset["kind"])}" data-id="{escape(asset["id"])}" data-search="{escape(search)}">
  <p class="asset-kind">{escape(asset["kind"])}{archived}</p>
  <h2><a class="source-link" href="{escape(asset["sourceUrl"])}" target="_blank" rel="noopener noreferrer">{escape(asset["id"])}</a></h2>
  <p class="asset-category">{escape(asset["category"])}</p>
  <p class="asset-claim"><span>{label}</span> {escape(asset["state"])}</p>
  <p class="asset-revision">Source revision <code>{escape(asset["revision"][:12])}</code></p>
{run}
</article>'''


def replace_once(text: str, pattern: str, replacement: str) -> str:
    result, count = re.subn(pattern, lambda match: replacement, text, flags=re.S)
    if count != 1:
        raise ValueError("Estate page template has missing or ambiguous generation boundaries")
    return result


def replace_region(text: str, start: str, end: str, content: str) -> str:
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError("Estate page template has missing or ambiguous generation boundaries")
    start_index = text.index(start) + len(start)
    end_index = text.index(end, start_index)
    return text[:start_index] + content + text[end_index:]


def render_page(template: str, snapshot: dict) -> str:
    stamp = observed_datetime(snapshot["observed_at"])
    date_label = f"{stamp.day} {calendar.month_name[stamp.month]} {stamp.year}, {stamp:%H:%M} UTC"
    page = replace_once(template, r'<time datetime="[^"]+">[^<]*</time>',
                        f'<time datetime="{snapshot["observed_at"]}">{date_label}</time>')
    labels = ("GitHub repositories", "HF model repositories", "HF dataset repositories", "HF Spaces")
    stats = "\n" + "\n".join(
        f'      <div class="stat"><strong>{snapshot["counts"][kind]}</strong><span>{label}</span></div>'
        for kind, label in zip(KINDS, labels)) + "\n    </div>\n"
    page = replace_region(page, '    <div class="stats" aria-label="Public snapshot counts">',
                          '    <div class="filters"', stats)
    page = replace_once(page, r'<p class="count" id="estate-count" role="status" aria-live="polite">[^<]*</p>',
                        f'<p class="count" id="estate-count" role="status" aria-live="polite">{len(snapshot["assets"])} public assets in this snapshot</p>')
    cards = "\n".join(render_card(asset) for asset in snapshot["assets"]) + "\n"
    page = replace_region(page, '    <div class="grid" id="estate-grid">\n',
                          '    </div>\n    <noscript>', cards)
    page = replace_once(page, r'<footer><div class="shell">Source snapshot: [^<]*</div></footer>',
                        f'<footer><div class="shell">Source snapshot: {stamp:%Y-%m-%d %H:%M} UTC · Public records only · No live authorization claim.</div></footer>')
    return page


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True,
                        help="Completed local audit directory or its audit-data/ directory")
    parser.add_argument("--observed-at", required=True,
                        help="Completed audit observation timestamp in ISO 8601 UTC")
    parser.add_argument("--site-dir", type=Path, default=ROOT,
                        help="Site checkout with existing estate/index.html (default: this checkout)")
    args = parser.parse_args(argv)
    try:
        github, reports, hf = load_audit(args.audit_dir)
        snapshot = build_snapshot(github, reports, hf, args.observed_at)
        page_path = args.site_dir / "estate" / "index.html"
        page = render_page(page_path.read_text(encoding="utf-8"), snapshot)
        serialized = json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        # Validate every input and page boundary before either output is changed.
        (args.site_dir / "estate" / "public-snapshot.json").write_text(serialized, encoding="utf-8", newline="\n")
        page_path.write_text(page, encoding="utf-8", newline="\n")
    except (ValueError, OSError) as error:
        print(f"Public snapshot build stopped: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"observed_at": snapshot["observed_at"], "public_counts": snapshot["counts"],
                      "public_assets": len(snapshot["assets"]), "inference": "NOT RUN"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
