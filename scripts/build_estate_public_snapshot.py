#!/usr/bin/env python3
"""Build the dated /estate/ public projection from an explicit local raw audit.

Uses only the Python standard library and performs no network calls. Raw audit
data stays outside the site. Only literal private=False rows in the canonical
organizations enter the closed public field allowlist. Every included asset
must have an exact source SHA; missing revisions stop the complete build.

The CLI requires an unsigned private public-source-binding.json at audit root.
It verifies complete collection assertions and the hashes/counts of the source
bytes before deriving the observation time from the bound summary and receipt.
Example:
  py -3 scripts/build_estate_public_snapshot.py --audit-dir <audit-directory>

The existing page is the visual template. Its CSS, JavaScript and CSP are kept
intact. Run scripts/bind_browser_policy.py --check after generation.
"""
from __future__ import annotations

import argparse
import calendar
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "szl.public-estate-snapshot/v1"
BINDING_SCHEMA = "szl.estate-audit-source-binding/v1"
SCOPE = {"github": ["szl-holdings"], "huggingface": ["SZLHOLDINGS"]}
BASE_INPUTS = frozenset({
    "audit-data/github-repositories.json", "audit-data/huggingface-repositories.json",
    "audit-data/estate-summary.json", "audit-receipt.json",
    "execution-source-binding.json", "github-request-ledger.jsonl",
})
EXECUTION_NAMES = frozenset({
    "estate_agent.py", "audit_estate.py", "enrich_estate.py", "audit_controls.py",
    "review_models.py", "review_datasets.py", "build_showcase.py", "audit_guard.py",
})
KINDS = ("GitHub", "HF Model", "HF Dataset", "HF Space")
ASSET_FIELDS = frozenset({
    "id", "kind", "url", "revision", "archived", "category", "ci",
    "state", "sourceUrl", "ciUrl", "private",
})
SHA = re.compile(r"[0-9a-f]{40}\Z")
EXHIBITS_SCHEMA = "szl.public-research-exhibits/v1"
EXHIBIT_FIELDS = frozenset({"id", "title", "summary", "limitations", "source_ids"})
GITHUB_ID = re.compile(r"szl-holdings/[A-Za-z0-9_.-]+\Z")
HF_ID = re.compile(r"SZLHOLDINGS/[A-Za-z0-9_.-]+\Z")
LIMITATIONS = (
    "Dated public source and provider metadata snapshot; not a live monitor.",
    "GitHub CI summaries cover the bounded latest 100 default-branch runs, grouped by workflow. Only runs matching the collected SHA count; older runs and absent workflows remain UNKNOWN.",
    "Listed model files are artifact metadata, not evidence of trained weight quality, held-out evaluation, authorization, or production readiness.",
    "A provider revision or DECLARED RUNNING Space does not establish source/runtime parity; runtime behavior NOT RUN.",
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


def load_audit(audit_dir: Path, verified_bytes: dict[str, bytes] | None = None) -> tuple[list[dict], dict[str, dict], list[dict]]:
    data_dir = audit_dir if (audit_dir / "github-repositories.json").is_file() else audit_dir / "audit-data"

    def read(name: str) -> object:
        # When bound, never reread a file after checking its hash.
        raw = verified_bytes["audit-data/" + name] if verified_bytes is not None else (data_dir / name).read_bytes()
        return json.loads(raw)

    def read_rows(name: str) -> list[dict]:
        try:
            value = read(name)
        except (OSError, KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
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
        if verified_bytes is None and not path.is_file():
            continue  # build_snapshot rejects its missing source revision.
        try:
            report = read(path.name)
        except (OSError, KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"Raw source report invalid for public asset {name}") from error
        if not isinstance(report, dict) or report.get("full_name") != name:
            raise ValueError(f"Raw source report identity mismatch for public asset {name}")
        reports[name] = report
    return github, reports, hf


def load_bound_audit(audit_dir: Path, observed_override: str | None = None,
                     *, now: datetime | None = None) -> tuple[list[dict], dict[str, dict], list[dict], str]:
    """Enforce the unsigned local collection contract; this is not authentication.

    Completion is a collector observation, not inferred from matching counts.
    Source hashes and counts are independently checked locally. The private
    binding, report paths, raw counts and collector identity are never published.
    """
    audit_root = audit_dir.parent if audit_dir.name == "audit-data" else audit_dir

    def parse(raw: bytes, label: str) -> dict:
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid bound audit JSON: {label}") from error
        if not isinstance(value, dict):
            raise ValueError(f"Bound audit object required: {label}")
        return value

    try:
        binding = parse((audit_root / "public-source-binding.json").read_bytes(), "source binding")
    except OSError as error:
        raise ValueError("Completed audit requires audit-root public-source-binding.json") from error
    if binding.get("schema") != BINDING_SCHEMA or binding.get("signed") is not False or binding.get("scope") != SCOPE:
        raise ValueError("Unsupported unsigned source binding or canonical scope")
    completion = binding.get("completion")
    if not isinstance(completion, dict):
        raise ValueError("Collector completion evidence is required")
    collector = completion.get("collector", {})
    gh_completion = completion.get("github", {})
    hf_completion = completion.get("huggingface", {})
    if not all(isinstance(value, dict) for value in (collector, gh_completion, hf_completion)):
        raise ValueError("Invalid collector coverage evidence")
    if (collector.get("completed") is not True or type(collector.get("exit_code")) is not int
            or collector["exit_code"] != 0 or collector.get("evidence_class") != "DECLARED"
            or collector.get("command") != "estate_agent.py all --output ."
            or gh_completion.get("enumeration_complete") is not True
            or gh_completion.get("inspection_complete") is not True
            or hf_completion.get("enumeration_complete") is not True
            or hf_completion.get("iterators_exhausted") != ["model", "dataset", "space"]):
        raise ValueError("Complete collector execution, GitHub pagination and HF iterator exhaustion are required")
    inputs = binding.get("input_sha256")
    if not isinstance(inputs, dict) or not BASE_INPUTS.issubset(inputs):
        raise ValueError("Source binding lacks required audit inputs")
    cached = {}
    for name, digest in inputs.items():
        if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", name)
                or any(part in {".", ".."} for part in name.split("/"))
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("Invalid relative input path or SHA-256 in source binding")
        target = (audit_root / name).resolve()
        if not target.is_relative_to(audit_root.resolve()):
            raise ValueError("Bound input escapes audit root")
        raw = target.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(f"Bound audit input SHA-256 mismatch: {name}")
        cached[name] = raw
    summary = parse(cached["audit-data/estate-summary.json"], "summary")
    receipt = parse(cached["audit-receipt.json"], "receipt")
    observed_at = summary.get("generated_at")
    stamp = observed_datetime(observed_at)
    if (binding.get("observed_at") != observed_at or receipt.get("generated_at") != observed_at
            or (observed_override is not None and observed_override != observed_at)):
        raise ValueError("Observation timestamp must exactly match bound summary and receipt")
    if stamp > (now if now is not None else datetime.now(timezone.utc)):
        raise ValueError("Audit observation timestamp is in the future")
    if (receipt.get("schema") != "szl.local-estate-audit/v1" or receipt.get("signed") is not False
            or receipt.get("source_summary_sha256") != inputs["audit-data/estate-summary.json"]):
        raise ValueError("Unsigned audit receipt does not bind the collected summary")
    execution = parse(cached["execution-source-binding.json"], "execution source binding")
    if execution.get("schema") != "szl.audit-execution-source-binding/v1" or execution.get("scope") != SCOPE:
        raise ValueError("Collector source binding scope mismatch")
    execution_files = execution.get("files")
    if not isinstance(execution_files, list) or not all(isinstance(row, dict) for row in execution_files):
        raise ValueError("Collector source file bindings are required")
    code_hashes = {row.get("name"): row.get("execution_sha256") for row in execution_files
                   if isinstance(row.get("name"), str)}
    if len(code_hashes) != len(execution_files) or set(code_hashes) != EXECUTION_NAMES - {"audit_guard.py"}:
        raise ValueError("Collector source file coverage mismatch")
    code_hashes["audit_guard.py"] = execution.get("guard_sha256")
    if any(inputs.get("execution/" + name) != digest or "execution/" + name not in cached
           for name, digest in code_hashes.items()):
        raise ValueError("Collector executable bytes do not match execution source binding")
    github, reports, hf = load_audit(audit_root, cached)
    names = []
    for row in github:
        name = canonical_id(row.get("full_name"), GITHUB_ID, "szl-holdings")
        if name is None or name in names:
            raise ValueError("Raw GitHub census is duplicated or outside canonical scope")
        names.append(name)
    hf_seen = set()
    for row in hf:
        name = canonical_id(row.get("id"), HF_ID, "SZLHOLDINGS")
        repo_type = row.get("type")
        if not isinstance(repo_type, str) or repo_type not in {"model", "dataset", "space"}:
            raise ValueError("Raw HF census has an unsupported repository type")
        key = (repo_type, name)
        if name is None or key in hf_seen:
            raise ValueError("Raw HF census is duplicated or outside canonical scope")
        hf_seen.add(key)
    report_inputs = {"audit-data/repo--" + name.replace("/", "--") + ".json" for name in names}
    expected_inputs = BASE_INPUTS | report_inputs | {"execution/" + name for name in EXECUTION_NAMES}
    if set(inputs) != expected_inputs:
        raise ValueError("Source binding does not cover exactly the complete census and collector inputs")
    for name in names:
        path = "audit-data/repo--" + name.replace("/", "--") + ".json"
        if parse(cached[path], "source report").get("full_name") != name:
            raise ValueError("Bound source report identity mismatch")
    raw_counts = {"GitHub": len(github), **{
        kind: sum(row["type"] == repo_type for row in hf)
        for kind, repo_type in zip(KINDS[1:], ("model", "dataset", "space"))}}
    public_counts = {"GitHub": sum(row.get("private") is False for row in github), **{
        kind: sum(row["type"] == repo_type and row.get("private") is False for row in hf)
        for kind, repo_type in zip(KINDS[1:], ("model", "dataset", "space"))}}
    counts = binding.get("counts")
    coverage = summary.get("coverage")
    def exact_counts(value: object, expected: dict[str, int]) -> bool:
        return (isinstance(value, dict) and value == expected
                and all(type(count) is int for count in value.values()))

    if (not isinstance(counts, dict) or counts.get("raw") != raw_counts
            or not exact_counts(counts.get("raw"), raw_counts)
            or not exact_counts(counts.get("public"), public_counts)
            or not exact_counts(receipt.get("counts"), raw_counts)
            or not isinstance(coverage, dict) or coverage.get("github") != len(github)
            or coverage.get("github_inspected") != len(github) or coverage.get("hf") != len(hf)
            or any(type(coverage.get(key)) is not int for key in ("github", "github_inspected", "hf"))):
        raise ValueError("Bound audit counts or full inspection coverage mismatch")
    pagination = gh_completion.get("pagination")
    if not isinstance(pagination, dict):
        raise ValueError("Terminal GitHub pagination observation required")
    per_page, terminal_page, terminal_rows = (pagination.get(key) for key in ("per_page", "terminal_page", "terminal_rows"))
    if (any(type(value) is not int for value in (per_page, terminal_page, terminal_rows))
            or per_page != 100 or terminal_page < 1 or not 0 <= terminal_rows < per_page
            or (terminal_page - 1) * per_page + terminal_rows != len(github)):
        raise ValueError("GitHub census does not match observed terminal pagination")
    try:
        ledger = [json.loads(line) for line in cached["github-request-ledger.jsonl"].decode("utf-8-sig").splitlines() if line.strip()]
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid bound GitHub pagination ledger") from error
    prefix = "orgs/szl-holdings/repos?type=all&per_page=100&page="
    pages = [row for row in ledger if isinstance(row, dict) and str(row.get("path", "")).startswith(prefix)]
    if (len(pages) != terminal_page or any(row.get("path") != prefix + str(index)
            or row.get("status") != 200 or type(row.get("returncode")) is not int
            or row["returncode"] != 0 or row.get("rate_failure") is not False
            or observed_datetime(row.get("at")) > stamp for index, row in enumerate(pages, 1))):
        raise ValueError("Successful terminal GitHub pagination is not established by bound request ledger")
    return github, reports, hf, observed_at


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
        return gate + f"DECLARED {stage}{hardware_note}; source/runtime parity UNKNOWN; runtime behavior NOT RUN"
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
    label = "MEASURED exact-source CI metadata:" if asset["kind"] == "GitHub" else "DECLARED provider repository metadata:"
    archived = " · Archived source" if asset["archived"] else ""
    run = (f'  <a href="{escape(asset["ciUrl"])}" target="_blank" rel="noopener noreferrer">Observed workflow run</a>'
           if asset["ciUrl"] else "")
    return f'''<article class="asset" data-estate-asset data-kind="{escape(asset["kind"])}" data-category="{escape(asset["category"])}" data-id="{escape(asset["id"])}" data-search="{escape(search)}">
  <p class="asset-kind">{escape(asset["kind"])}{archived}</p>
  <h2><a class="source-link" href="{escape(asset["sourceUrl"])}" target="_blank" rel="noopener noreferrer">{escape(asset["id"])}</a></h2>
  <p class="asset-category">{escape(asset["category"])}</p>
  <p class="asset-claim"><span>{label}</span> {escape(asset["state"])}</p>
  <p class="asset-revision">Source revision <code>{escape(asset["revision"][:12])}</code></p>
{run}
</article>'''


def load_exhibits(path: Path) -> dict:
    """Read reviewed curator text, rejecting duplicate keys before validation."""
    def unique_object(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate key in research exhibit manifest")
            result[key] = value
        return result

    try:
        value = json.loads(path.read_bytes(), object_pairs_hook=unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid research exhibit JSON") from error
    if not isinstance(value, dict):
        raise ValueError("Research exhibit manifest must be an object")
    return value


def render_exhibits(manifest: dict, snapshot: dict) -> str:
    """Bind reviewed plain text to public source rows; this runs no software."""
    def closed(value: object, fields: set | frozenset, label: str) -> dict:
        if not isinstance(value, dict) or set(value) != fields:
            raise ValueError(f"Research exhibit {label} field allowlist mismatch")
        return value

    def plain_text(value: object, label: str, maximum: int = 2000) -> str:
        if (not isinstance(value, str) or not value.strip() or len(value) > maximum
                or any(ord(character) < 32 or ord(character) == 127 for character in value)):
            raise ValueError(f"Research exhibit {label} must be bounded plain text")
        return value

    closed(manifest, {"schema", "evidence_class", "exhibits"}, "manifest")
    if manifest["schema"] != EXHIBITS_SCHEMA or manifest["evidence_class"] != "DECLARED":
        raise ValueError("Research exhibits require the DECLARED curator schema")
    exhibits = manifest["exhibits"]
    if not isinstance(exhibits, list) or not 1 <= len(exhibits) <= 10:
        raise ValueError("Research exhibit list must contain one to ten reviewed entries")
    assets = snapshot.get("assets")
    if not isinstance(assets, list):
        raise ValueError("Research exhibits require a public snapshot asset list")
    by_id = {}
    for asset in assets:
        if (not isinstance(asset, dict) or not isinstance(asset.get("kind"), str)
                or not isinstance(asset.get("id"), str)):
            raise ValueError("Research exhibit source identity invalid")
        key = (asset["kind"], asset["id"])
        if key in by_id:
            raise ValueError("Research exhibit snapshot has duplicate source identities")
        by_id[key] = asset
    seen = set()
    cards = []
    escape = lambda value: html.escape(value, quote=True)
    for exhibit in exhibits:
        closed(exhibit, EXHIBIT_FIELDS, "entry")
        exhibit_id = exhibit["id"]
        if (not isinstance(exhibit_id, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", exhibit_id)
                or exhibit_id in seen):
            raise ValueError("Research exhibit IDs must be unique bounded identifiers")
        seen.add(exhibit_id)
        title = plain_text(exhibit["title"], "title", 160)
        summary = plain_text(exhibit["summary"], "summary")
        limitations = plain_text(exhibit["limitations"], "limitations")
        sources = exhibit["source_ids"]
        if not isinstance(sources, list) or not 1 <= len(sources) <= 4:
            raise ValueError("Research exhibit requires one to four snapshot source IDs")
        source_rows = []
        source_seen = set()
        for source in sources:
            closed(source, {"kind", "id"}, "source reference")
            kind, source_id = source["kind"], source["id"]
            if not isinstance(kind, str) or not isinstance(source_id, str):
                raise ValueError("Research exhibit source reference must use strings")
            key = (kind, source_id)
            if key in source_seen or key not in by_id:
                raise ValueError("Research exhibit source absent or repeated in public snapshot")
            source_seen.add(key)
            asset = by_id[key]
            if set(asset) != ASSET_FIELDS or asset["private"] is not False or kind not in KINDS:
                raise ValueError("Research exhibit source must be an allowlisted literal-public snapshot row")
            pattern, owner = (GITHUB_ID, "szl-holdings") if kind == "GitHub" else (HF_ID, "SZLHOLDINGS")
            if canonical_id(source_id, pattern, owner) != source_id:
                raise ValueError("Research exhibit source outside canonical scope")
            revision = exact_revision(asset["revision"], source_id)
            prefix = {"GitHub": "https://github.com/", "HF Model": "https://huggingface.co/",
                      "HF Dataset": "https://huggingface.co/datasets/", "HF Space": "https://huggingface.co/spaces/"}[kind]
            if asset["sourceUrl"] != prefix + source_id + "/tree/" + revision:
                raise ValueError("Research exhibit link does not match immutable snapshot source")
            state = plain_text(asset["state"], "snapshot state")
            source_rows.append(
                f'      <li><a href="{escape(asset["sourceUrl"])}" target="_blank" rel="noopener noreferrer">{escape(source_id)}</a>'
                f'<p class="exhibit-state"><strong>Snapshot state:</strong> {escape(state)}</p></li>'
            )
        cards.append(
            f'  <article class="asset research-exhibit" id="exhibit-{exhibit_id}">\n'
            f'    <p class="eyebrow">DECLARED research exhibit</p>\n'
            f'    <h3>{escape(title)}</h3>\n    <p>{escape(summary)}</p>\n'
            '    <ul class="exhibit-sources">\n' + "\n".join(source_rows) + '\n    </ul>\n'
            f'    <p class="exhibit-limit"><strong>Limit:</strong> {escape(limitations)}</p>\n  </article>'
        )
    return ('\n<section class="research-exhibits" aria-labelledby="estate-exhibits-title">\n'
            '  <h2 id="estate-exhibits-title">Research exhibits: start with the source</h2>\n'
            '  <p>DECLARED curator selections from this dated public snapshot. Each exhibit links to exact source; inclusion establishes no runtime or independent evaluation.</p>\n'
            '  <div class="grid">\n' + "\n".join(cards) + '\n  </div>\n</section>\n')


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


def render_page(template: str, snapshot: dict, exhibits: dict | None = None) -> str:
    stamp = observed_datetime(snapshot["observed_at"])
    date_label = f"{stamp.day} {calendar.month_name[stamp.month]} {stamp.year}, {stamp:%H:%M} UTC"
    page = replace_once(template, r'<time id="estate-observed-at" datetime="[^"]+">[^<]*</time>',
                        f'<time id="estate-observed-at" datetime="{snapshot["observed_at"]}">{date_label}</time>')
    labels = ("GitHub repositories", "HF model repositories", "HF dataset repositories", "HF Spaces")
    stats = "\n" + "\n".join(
        f'      <div class="stat"><strong>{snapshot["counts"][kind]}</strong><span>{label}</span></div>'
        for kind, label in zip(KINDS, labels)) + "\n    </div>\n"
    page = replace_region(page, '    <div class="stats" aria-label="Public snapshot counts">',
                          '    <div class="filters"', stats)
    categories = {asset["category"] for asset in snapshot["assets"]
                  if isinstance(asset.get("category"), str) and asset["category"]}
    if any(not isinstance(asset.get("category"), str) or not asset["category"] for asset in snapshot["assets"]):
        raise ValueError("Public artifact categories must be nonempty strings")
    options = '<option value="">All categories</option>' + "".join(
        f'<option value="{html.escape(category, quote=True)}">{html.escape(category)}</option>'
        for category in sorted(categories, key=lambda value: (value.casefold(), value)))
    page = replace_once(page, r'<select id="estate-category"[^>]*>.*?</select>',
                        '<select id="estate-category">' + options + '</select>')
    if exhibits is not None:
        page = replace_region(page, '<!-- estate-exhibits:start -->',
                              '<!-- estate-exhibits:end -->', render_exhibits(exhibits, snapshot))
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
    parser.add_argument("--observed-at",
                        help="Optional assertion; must exactly match the bound completed audit timestamp")
    parser.add_argument("--site-dir", type=Path, default=ROOT,
                        help="Site checkout with existing estate/index.html (default: this checkout)")
    args = parser.parse_args(argv)
    try:
        github, reports, hf, observed_at = load_bound_audit(args.audit_dir, args.observed_at)
        snapshot = build_snapshot(github, reports, hf, observed_at)
        page_path = args.site_dir / "estate" / "index.html"
        exhibits = load_exhibits(args.site_dir / "estate" / "exhibits.json")
        page = render_page(page_path.read_text(encoding="utf-8"), snapshot, exhibits=exhibits)
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
