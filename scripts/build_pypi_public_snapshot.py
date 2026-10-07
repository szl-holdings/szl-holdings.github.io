#!/usr/bin/env python3
"""Validate the reviewed public PyPI projection without network IO or package execution.

The metadata observation establishes that PyPI lists named version artifacts.
Provider artifact hashes and publisher attribution remain DECLARED; this module
neither downloads those artifacts nor verifies attestations or source equivalence.
Only public distribution metadata enters this separate asset namespace. Models,
kernels, repositories and unique project counts are not inferred from packages.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
import hashlib, json
from pathlib import Path, PurePosixPath
import re, sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
COVERAGE = "bounded manifest and README discovery"
LIMITATIONS = (
    "GitHub metadata is bound to the complete 2026-10-06 public snapshot, not a current-default-head claim.",
    "Candidate discovery covers pyproject.toml paths recorded by that snapshot plus explicit PyPI links in its root READMEs. setup.py-only, unlisted legacy or additional package names may be absent.",
    "PyPI project source links are repository declarations; artifact/source equivalence and signer trust remain UNKNOWN.",
    "Artifact SHA256 values and Trusted Publisher identities are DECLARED by PyPI; artifact bytes and attestation signatures were not independently verified.",
    "No distributions were installed or imported, and no model inference, certification or publication was run.",
)
TOP_FIELDS = frozenset({"schema_version", "generated_at", "evidence_class", "public_github_repositories", "immutable_pyproject_inputs", "source_http_successes", "source_errors", "candidate_distributions", "pypi_http_successes", "published_public_distributions", "coverage", "limitations", "packages"})
PACKAGE_FIELDS = frozenset({"package_name", "version", "pypi_url", "source_repositories", "source_records", "summary", "requires_python", "artifacts", "publication_evidence_class", "source_attribution_evidence_class", "source_package_binding", "observed_at"})
SOURCE_FIELDS = frozenset({"repository", "revision", "metadata_path", "metadata_sha256", "declared_name", "declared_version", "discovery"})
ARTIFACT_FIELDS = frozenset({"filename", "url", "sha256", "bytes", "package_type", "uploaded_at", "yanked", "digest_evidence_class", "provenance_url", "attestation_signature_verification"})
COUNTS = frozenset({"public_github_repositories", "immutable_pyproject_inputs", "source_http_successes", "source_errors", "candidate_distributions", "pypi_http_successes", "published_public_distributions"})
PACKAGE_NAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?\Z")
VERSION = re.compile(r"(?:[0-9]+!)?[0-9]+(?:\.[0-9]+)*(?:(?:a|b|rc)[0-9]+)?(?:\.post[0-9]+)?(?:\.dev[0-9]+)?(?:\+[a-z0-9]+(?:[.-][a-z0-9]+)*)?\Z", re.IGNORECASE)
REPOSITORY = re.compile(r"szl-holdings/[A-Za-z0-9_.-]+\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def closed_object(value: object, fields: frozenset[str], label: str) -> dict:
    require(isinstance(value, dict) and set(value) == fields, f"Public PyPI {label} field allowlist mismatch")
    return value


def text(value: object, label: str, *, allow_empty: bool = False) -> str:
    require(isinstance(value, str) and (allow_empty or bool(value)), f"Public PyPI {label} must be text")
    require(not any(ord(char) < 32 and char not in "\n\r\t" for char in value), f"Public PyPI {label} has invalid controls")
    return value


def observed_datetime(value: object) -> datetime:
    require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", value) is not None,
            "Public PyPI observation requires an explicit UTC ISO 8601 timestamp")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Public PyPI observation has an invalid calendar timestamp") from error
    require(stamp.utcoffset() == timedelta(0), "Public PyPI observation must use UTC")
    return stamp


def exact_hex(value: object, pattern: re.Pattern[str], label: str) -> str:
    require(isinstance(value, str) and pattern.fullmatch(value) is not None, f"Public PyPI {label} requires an exact lowercase hexadecimal digest")
    return value


def repository_id(value: object) -> str:
    require(isinstance(value, str) and REPOSITORY.fullmatch(value) is not None and value.split("/")[1] not in {".", ".."},
            "Public PyPI source must be a canonical szl-holdings repository")
    return value


def public_source_ids(rows: list[dict]) -> set[str]:
    """Accept literal public GitHub asset rows or raw public repository metadata."""
    require(isinstance(rows, list) and all(isinstance(row, dict) for row in rows), "Public PyPI source inventory must be an object list")
    result = set()
    for row in rows:
        if row.get("private") is not False:
            continue
        if "full_name" in row:
            if row.get("visibility") != "public":
                continue
            source_id = row.get("full_name")
        else:
            if row.get("kind") != "GitHub":
                continue
            source_id = row.get("id")
        if isinstance(source_id, str) and not source_id.startswith("szl-holdings/"):
            continue
        source_id = repository_id(source_id)
        require(source_id not in result, "Duplicate public GitHub source identity")
        result.add(source_id)
    return result


def parse_json(raw: bytes, label: str) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate JSON key in public PyPI {label}")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid public PyPI {label} JSON") from error


def validate_artifact(artifact: dict, package_name: str, version: str, generated: datetime) -> None:
    closed_object(artifact, ARTIFACT_FIELDS, "artifact")
    filename = text(artifact["filename"], "artifact filename")
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+!-]*", filename) is not None,
            "Public PyPI artifact filename must be a simple distribution filename")
    package_type = artifact["package_type"]
    if package_type == "bdist_wheel":
        match = re.fullmatch(r"(.+)-" + re.escape(version) + r"-(?:[A-Za-z0-9_.]+-)?[A-Za-z0-9_.]+-[A-Za-z0-9_.]+-[A-Za-z0-9_.]+\.whl", filename)
        declared_name = match.group(1) if match else None
    elif package_type == "sdist":
        suffix = next((suffix for suffix in (".tar.gz", ".zip") if filename.endswith(suffix)), None)
        stem = filename[:-len(suffix)] if suffix else ""
        declared_name = stem[:-len(version)-1] if stem.endswith("-" + version) else None
    else:
        declared_name = None
    require(declared_name is not None and normalize_name(declared_name) == normalize_name(package_name),
            "Public PyPI artifact must name its package and exact listed version")
    url = text(artifact["url"], "artifact URL")
    parts = urlsplit(url)
    path = unquote(parts.path)
    require(url == parts.geturl() and parts.scheme == "https" and parts.netloc == "files.pythonhosted.org" and not parts.query and not parts.fragment
            and re.fullmatch(r"/[A-Za-z0-9._+!/-]+", path) is not None and path.startswith("/packages/") and "\\" not in path
            and all(piece not in {".", "..", ""} for piece in path.split("/")[1:])
            and PurePosixPath(path).name == filename,
            "Public PyPI artifact URL must bind the allowed provider origin and exact filename")
    exact_hex(artifact["sha256"], DIGEST, "provider artifact SHA256")
    require(type(artifact["bytes"]) is int and artifact["bytes"] > 0, "Public PyPI artifact size must be a positive byte count")
    require(type(artifact["yanked"]) is bool, "Public PyPI artifact yanked flag must be a boolean")
    require(observed_datetime(artifact["uploaded_at"]) <= generated, "Public PyPI artifact upload is later than its observation")
    require(artifact["digest_evidence_class"] == "DECLARED" and artifact["attestation_signature_verification"] == "UNKNOWN",
            "Provider artifact metadata must not claim independent byte or signature verification")
    provenance = artifact["provenance_url"]
    require(provenance is None or provenance == f"https://pypi.org/integrity/{package_name}/{version}/{filename}/provenance",
            "Public PyPI provenance URL must bind the exact package, version and artifact")


def validate_snapshot(snapshot: dict, public_sources: list[dict], *, now: datetime | None = None) -> None:
    """Enforce the closed public metadata contract; this is not artifact authentication."""
    closed_object(snapshot, TOP_FIELDS, "snapshot")
    require(type(snapshot["schema_version"]) is int and snapshot["schema_version"] == 1, "Unsupported public PyPI schema")
    require(snapshot["evidence_class"] == "MEASURED" and snapshot["coverage"] == COVERAGE, "Public PyPI metadata observation and bounded coverage are required")
    require(snapshot["limitations"] == list(LIMITATIONS), "Public PyPI metadata verification limits must remain explicit")
    generated = observed_datetime(snapshot["generated_at"])
    require(generated <= (now if now is not None else datetime.now(timezone.utc)), "Public PyPI observation is in the future")
    for key in COUNTS:
        require(type(snapshot[key]) is int and snapshot[key] >= 0, "Public PyPI observed counts must be nonnegative integers")
    require(snapshot["source_errors"] == 0 and snapshot["source_http_successes"] == snapshot["immutable_pyproject_inputs"],
            "Public PyPI immutable metadata discovery has incomplete source reads")
    rows = snapshot["packages"]
    require(isinstance(rows, list), "Public PyPI packages must be a list")
    require(snapshot["published_public_distributions"] == len(rows) <= snapshot["pypi_http_successes"] <= snapshot["candidate_distributions"],
            "Public PyPI observed counts conflict with the included distributions")
    allowed_sources = public_source_ids(public_sources)
    names = set()
    for row in rows:
        closed_object(row, PACKAGE_FIELDS, "distribution")
        name, version = row["package_name"], row["version"]
        require(isinstance(name, str) and PACKAGE_NAME.fullmatch(name) is not None, "Public PyPI package name is invalid")
        identity = normalize_name(name)
        require(identity not in names, "Duplicate normalized public PyPI distribution identity")
        names.add(identity)
        require(isinstance(version, str) and VERSION.fullmatch(version) is not None, "Public PyPI version must be an exact supported normalized release version")
        require(row["pypi_url"] == f"https://pypi.org/project/{name}/{version}/", "Public PyPI URL must select its exact listed release")
        require(row["publication_evidence_class"] == "MEASURED" and row["source_attribution_evidence_class"] == "DECLARED"
                and row["source_package_binding"] == "UNKNOWN", "Public PyPI source attribution and package equivalence cannot be upgraded")
        require(observed_datetime(row["observed_at"]) <= generated, "Public PyPI distribution observation is later than the snapshot")
        text(row["summary"], "summary", allow_empty=True)
        text(row["requires_python"], "Python requirement", allow_empty=True)
        repositories = row["source_repositories"]
        require(isinstance(repositories, list) and repositories and all(isinstance(repo, str) for repo in repositories), "Public PyPI declared sources must be a nonempty list")
        require(len(set(repositories)) == len(repositories), "Duplicate declared public PyPI source repository")
        for repo in repositories:
            repository_id(repo)
            require(repo in allowed_sources, "Public PyPI distribution source lacks literal public GitHub visibility")
        source_records = row["source_records"]
        require(isinstance(source_records, list) and source_records, "Public PyPI distribution requires immutable source metadata records")
        metadata = set()
        for source in source_records:
            closed_object(source, SOURCE_FIELDS, "source metadata")
            require(source["repository"] in repositories, "Public PyPI immutable metadata repository is unbound")
            revision = exact_hex(source["revision"], SHA, "GitHub source revision")
            exact_hex(source["metadata_sha256"], DIGEST, "source metadata SHA256")
            path = source["metadata_path"]
            require(isinstance(path, str) and re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", path) is not None
                    and all(part not in {".", ".."} for part in path.split("/")) and path.split("/")[-1] == "pyproject.toml",
                    "Public PyPI metadata path must be a canonical relative pyproject.toml path")
            require(source["discovery"] == "immutable pyproject name", "Public PyPI source requires an immutable pyproject name declaration")
            declared_name = source["declared_name"]
            require(isinstance(declared_name, str) and PACKAGE_NAME.fullmatch(declared_name) is not None and normalize_name(declared_name) == identity,
                    "Public PyPI immutable source name differs from the distribution identity")
            declared_version = source["declared_version"]
            require(declared_version is None or isinstance(declared_version, str) and VERSION.fullmatch(declared_version) is not None,
                    "Public PyPI source version must remain a declared supported version or null")
            key = (source["repository"], revision, path)
            require(key not in metadata, "Duplicate immutable public PyPI source metadata")
            metadata.add(key)
        require({source["repository"] for source in source_records} == set(repositories),
                "Public PyPI declared source coverage conflicts with immutable metadata records")
        artifacts = row["artifacts"]
        require(isinstance(artifacts, list) and artifacts, "Public PyPI distribution requires artifact metadata")
        filenames = set()
        for artifact in artifacts:
            validate_artifact(artifact, name, version, generated)
            require(artifact["filename"] not in filenames, "Duplicate public PyPI artifact filename")
            filenames.add(artifact["filename"])


def load_snapshot(path: Path, public_sources: list[dict], *, expected_sha256: str | None = None, now: datetime | None = None) -> dict:
    """Read once, optionally bind reviewed bytes, then validate without network IO."""
    raw = Path(path).read_bytes()
    if expected_sha256 is not None:
        exact_hex(expected_sha256, DIGEST, "reviewed input SHA256")
        require(hashlib.sha256(raw).hexdigest() == expected_sha256, "Public PyPI reviewed input SHA256 mismatch")
    snapshot = parse_json(raw, "snapshot")
    validate_snapshot(snapshot, public_sources, now=now)
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True, help="Validate committed metadata without modifying files")
    parser.add_argument("--snapshot", type=Path, default=ROOT / "estate" / "pypi-packages.json")
    parser.add_argument("--public-sources", type=Path, default=ROOT / "estate" / "public-snapshot.json")
    parser.add_argument("--expected-sha256", help="Optional reviewed public PyPI input byte hash")
    args = parser.parse_args(argv)
    try:
        sources = parse_json(args.public_sources.read_bytes(), "GitHub source inventory")
        if isinstance(sources, dict):
            sources = sources.get("assets")
        snapshot = load_snapshot(args.snapshot, sources, expected_sha256=args.expected_sha256)
    except (OSError, ValueError) as error:
        print(f"Public PyPI snapshot validation stopped: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"observed_at": snapshot["generated_at"], "public_pypi_distributions": len(snapshot["packages"]),
                      "artifact_bytes_verified": "NOT RUN", "attestation_signature_verification": "NOT RUN", "source_package_binding": "UNKNOWN"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
