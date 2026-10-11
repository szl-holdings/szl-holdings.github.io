#!/usr/bin/env python3
"""Measure common paths in dated public Kernel Hub and model-mirror trees."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import parse_qs, quote, unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from build_kernel_public_snapshot import parse_json, validate_snapshot

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "estate" / "kernel-shared-byte-readback.json"
SOURCE_REVISION = "dccee6aeda928aa24f40a8a1e568ad58bb925e67"
MANIFEST_SHA256 = "298466da9f5d8102e65017bbc9919f5de308c025e4cb164522181a063c6190f7"
REPORT_SHA256 = "11e13d26297287644a71153c13a3d9265d0930ed4b0241473a0e34108c8777ed"
SCHEMA = "szl.public-kernel-shared-byte-readback/v1"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
IDENTITY = re.compile(r"SZLHOLDINGS/[A-Za-z0-9_.-]+\Z")
MAX_TREE_BYTES = 2_000_000
MAX_TREE_PAGES = 10
MAX_FILE_BYTES = 250_000
MAX_DECLARED_FILE_BYTES = 10_000_000_000
MAX_TRANSFER_BYTES = 10_000_000


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_blob(path: str) -> bytes:
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{SOURCE_REVISION}:{path}"],
                          capture_output=True, check=True, timeout=20).stdout


def pinned_manifest() -> dict:
    raw = git_blob("estate/kernel-distributions.json")
    if digest(raw) != MANIFEST_SHA256:
        raise ValueError("kernel source manifest differs from pinned Git bytes")
    manifest = parse_json(raw, "kernel source manifest")
    validate_snapshot(manifest)
    public = parse_json(git_blob("estate/public-snapshot.json"), "dated public inventory")
    if not isinstance(public, dict) or not isinstance(public.get("assets"), list):
        raise ValueError("dated public inventory is invalid")
    models = {(item.get("id"), item.get("kind")) for item in public["assets"]
              if isinstance(item, dict) and item.get("private") is False}
    for row in manifest["distributions"]:
        if not IDENTITY.fullmatch(row["id"]) or (row["id"], "HF Model") not in models:
            raise ValueError("kernel mirror is not a literal-public model identity")
        if not SHA40.fullmatch(row["modelMirrorRevision"]):
            raise ValueError("kernel mirror revision is not immutable")
    return manifest


class SameHostRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        if target.scheme != "https" or target.netloc != "huggingface.co":
            raise ValueError("Hub redirect left the allowlisted host")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def get(url: str, *, limit: int, expected_paths: tuple[str, ...] | None = None,
        cache_etag: str | None = None, allow_next: bool = False) -> bytes | tuple[bytes, str | None]:
    request = Request(url, headers={"User-Agent": "szl-kernel-byte-readback/1", "Accept-Encoding": "identity"})
    with build_opener(SameHostRedirect).open(request, timeout=25) as response:
        target = urlsplit(response.geturl())
        if response.status != 200 or target.scheme != "https" or target.netloc != "huggingface.co":
            raise ValueError("Hub response status or host changed")
        if expected_paths is not None:
            final_path = unquote(target.path)
            if final_path not in expected_paths or target.fragment:
                raise ValueError("Hub response path lost the pinned repository binding")
            if cache_etag is not None and len(expected_paths) == 2 and final_path == expected_paths[1]:
                expected_query = {expected_paths[0]: [""], "etag": [f'"{cache_etag}"']}
                if parse_qs(target.query, keep_blank_values=True) != expected_query:
                    raise ValueError("Hub cache query lost source path or tree etag")
            elif target.query != urlsplit(url).query:
                raise ValueError("Hub response query lost the pinned repository binding")
        link = response.headers.get("Link", "")
        next_match = re.fullmatch(r'<([^>]+)>;\s*rel="next"', link) if link else None
        if link and not next_match:
            raise ValueError("Hub pagination header is unsupported")
        if next_match and not allow_next:
            raise ValueError("Hub tree response is paginated")
        declared_length = response.headers.get("Content-Length")
        if declared_length is not None and int(declared_length) > limit:
            raise ValueError("Hub response exceeds byte cap")
        chunks = []
        count = 0
        while block := response.read(min(65536, limit - count + 1)):
            count += len(block)
            if count > limit:
                raise ValueError("Hub response exceeds byte cap")
            chunks.append(block)
    raw = b"".join(chunks)
    return (raw, next_match.group(1) if next_match else None) if allow_next else raw


def safe_path(path: object) -> str:
    if (not isinstance(path, str) or not path or path.startswith("/") or "\\" in path
            or any(part in {"", ".", ".."} for part in path.split("/"))
            or any(ord(char) < 32 for char in path)):
        raise ValueError("unsafe Hub tree file path")
    return path


def tree(kind: str, row: dict, revision: str) -> tuple[dict, str, int]:
    prefix = "kernels/" if kind == "kernel" else "models/"
    url = f"https://huggingface.co/api/{prefix}{row['id']}/tree/{revision}?recursive=true&expand=true"
    listing = []
    pages = []
    seen = set()
    while url:
        if url in seen or len(pages) >= MAX_TREE_PAGES:
            raise ValueError("Hub tree pagination repeated or exceeded page cap")
        seen.add(url)
        raw, next_url = get(url, limit=MAX_TREE_BYTES,
                            expected_paths=(f"/api/{prefix}{row['id']}/tree/{revision}",),
                            allow_next=True)
        page = parse_json(raw, "Hub tree")
        if not isinstance(page, list):
            raise ValueError("Hub tree page must be a list")
        listing.extend(page)
        pages.append(raw)
        if next_url:
            target = urlsplit(next_url)
            query = parse_qs(target.query)
            expected_path = f"/api/{prefix}{row['id']}/tree/{revision}"
            if (target.scheme != "https" or target.netloc != "huggingface.co"
                    or target.path != expected_path or target.fragment
                    or set(query) != {"recursive", "expand", "limit", "cursor"}
                    or query["recursive"] != ["true"] or query["expand"] != ["true"]
                    or query["limit"] != ["50"] or len(query["cursor"]) != 1):
                raise ValueError("Hub tree next page escaped pinned source")
        url = next_url
    files = {}
    for item in listing:
        if not isinstance(item, dict) or item.get("type") not in {"directory", "file"}:
            raise ValueError("Hub tree item is invalid")
        if item["type"] != "file":
            continue
        path = safe_path(item.get("path"))
        size = item.get("size")
        oid = item.get("oid")
        if (path in files or type(size) is not int or size < 0 or size > MAX_DECLARED_FILE_BYTES
                or not isinstance(oid, str) or not SHA40.fullmatch(oid)):
            raise ValueError("Hub tree has duplicate or unbound file")
        files[path] = {"bytes": size, "git_blob_oid": oid, "lfs": item.get("lfs") is not None}
    framed = b"".join(len(page).to_bytes(8, "big") + page for page in pages)
    return files, digest(framed), len(pages)


def measure_one(kind: str, row: dict, path: str, info: dict) -> dict:
    prefix = "kernels/" if kind == "kernel" else ""
    revision = row["revision"] if kind == "kernel" else row["modelMirrorRevision"]
    encoded = quote(path, safe="/")
    url = f"https://huggingface.co/{prefix}{row['id']}/resolve/{revision}/{encoded}"
    try:
        source_path = f"/{prefix}{row['id']}/resolve/{revision}/{path}"
        cache_prefix = "kernels/" if kind == "kernel" else "models/"
        cache_path = f"/api/resolve-cache/{cache_prefix}{row['id']}/{revision}/{path}"
        raw = get(url, limit=MAX_FILE_BYTES, expected_paths=(source_path, cache_path),
                  cache_etag=info["git_blob_oid"])
    except Exception as error:
        raise ValueError(f"{row['id']} {kind} {path}: pinned public byte read failed: {error}") from error
    observed_oid = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    if len(raw) != info["bytes"] or observed_oid != info["git_blob_oid"]:
        raise ValueError("downloaded Hub bytes differ from immutable tree metadata")
    return {"bytes": len(raw), "sha256": digest(raw)}


def model_access(row: dict) -> tuple[dict, str]:
    raw = get(f"https://huggingface.co/api/models/{row['id']}", limit=MAX_TREE_BYTES,
              expected_paths=(f"/api/models/{row['id']}",))
    metadata = parse_json(raw, "Hub model access")
    if (not isinstance(metadata, dict) or metadata.get("id") != row["id"]
            or metadata.get("private") is not False or metadata.get("gated") not in (False, "manual", "auto")
            or not isinstance(metadata.get("sha"), str) or not SHA40.fullmatch(metadata["sha"])):
        raise ValueError("Hub model access metadata is invalid or private")
    return metadata, digest(raw)


def collect_pair(row: dict) -> dict:
    access, access_sha = model_access(row)
    kernels, kernel_tree_sha, kernel_pages = tree("kernel", row, row["revision"])
    mirrors, mirror_tree_sha, mirror_pages = tree("model", row, row["modelMirrorRevision"])
    shared = sorted(set(kernels) & set(mirrors))
    if any(kernels[path]["lfs"] or mirrors[path]["lfs"] or
           kernels[path]["bytes"] > MAX_FILE_BYTES or mirrors[path]["bytes"] > MAX_FILE_BYTES
           for path in shared):
        raise ValueError("shared Hub file requires LFS or exceeds bounded byte read")
    transfer = sum(kernels[path]["bytes"] + mirrors[path]["bytes"] for path in shared)
    if transfer > MAX_TRANSFER_BYTES:
        raise ValueError("pair exceeds bounded byte read")

    def compare(path: str) -> dict:
        kernel = measure_one("kernel", row, path, kernels[path]) if access["gated"] is False else None
        mirror = measure_one("model", row, path, mirrors[path]) if access["gated"] is False else None
        return {"path": path, "kernel_declared": {key: kernels[path][key] for key in ("bytes", "git_blob_oid")},
                "mirror_declared": {key: mirrors[path][key] for key in ("bytes", "git_blob_oid")},
                "kernel_measured": kernel, "mirror_measured": mirror,
                "bytes_match": kernel == mirror if kernel is not None else None}

    if access["gated"] is False:
        with ThreadPoolExecutor(max_workers=4) as pool:
            files = list(pool.map(compare, shared))
    else:
        files = [compare(path) for path in shared]
    measured = access["gated"] is False
    return {"id": row["id"], "kernel_revision": row["revision"],
            "model_mirror_revision": row["modelMirrorRevision"],
            "model_access_current_revision": access["sha"], "model_access_gated": access["gated"],
            "model_access_metadata_sha256": access_sha,
            "kernel_tree_sha256": kernel_tree_sha, "mirror_tree_sha256": mirror_tree_sha,
            "kernel_tree_pages": kernel_pages, "mirror_tree_pages": mirror_pages,
            "kernel_only_paths": sorted(set(kernels) - set(mirrors)),
            "mirror_only_paths": sorted(set(mirrors) - set(kernels)),
            "shared_files": files, "kernel_file_count": len(kernels), "mirror_file_count": len(mirrors),
            "access_status": "MEASURED" if measured else "UNAVAILABLE",
            "shared_count": len(files), "measured_count": len(files) if measured else 0,
            "unavailable_count": 0 if measured else len(files),
            "matched_count": sum(item["bytes_match"] is True for item in files),
            "differing_count": sum(item["bytes_match"] is False for item in files),
            "measured_bytes": transfer if measured else 0, "whole_artifact_equivalence": "UNKNOWN"}


def collect(manifest: dict) -> dict:
    pairs = [collect_pair(row) for row in manifest["distributions"]]
    return {"schema": SCHEMA, "observed_at": datetime.now(timezone.utc).isoformat(),
            "evidence_class": "MEASURED", "scope": "PINNED_PUBLIC_SHARED_PATH_BYTES_ONLY",
            "source_revision": SOURCE_REVISION, "source_manifest_sha256": MANIFEST_SHA256,
            "source_manifest_observed_at": manifest["observed_at"],
            "pair_count": len(pairs), "measured_pair_count": sum(item["access_status"] == "MEASURED" for item in pairs),
            "unavailable_pair_count": sum(item["access_status"] == "UNAVAILABLE" for item in pairs),
            "shared_path_count": sum(item["shared_count"] for item in pairs),
            "measured_shared_count": sum(item["measured_count"] for item in pairs),
            "unavailable_shared_count": sum(item["unavailable_count"] for item in pairs),
            "matched_count": sum(item["matched_count"] for item in pairs),
            "differing_count": sum(item["differing_count"] for item in pairs),
            "measured_bytes": sum(item["measured_bytes"] for item in pairs),
            "whole_artifact_equivalence": "UNKNOWN", "runtime_behavior": "NOT RUN",
            "independent_replay": "NOT RUN", "pairs": pairs}


def validate_report(report: dict, manifest: dict) -> None:
    fields = {"schema", "observed_at", "evidence_class", "scope", "source_revision", "source_manifest_sha256",
              "source_manifest_observed_at", "pair_count", "measured_pair_count", "unavailable_pair_count",
              "shared_path_count", "measured_shared_count", "unavailable_shared_count", "matched_count", "differing_count",
              "measured_bytes", "whole_artifact_equivalence", "runtime_behavior", "independent_replay", "pairs"}
    if not isinstance(report, dict) or set(report) != fields or report["schema"] != SCHEMA:
        raise ValueError("kernel readback report schema mismatch")
    observed = datetime.fromisoformat(report["observed_at"].replace("Z", "+00:00"))
    source_time = datetime.fromisoformat(manifest["observed_at"].replace("Z", "+00:00"))
    if (observed.tzinfo is None or observed.utcoffset() != timezone.utc.utcoffset(observed)
            or observed < source_time or observed > datetime.now(timezone.utc)):
        raise ValueError("kernel readback observation time invalid")
    if (report["evidence_class"] != "MEASURED" or report["scope"] != "PINNED_PUBLIC_SHARED_PATH_BYTES_ONLY"
            or report["source_revision"] != SOURCE_REVISION or report["source_manifest_sha256"] != MANIFEST_SHA256
            or report["source_manifest_observed_at"] != manifest["observed_at"]
            or report["whole_artifact_equivalence"] != "UNKNOWN"
            or report["runtime_behavior"] != "NOT RUN" or report["independent_replay"] != "NOT RUN"):
        raise ValueError("kernel readback scope or authority changed")
    pairs = report["pairs"]
    if not isinstance(pairs, list) or len(pairs) != len(manifest["distributions"]):
        raise ValueError("kernel pair coverage differs from pinned manifest")
    for item, source in zip(pairs, manifest["distributions"]):
        pair_fields = {"id", "kernel_revision", "model_mirror_revision", "model_access_current_revision",
                       "model_access_gated", "model_access_metadata_sha256",
                       "kernel_tree_sha256", "mirror_tree_sha256", "kernel_tree_pages", "mirror_tree_pages",
                       "kernel_only_paths", "mirror_only_paths", "shared_files", "kernel_file_count", "mirror_file_count",
                       "access_status", "shared_count", "measured_count", "unavailable_count",
                       "matched_count", "differing_count", "measured_bytes", "whole_artifact_equivalence"}
        if (not isinstance(item, dict) or set(item) != pair_fields or item["id"] != source["id"]
                or item["kernel_revision"] != source["revision"]
                or item["model_mirror_revision"] != source["modelMirrorRevision"]
                or not isinstance(item["model_access_current_revision"], str)
                or not SHA40.fullmatch(item["model_access_current_revision"])
                or item["model_access_gated"] not in (False, "manual", "auto")
                or not isinstance(item["model_access_metadata_sha256"], str)
                or not SHA64.fullmatch(item["model_access_metadata_sha256"])
                or item["access_status"] != ("MEASURED" if item["model_access_gated"] is False else "UNAVAILABLE")
                or item["whole_artifact_equivalence"] != "UNKNOWN"
                or any(not isinstance(item[key], str) or not SHA64.fullmatch(item[key])
                       for key in ("kernel_tree_sha256", "mirror_tree_sha256"))
                or any(type(item[key]) is not int or not 1 <= item[key] <= MAX_TREE_PAGES
                       for key in ("kernel_tree_pages", "mirror_tree_pages"))):
            raise ValueError("kernel pair source or field mismatch")
        unique = set()
        for key in ("kernel_only_paths", "mirror_only_paths"):
            if (not isinstance(item[key], list) or item[key] != sorted(set(item[key]))
                    or any(safe_path(path) != path for path in item[key])):
                raise ValueError("kernel unmatched path list invalid")
            if unique.intersection(item[key]):
                raise ValueError("kernel unmatched path lists overlap")
            unique.update(item[key])
        files = item["shared_files"]
        if (not isinstance(files, list) or any(not isinstance(file, dict) for file in files)
                or [file.get("path") for file in files] != sorted({file.get("path") for file in files})):
            raise ValueError("kernel shared path coverage invalid")
        for file in files:
            if (not isinstance(file, dict) or set(file) != {"path", "kernel_declared", "mirror_declared",
                                                          "kernel_measured", "mirror_measured", "bytes_match"}
                    or safe_path(file["path"]) != file["path"] or file["path"] in unique):
                raise ValueError("kernel shared file fields invalid")
            for side in ("kernel", "mirror"):
                declared = file[f"{side}_declared"]
                measured = file[f"{side}_measured"]
                if (not isinstance(declared, dict) or set(declared) != {"bytes", "git_blob_oid"}
                        or type(declared["bytes"]) is not int or not 0 <= declared["bytes"] <= MAX_FILE_BYTES
                        or not isinstance(declared["git_blob_oid"], str)
                        or not SHA40.fullmatch(declared["git_blob_oid"])):
                    raise ValueError("kernel per-file byte declaration invalid")
                if item["access_status"] == "MEASURED":
                    if (not isinstance(measured, dict) or set(measured) != {"bytes", "sha256"}
                            or measured["bytes"] != declared["bytes"]
                            or not isinstance(measured["sha256"], str)
                            or not SHA64.fullmatch(measured["sha256"])):
                        raise ValueError("kernel measured bytes invalid")
                elif measured is not None:
                    raise ValueError("gated mirror was claimed measured")
            expected_match = (file["kernel_measured"] == file["mirror_measured"]
                              if item["access_status"] == "MEASURED" else None)
            if file["bytes_match"] is not expected_match:
                raise ValueError("kernel per-file match flag invalid")
        if (type(item["kernel_file_count"]) is not int or item["kernel_file_count"] != len(item["kernel_only_paths"]) + len(files)
                or type(item["mirror_file_count"]) is not int or item["mirror_file_count"] != len(item["mirror_only_paths"]) + len(files)
                or type(item["shared_count"]) is not int or item["shared_count"] != len(files)
                or type(item["measured_count"]) is not int
                or item["measured_count"] != (len(files) if item["access_status"] == "MEASURED" else 0)
                or type(item["unavailable_count"]) is not int
                or item["unavailable_count"] != (0 if item["access_status"] == "MEASURED" else len(files))
                or type(item["matched_count"]) is not int
                or item["matched_count"] != sum(file["bytes_match"] is True for file in files)
                or type(item["differing_count"]) is not int
                or item["differing_count"] != sum(file["bytes_match"] is False for file in files)
                or type(item["measured_bytes"]) is not int or item["measured_bytes"] != sum(
                    file["kernel_measured"]["bytes"] + file["mirror_measured"]["bytes"] for file in files
                    if file["kernel_measured"] is not None)):
            raise ValueError("kernel pair totals invalid")
    if (type(report["pair_count"]) is not int or report["pair_count"] != len(pairs)
            or type(report["measured_pair_count"]) is not int
            or report["measured_pair_count"] != sum(item["access_status"] == "MEASURED" for item in pairs)
            or type(report["unavailable_pair_count"]) is not int
            or report["unavailable_pair_count"] != sum(item["access_status"] == "UNAVAILABLE" for item in pairs)
            or type(report["shared_path_count"]) is not int or report["shared_path_count"] != sum(item["shared_count"] for item in pairs)
            or type(report["measured_shared_count"]) is not int
            or report["measured_shared_count"] != sum(item["measured_count"] for item in pairs)
            or type(report["unavailable_shared_count"]) is not int
            or report["unavailable_shared_count"] != sum(item["unavailable_count"] for item in pairs)
            or type(report["matched_count"]) is not int or report["matched_count"] != sum(item["matched_count"] for item in pairs)
            or type(report["differing_count"]) is not int or report["differing_count"] != sum(item["differing_count"] for item in pairs)
            or type(report["measured_bytes"]) is not int or report["measured_bytes"] != sum(item["measured_bytes"] for item in pairs)
            or report["measured_bytes"] > MAX_TRANSFER_BYTES):
        raise ValueError("kernel readback totals invalid")


def check_committed_report(raw: bytes, manifest: dict) -> dict:
    """Validate the exact committed report bytes and their structural scope offline."""
    if digest(raw) != REPORT_SHA256:
        raise ValueError("kernel report differs from the reviewed byte readback")
    report = parse_json(raw, "kernel byte readback")
    validate_report(report, manifest)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate the committed report without provider reads")
    parser.add_argument("--output", type=Path, help="Fresh output path for bounded live provider reads")
    args = parser.parse_args()
    manifest = pinned_manifest()
    if args.check:
        report = check_committed_report((args.output or REPORT).read_bytes(), manifest)
        print(f"offline hash-bound report covers {report['pair_count']} kernel pairs and "
              f"{report['measured_shared_count']} measured shared paths; no provider replay")
        return 0
    if args.output is None:
        parser.error("a fresh --output is required for live provider reads")
    output = args.output.resolve()
    if output.exists() or output in {Path(__file__).resolve(), ROOT / "estate" / "kernel-distributions.json"}:
        raise ValueError("kernel output must be a fresh non-source file")
    report = collect(manifest)
    validate_report(report, manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        handle.write((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: report[key] for key in ("pair_count", "shared_path_count", "matched_count", "differing_count", "measured_bytes")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
