"""Fail closed if the public frontier bundle loses its source or privacy boundary."""

from __future__ import annotations

import csv
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
    require(len(math) == 39 and len(models) == 47 and len(assets) == 244,
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
    require(all(row.get("owner") in {"szl-holdings", "SZLHOLDINGS"}
                and row.get("private", "").lower() == "false" for row in assets),
            "full inventory contains private or off-owner assets")
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
    require(len(full.get("assets", [])) == len(assets), "full page count drift")
    require(all(row.get("private") is False
                and row.get("owner") in {"szl-holdings", "SZLHOLDINGS"}
                and re.fullmatch(r"[0-9a-f]{40}", row.get("revision", ""))
                for row in full["assets"]),
            "full page embeds a private, off-owner, or unpinned record")
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
    require(page_assets[("HF Model", "SZLHOLDINGS/szl-formulas")]["revision"]
            == replacements[0]["sha"],
            "searchable atlas does not use the published formula mirror revision")
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
            and org_card["status"] == "Public source observed; product runtime not probed",
            "organization profile card was presented as a product runtime")
    require(all(csv_assets[key]["status"] == page_assets[key]["status"]
                and csv_assets[key]["revision"] == page_assets[key]["revision"]
                for key in page_assets), "downloadable inventory status or revision differs from page")
    require(full.get("local_skills") == [] and full.get("local_models") == "",
            "full page embeds local inventory")
    require(full.get("skills") == [], "full page embeds a skills inventory")
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
    require(isinstance(findings, list) and len(findings) == 41,
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
        ("findings", "8e2511f47e4ec6bcfda63fa2d799748b59d88e42e5c97a53c2bf0db8aed08dd1"),
        ("coverage", "d04ac54011a07354a082d3f2a82cf987f2b5edc166bac2c3c2d51499c6e39744"),
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
    broad_html = (FRONTIER / "showcase-public.html").read_text(encoding="utf-8")
    require("LOCAL PREVIEW" not in broad_html and '<option value="private">' not in broad_html,
            "public page still offers local or private inventory framing")
    require("Private inventory is outside this public snapshot" in broad_html,
            "public page implies retained private records")
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
