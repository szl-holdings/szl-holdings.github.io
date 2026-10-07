"""Fail closed if the public frontier bundle loses its source or privacy boundary."""

from __future__ import annotations

import csv
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
FRONTIER = ROOT / "frontier"
PUBLIC_FILES = {
    "index.html", "showcase-public.html", "math-software.csv", "models.csv",
    "assets-inventory.csv", "PROOF_TO_CODE.md", "proof-to-code-matrix.csv",
    "build_proof_code_matrix.py", "audit-data/public-source-receipt.json",
    "audit-data/hf-public-overlay.json",
    "audit-data/showcase-public-source-receipt.json",
}
CSV_ASSET_FIELDS = {
    "kind", "id", "owner", "url", "private", "archived", "category",
    "status", "license", "revision", "updated",
}
COMMON_ASSET_FIELDS = CSV_ASSET_FIELDS | {"description"}
GITHUB_ASSET_FIELDS = COMMON_ASSET_FIELDS | {
    "workflow_count", "test_path_count", "skill_count", "kernel_path_count",
    "source_file_count", "tree_truncated",
}
HUB_ASSET_FIELDS = COMMON_ASSET_FIELDS | {
    "downloads", "likes", "card_available", "file_count", "files_coverage",
    "tensor_artifact", "numeric_archives", "declared_artifact_class",
    "declared_base", "declared_eval_gate", "publication_eligible",
}
ASSET_FIELDS_BY_KIND = {
    "GitHub": GITHUB_ASSET_FIELDS,
    "HF Model": HUB_ASSET_FIELDS,
    "HF Dataset": HUB_ASSET_FIELDS,
    "HF Space": HUB_ASSET_FIELDS,
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"Frontier public contract FAILED: {message}")


def rows(name: str) -> list[dict[str, str]]:
    with (FRONTIER / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def embedded_json(page: str, prefix: str, suffix: str) -> dict:
    content = (FRONTIER / page).read_text(encoding="utf-8")
    before, marker, tail = content.partition(prefix)
    require(bool(marker), f"{page} has no embedded data start")
    payload, marker, _ = tail.partition(suffix)
    require(bool(marker), f"{page} has no embedded data end")
    require("</script" not in payload.lower(), f"{page} embeds a script closer")
    return json.loads(payload)


def has_canonical_public_identity(row: dict) -> bool:
    boundaries = {
        "GitHub": ("szl-holdings", "https://github.com/"),
        "HF Model": ("SZLHOLDINGS", "https://huggingface.co/"),
        "HF Dataset": ("SZLHOLDINGS", "https://huggingface.co/datasets/"),
        "HF Space": ("SZLHOLDINGS", "https://huggingface.co/spaces/"),
    }
    boundary = boundaries.get(row.get("kind"))
    asset_id = row.get("id")
    if boundary is None or not isinstance(asset_id, str):
        return False
    owner, url_prefix = boundary
    return (row.get("owner") == owner
            and asset_id.startswith(owner + "/")
            and row.get("url") == url_prefix + asset_id)


def main() -> None:
    receipt_bytes = (FRONTIER / "audit-data" / "public-source-receipt.json").read_bytes()
    receipt = json.loads(receipt_bytes)
    require(receipt.get("schema") == "szl.public-org-showcase-source/v1", "wrong receipt schema")
    require(receipt.get("github_owner") == "szl-holdings", "wrong GitHub owner")
    require(receipt.get("hf_owner") == "SZLHOLDINGS", "wrong Hub owner")
    require(receipt.get("github_public_repositories") == 127, "GitHub snapshot count changed")
    require(receipt.get("hf_public_repositories") == 117, "Hub snapshot total changed")
    require(receipt.get("hf_public_types") == {"model": 47, "dataset": 36, "space": 34},
            "Hub snapshot count changed")
    showcase_receipt_bytes = (
        FRONTIER / "audit-data" / "showcase-public-source-receipt.json"
    ).read_bytes()
    showcase_receipt = json.loads(showcase_receipt_bytes)
    require(showcase_receipt.get("schema")
            == "szl.public-org-showcase-successor-source/v1",
            "wrong full-showcase receipt schema")
    require(showcase_receipt.get("evidence_class") == "DECLARED"
            and showcase_receipt.get("signed") is False,
            "full-showcase source receipt overstates its evidence")
    require(showcase_receipt.get("generated_at_utc")
            == "2026-10-06T03:21:26.404577+00:00",
            "full-showcase observation time changed")
    require(showcase_receipt.get("github_owner") == "szl-holdings"
            and showcase_receipt.get("hf_owner") == "SZLHOLDINGS",
            "wrong full-showcase owner boundary")
    require(showcase_receipt.get("public_assets") == 247
            and showcase_receipt.get("public_types") == {
                "GitHub": 128, "HF Model": 47, "HF Dataset": 37, "HF Space": 35,
            }, "full-showcase public counts changed")
    require(showcase_receipt.get("source_sha256") == {
        "showcase-public.html":
            "e15f74d3a370a3dfc8d2642c4629031fd26299da2052aea490217219c77c13ea",
        "assets-inventory.csv":
            "0028eec048fb78ca533cf6099f42b7b7b1d3aae14371b2da6cc96657a0cd22eb",
        "audit-receipt.json":
            "d6fde8d71df408ef6a2a9bc838c3312ee139d652b03efa80be5572a4e3916610",
        "audit-data/estate-summary.json":
            "77b7a0382e5edf8ad6a4ec4a6631856669b851aec0f6c4138851484e14998e3d",
        "audit-data/github-repositories.json":
            "2e3f49b6f72fd900774d9e9759a317fee4671262ec10c2aea2c0336accad838c",
        "audit-data/huggingface-repositories.json":
            "1e4a973e29f44d4e93803e7c0eb5569e3be83cf10f3f707fd48725e4363b24d5",
    }, "full-showcase inputs changed without review")
    require(showcase_receipt.get("projection") == {
        "required_private_value": False,
        "allowed_owners": {
            "GitHub": ["szl-holdings"], "Hugging Face": ["SZLHOLDINGS"],
        },
        "local_inventory_included": False,
        "raw_audit_included": False,
    }, "full-showcase closed projection changed")
    require(showcase_receipt.get("verification", {}).get("evidence_class") == "MEASURED"
            and showcase_receipt.get("deployment_evidence") == "UNAVAILABLE"
            and showcase_receipt.get("independent_witness") == "UNAVAILABLE",
            "full-showcase receipt conflates local checks with publication proof")
    overlay_bytes = (FRONTIER / "audit-data" / "hf-public-overlay.json").read_bytes()
    overlay = json.loads(overlay_bytes)
    require(overlay.get("schema") == "szl.hf-public-overlay/v1"
            and overlay.get("owner") == "SZLHOLDINGS"
            and overlay.get("base_public_count") == 114
            and overlay.get("observed_public_count") == 117,
            "Hub public addition provenance changed")
    require(receipt.get("source_sha256", {}).get("hf-public-overlay.json")
            == hashlib.sha256(overlay_bytes.replace(b"\r\n", b"\n")).hexdigest(),
            "Hub public additions do not match the source receipt")
    require({(row.get("type"), row.get("id")) for row in overlay.get("additions", [])} == {
        ("dataset", "SZLHOLDINGS/szl-science-forum-corpus"),
        ("space", "SZLHOLDINGS/README"),
        ("model", "SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v3-authenticated"),
    } and all(row.get("private") is False and row.get("public_only") is True
              and re.fullmatch(r"[0-9a-f]{40}", row.get("sha", ""))
              for row in overlay["additions"]),
            "Hub additions escaped the reviewed public, pinned scope")
    replacements = overlay.get("replacements", [])
    require(len(replacements) == 1
            and replacements[0].get("type") == "model"
            and replacements[0].get("id") == "SZLHOLDINGS/szl-formulas"
            and replacements[0].get("private") is False
            and replacements[0].get("is_kernel") is True
            and replacements[0].get("replaces_sha") == "937c8460ed1a77bb817be41cd8a1c39369ffb8bd"
            and replacements[0].get("sha") == "d3f2dbbb7c59bef13cf1b755edf487bfb2960653",
            "formula software mirror revision changed without review")
    binding = replacements[0].get("publication_binding", {})
    require(binding.get("source_repository") == "szl-holdings/szl-formulas"
            and binding.get("source_revision") == "a3f9dcab6e3564ce384bd3c095f64cc2121059f9"
            and binding.get("model_revision") == replacements[0]["sha"]
            and binding.get("previous_published_overlay_revision")
            == "355695fe22ec9361283cf19790166cf0d2093bcd"
            and binding.get("kernel_revision") == "04082bd2f7ca43ce7c00d47069cb5a25d662116c"
            and binding.get("binding_sha256")
            == "35ccd96b50d2547ec462d596d13cc27a3010e60e85633ff4365be1f29226b18f"
            and binding.get("managed_file_hashes_matched") == 32
            and binding.get("managed_file_hashes_checked") == 32,
            "formula mirror lacks the exact public source and kernel binding receipt")

    math = rows("math-software.csv")
    models = rows("models.csv")
    assets = rows("assets-inventory.csv")
    proof = rows("proof-to-code-matrix.csv")
    require(len(math) == 39 and len(models) == 47 and len(assets) == 247,
            "CSV counts do not match the reviewed snapshot")
    formula_rows = [row for row in models if row["id"] == "SZLHOLDINGS/szl-formulas"]
    require(len(formula_rows) == 1 and formula_rows[0]["revision"] == replacements[0]["sha"],
            "model export does not use the published formula mirror revision")
    scaffold_id = "SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v3-authenticated"
    scaffold_rows = [row for row in models if row["id"] == scaffold_id]
    require(len(scaffold_rows) == 1
            and scaffold_rows[0]["artifact_class"] == "Repository scaffold"
            and scaffold_rows[0]["promotion"] == "Promotion not established",
            "empty model repository was presented as qualified weights")
    require(len(proof) == 21, "proof-to-code matrix must contain 21 callables")
    for name, entries, owner in (("math", math, "szl-holdings"),
                                 ("models", models, "SZLHOLDINGS")):
        require(all(row.get("owner") == owner and row.get("private", "").lower() == "false"
                    for row in entries), f"{name} escaped its public owner boundary")
        require(all(re.fullmatch(r"[0-9a-f]{40}", row.get("revision", ""))
                    for row in entries), f"{name} contains an unpinned revision")
    require(all(has_canonical_public_identity(row)
                and row.get("private", "").lower() == "false" for row in assets),
            "full inventory contains private or off-owner assets")
    require(all(set(row) == CSV_ASSET_FIELDS for row in assets),
            "downloadable inventory escaped its closed public schema")
    require(Counter(row["kind"] for row in assets) == Counter({
        "GitHub": 128, "HF Model": 47, "HF Dataset": 37, "HF Space": 35,
    }), "full inventory kind counts changed")
    require(len({(row["kind"], row["id"]) for row in assets}) == len(assets),
            "full inventory contains duplicate assets")
    require(all(row.get("proof_to_code_mapping") == "UNVERIFIED"
                and not row.get("locked_f_id_verified") for row in proof),
            "unverified proof mapping was promoted")

    focused = embedded_json("index.html", "const CATALOG=", ";\nconst $=")
    require(focused.get("schema") == "szl.frontier-public-showcase/v1", "wrong focused schema")
    # Git stores LF text; Windows working trees may expose CRLF. Bind the
    # published page to the canonical committed bytes on both platforms.
    canonical_receipt = receipt_bytes.replace(b"\r\n", b"\n")
    require(focused.get("source_receipt_sha256") == hashlib.sha256(canonical_receipt).hexdigest(),
            "focused page is not bound to the committed public receipt")
    require(len(focused.get("math", [])) == len(math)
            and len(focused.get("models", [])) == len(models), "focused page count drift")
    require(all(row.get("private") is False
                and row.get("owner") == owner
                and re.fullmatch(r"[0-9a-f]{40}", row.get("revision", ""))
                for entries, owner in ((focused["math"], "szl-holdings"),
                                       (focused["models"], "SZLHOLDINGS"))
                for row in entries), "focused page embeds a private, off-owner, or unpinned record")
    full = embedded_json("showcase-public.html", "const DATA=", ";\nconst esc=")
    require(full.get("schema") == "szl.public-org-showcase/v2"
            and full.get("evidence_class") == "DECLARED",
            "full page lacks its declared-evidence schema")
    canonical_showcase_receipt = showcase_receipt_bytes.replace(b"\r\n", b"\n")
    require(full.get("source_receipt_sha256")
            == hashlib.sha256(canonical_showcase_receipt).hexdigest(),
            "full page is not bound to its committed source receipt")
    canonical_projection = {
        "assets-inventory.csv": hashlib.sha256(
            (FRONTIER / "assets-inventory.csv").read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "embedded_assets": hashlib.sha256(json.dumps(
            full.get("assets"), sort_keys=True, ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
        "embedded_findings": hashlib.sha256(json.dumps(
            full.get("findings"), sort_keys=True, ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
        "embedded_coverage": hashlib.sha256(json.dumps(
            full.get("coverage"), sort_keys=True, ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
    }
    require(showcase_receipt.get("public_projection_sha256") == canonical_projection,
            "committed showcase projection does not match its source receipt")
    require(len(full.get("assets", [])) == len(assets), "full page count drift")
    require(all(row.get("private") is False
                and has_canonical_public_identity(row)
                and re.fullmatch(r"[0-9a-f]{40}", row.get("revision", ""))
                and set(row) == ASSET_FIELDS_BY_KIND.get(row.get("kind"))
                for row in full["assets"]),
            "full page embeds a private, off-owner, unpinned, or raw-audit record")
    require(all(row.get("file_count") is None
                and row.get("tensor_artifact") is None
                and row.get("numeric_archives") is None
                and row.get("evidence_files") is None
                for row in full["assets"]
                if row["kind"].startswith("HF ") and row.get("files_coverage") == "UNKNOWN"),
            "unknown Hub file coverage was presented as a complete inventory")
    csv_assets = {(row["kind"], row["id"]): row for row in assets}
    page_assets = {(row["kind"], row["id"]): row for row in full["assets"]}
    require(len(csv_assets) == len(assets) and set(csv_assets) == set(page_assets),
            "downloadable inventory differs from embedded public assets")
    full_formula = page_assets[("HF Model", "SZLHOLDINGS/szl-formulas")]
    require(full_formula["revision"] == "2363023fee676d20480ff015ea8687a0313e42dc"
            and full_formula.get("publication_eligible") is None
            and "unverified" in full_formula.get("status", "").lower(),
            "full inventory promoted the later unbound formula mirror")
    scaffold = page_assets.get(("HF Model", scaffold_id))
    require(scaffold is not None
            and scaffold["category"] == "Repository scaffold"
            and scaffold["file_count"] == 1
            and scaffold["tensor_artifact"] is False
            and scaffold["publication_eligible"] is False,
            "empty model repository gained an unsupported artifact or promotion claim")
    org_card = page_assets.get(("HF Space", "SZLHOLDINGS/README"))
    require(org_card is not None
            and org_card["category"] == "Organization profile card (static Space)"
            and org_card["status"]
            == "DECLARED provider stage RUNNING; product runtime not probed",
            "organization profile card was presented as a product runtime")
    require(all(csv_assets[key][field]
                == ("" if page_assets[key].get(field) is None
                    else str(page_assets[key].get(field)))
                for key in page_assets for field in CSV_ASSET_FIELDS),
            "downloadable inventory fields differ from the embedded projection")
    require(not ({"skills", "local_skills", "local_models"} & set(full)),
            "full page retains local or skills inventory fields")
    public_assets = {row["id"]: row for row in full["assets"]}
    for asset in full["assets"]:
        if asset.get("kind") != "GitHub":
            continue
        exact_runs = [run for run in asset.get("ci", [])
                      if isinstance(run, dict) and run.get("head_sha") == asset.get("revision")]
        exact_success = any(run.get("conclusion") == "success" for run in exact_runs)
        exact_failure = any(run.get("conclusion") in {
            "failure", "timed_out", "startup_failure", "cancelled", "action_required"
        } for run in exact_runs)
        require((exact_success and not exact_failure)
                or asset.get("status") != "Observed runs successful",
                "success label lacks clean sampled runs at the pinned revision")
        require(exact_failure or asset.get("status") != "Workflow failures",
                "historical failure was labeled as a pinned-revision failure")
    findings = full.get("findings")
    require(isinstance(findings, list) and len(findings) == 66,
            "finding list changed without public review")
    for finding in findings:
        asset = public_assets.get(finding.get("asset"))
        require(asset is not None, "finding refers to an asset outside the public set")
        url = finding.get("url", "")
        base = asset["url"].rstrip("/")
        require(isinstance(url, str) and urlsplit(url).scheme == "https"
                and (url == base or url.startswith(base + "/")),
                "finding URL is outside its public asset")
    # Free-text sections are pinned so a future refresh requires review before publication.
    for field, expected in (
        ("findings", "7beb03da5027e6dba178a1a27537dce8432bbde77b9c7ffdd04e3bcb50aa798a"),
        ("coverage", "6fbee9f032f2b41fad969009856be5ccb9db0a962fea4faa5308d62f61247866"),
    ):
        canonical = json.dumps(full[field], sort_keys=True, ensure_ascii=False,
                               separators=(",", ":")).encode("utf-8")
        require(hashlib.sha256(canonical).hexdigest() == expected,
                f"{field} text changed without public review")

    html = (FRONTIER / "index.html").read_text(encoding="utf-8")
    require('<link rel="canonical" href="https://holdings.a-11-oy.com/frontier/">' in html,
            "focused page lacks canonical URL")
    require("proof-to-code-matrix.csv" in html and "PROOF_TO_CODE.md" in html
            and "build_proof_code_matrix.py" in html,
            "focused page lacks the proof-to-code inventory")
    require("Browse all 247 public assets" in html
            and "Browse all 244 public assets" not in html,
            "focused page advertises a stale full-showcase count")
    broad_html = (FRONTIER / "showcase-public.html").read_text(encoding="utf-8")
    require("LOCAL PREVIEW" not in broad_html
            and 'id="state"' not in broad_html
            and '<option value="private">' not in broad_html
            and "Private · internal" not in broad_html
            and "Local model inventory" not in broad_html
            and "installed plugin versions" not in broad_html,
            "public page still offers local or private inventory framing")
    require("Private inventory is outside this public snapshot" in broad_html,
            "public page implies retained private records")
    require('<link rel="canonical" href="https://holdings.a-11-oy.com/frontier/showcase-public.html">'
            in broad_html, "public page lacks canonical URL")
    actual_files = {
        path.relative_to(FRONTIER).as_posix()
        for path in FRONTIER.rglob("*")
        if path.is_file() and "__pycache__" not in path.relative_to(FRONTIER).parts
    }
    require(actual_files == PUBLIC_FILES, "publication file set changed without review")
    for name in PUBLIC_FILES:
        path = FRONTIER / name
        content = path.read_text(encoding="utf-8")
        require(not any(marker in content for marker in
                        ("sk-proj-", "OPENAI_API_KEY", "HF_TOKEN", "C:\\Users\\")),
                f"sensitive marker in {path.relative_to(ROOT)}")
    print("OK: frontier public boundary, source receipt, and proof labels verified.")


if __name__ == "__main__":
    main()
