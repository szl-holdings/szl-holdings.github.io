#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replay four SAMPLE GovernedAction cases against immutable canonical bytes."""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

SOURCE_COMMIT = "1467fcbd1ff57b955d588c73e64a541ebc16770f"
SOURCE_REPOSITORY = "https://github.com/szl-holdings/szl-receipt"
SOURCE_LOCK_SHA256 = "e590d54e19acb59d10268256a9755b557d76edc1719ca9f3f726a1733461146b"
FIXTURE_SHA256 = "0a74c526872907b87d6b7676be0a0ecd0c8780cb643c615cfc4dfc9aa1be6306"
SCHEMA = "szl.receipt-replay-result/v1"
BUNDLE = Path(__file__).resolve().parent
DEPENDENCIES = {
    "cryptography": "50.0.1", "in-toto-attestation": "0.9.3",
    "protobuf": "7.36.2", "cffi": "2.1.1", "pycparser": "3.0",
}
CASE_IDS = ("complete_signed", "tampered_payload", "incomplete_signed", "unsigned_honest")
EXPECTATIONS = [
    {"id": "complete_signed", "expected_status": "PASS", "required_reasons": [], "signature_valid": True},
    {"id": "tampered_payload", "expected_status": "INCOMPLETE", "required_reasons": ["signature-mismatch"], "signature_valid": False},
    {"id": "incomplete_signed", "expected_status": "INCOMPLETE", "required_reasons": ["evidence-missing:runtime_witness", "evidence-role-set-mismatch", "missing-subject:runtime_witness"], "signature_valid": True},
    {"id": "unsigned_honest", "expected_status": "INCOMPLETE", "required_reasons": ["signature-not-present", "dsse-signature-count-not-one"], "signature_valid": False},
]


class ReplayError(ValueError):
    """A source, runtime or fixture binding failed before replay."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def load_json(path: Path) -> dict:
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ReplayError("duplicate JSON key")
            value[key] = item
        return value
    try:
        value = json.loads(path.read_bytes(), object_pairs_hook=unique)
    except (OSError, ValueError) as exc:
        raise ReplayError("bundle JSON is missing or invalid") from exc
    if not isinstance(value, dict):
        raise ReplayError("bundle JSON must be an object")
    return value


def git(source: Path, *arguments: str) -> bytes:
    try:
        environment = os.environ.copy()
        environment.update({"GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"})
        return subprocess.run(
            ["git", "--no-optional-locks", "-c", "protocol.allow=never", "-C", str(source), *arguments],
            check=True, capture_output=True, timeout=30, env=environment,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise ReplayError("source Git binding is unavailable") from exc


def verify_source(source: Path, bundle: Path = BUNDLE) -> dict:
    """Bind the full Python source set and metadata to Git object bytes."""
    if sha256((bundle / "source-lock.json").read_bytes()) != SOURCE_LOCK_SHA256:
        raise ReplayError("reviewed source lock bytes differ")
    lock = load_json(bundle / "source-lock.json")
    if set(lock) != {"schema", "repository", "commit", "minimum_python",
                     "dependencies", "dependency_lock_sha256", "files"}:
        raise ReplayError("source lock fields differ from the reviewed contract")
    if (lock["schema"] != "szl.receipt-replay-source-lock/v1"
            or lock["repository"] != SOURCE_REPOSITORY
            or lock["commit"] != SOURCE_COMMIT
            or lock["minimum_python"] != "3.11"
            or lock["dependencies"] != DEPENDENCIES):
        raise ReplayError("source lock identity or runtime binding differs")
    if sha256((bundle / "requirements.lock").read_bytes()) != lock["dependency_lock_sha256"]:
        raise ReplayError("reviewed dependency lock bytes differ")
    source = source.resolve(strict=True)
    if git(source, "rev-parse", "HEAD").decode("ascii").strip() != SOURCE_COMMIT:
        raise ReplayError("source checkout HEAD differs from the locked commit")
    tree = git(source, "ls-tree", "-r", "--name-only", SOURCE_COMMIT, "--", "src")
    package_files = {p for p in tree.decode("utf-8").splitlines() if p.endswith(".py")}
    if any(not p.startswith("src/szl_receipt/") for p in package_files):
        raise ReplayError("canonical import root contains an unexpected Python module")
    files = lock["files"]
    if not isinstance(files, dict) or set(files) != package_files | {"pyproject.toml", "LICENSE"}:
        raise ReplayError("source lock does not cover the complete Python module set")
    if not (source / "src").is_dir():
        raise ReplayError("source import root is unavailable")
    actual_python = set()
    for path in (source / "src").rglob("*"):
        resolved = path.resolve()
        if path.is_symlink() or not resolved.is_relative_to(source / "src"):
            raise ReplayError("source import root contains a link outside its binding")
        if path.suffix.lower() in {".pyc", ".pyo", ".pyd", ".so"}:
            raise ReplayError("source import root contains unbound executable bytes")
        if path.is_file() and path.suffix.lower() == ".py":
            actual_python.add(path.relative_to(source).as_posix())
    if actual_python != package_files:
        raise ReplayError("source import root contains missing or extra Python modules")
    for name, digest in files.items():
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ReplayError("source lock digest is invalid")
        path = source / name
        if path.is_symlink() or not path.resolve().is_relative_to(source):
            raise ReplayError("locked source file is outside its binding")
        blob = git(source, "show", SOURCE_COMMIT + ":" + name)
        if sha256(blob) != digest or sha256(path.read_bytes()) != digest:
            raise ReplayError("locked source file bytes differ: " + name)
    return lock


def verify_runtime() -> dict:
    if sys.version_info < (3, 11) or platform.python_implementation() != "CPython":
        raise ReplayError("replay requires reviewed CPython 3.11 or newer")
    if not sys.flags.isolated:
        raise ReplayError("run the replay with Python -I to exclude ambient import paths")
    actual = {}
    for name, expected in DEPENDENCIES.items():
        try:
            actual[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise ReplayError("reviewed runtime dependency is unavailable: " + name) from exc
        if actual[name] != expected:
            raise ReplayError("runtime dependency version differs: " + name)
    return {"implementation": "CPython", "python": platform.python_version(),
            "operating_system": platform.system(), "dependencies": actual,
            "installed_dependency_byte_integrity": "UNKNOWN"}


def load_canonical(source: Path):
    if any(name == "szl_receipt" or name.startswith("szl_receipt.") for name in sys.modules):
        raise ReplayError("a canonical package was imported before source verification")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(source / "src"))
    package = importlib.import_module("szl_receipt")
    api = importlib.import_module("szl_receipt.governed_action")
    canonical = importlib.import_module("szl_receipt._canonical")
    for name, module in list(sys.modules.items()):
        if name == "szl_receipt" or name.startswith("szl_receipt."):
            expected = (source / "src" / Path(*name.split("."))).with_suffix(".py")
            if name == "szl_receipt":
                expected = source / "src/szl_receipt/__init__.py"
            if Path(module.__file__).resolve() != expected.resolve():
                raise ReplayError("a canonical module resolved outside the locked source")
    return package, api, canonical


def signature_valid(api, envelope: dict, public_key: bytes) -> bool:
    """Measure authenticity separately from the admission verdict."""
    if len(envelope["signatures"]) != 1:
        return False
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    try:
        key = serialization.load_pem_public_key(public_key)
        key.verify(base64.b64decode(envelope["signatures"][0]["sig"], validate=True),
                   api.dsse_pae(envelope["payloadType"], base64.b64decode(envelope["payload"], validate=True)),
                   ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def run(source: Path, bundle: Path = BUNDLE) -> dict:
    runtime = verify_runtime()
    source = source.resolve(strict=True)
    lock = verify_source(source, bundle)
    if sha256((bundle / "sample-input.json").read_bytes()) != FIXTURE_SHA256:
        raise ReplayError("reviewed SAMPLE fixture bytes differ")
    fixture = load_json(bundle / "sample-input.json")
    if (set(fixture) != {"schema", "evidence_class", "description", "inputs", "cases"}
            or fixture["schema"] != "szl.receipt-replay-fixtures/v1"
            or fixture["evidence_class"] != "SAMPLE"
            or fixture["cases"] != EXPECTATIONS
            or not isinstance(fixture["inputs"], dict)
            or fixture["inputs"].get("side_effects") != []):
        raise ReplayError("fixture contract differs from the four reviewed cases")
    package, api, canonical = load_canonical(source)
    private_key, public_key = package.generate_keypair()
    complete = api.emit_governed_action(**fixture["inputs"], private_key_pem=private_key)
    tampered = copy.deepcopy(complete)
    statement = json.loads(base64.b64decode(tampered["payload"]))
    statement["predicate"]["action"]["id"] = "sample-local-replay-changed"
    tampered["payload"] = base64.b64encode(canonical.canonical_json(statement)).decode("ascii")
    incomplete_inputs = copy.deepcopy(fixture["inputs"])
    del incomplete_inputs["evidence"]["runtime_witness"]
    witness_name = incomplete_inputs["subject_roles"]["runtime_witness"]
    incomplete_inputs["subjects"] = [subject for subject in incomplete_inputs["subjects"]
                                     if subject["name"] != witness_name]
    incomplete = api.emit_governed_action(**incomplete_inputs, private_key_pem=private_key)
    unsigned = api.emit_governed_action(**fixture["inputs"], private_key_pem=None)
    envelopes = dict(zip(CASE_IDS, (complete, tampered, incomplete, unsigned)))
    cases = []
    for expectation in fixture["cases"]:
        envelope = envelopes[expectation["id"]]
        verdict = api.verify_governed_action(envelope, public_key)
        authentic = signature_valid(api, envelope, public_key)
        checks = {
            "expected_admission_status": verdict.status == expectation["expected_status"],
            "required_reasons_present": set(expectation["required_reasons"]).issubset(verdict.reasons),
            "expected_signature_validity": authentic is expectation["signature_valid"],
        }
        cases.append({"id": expectation["id"], "fixture_evidence_class": "SAMPLE",
                      "verification_evidence_class": "MEASURED", "status": verdict.status,
                      "reasons": list(verdict.reasons), "signature_valid": authentic,
                      "key_trust": "SAMPLE_LOCAL", "payload_sha256": sha256(base64.b64decode(envelope["payload"])),
                      "envelope_sha256": sha256(json_bytes(envelope)), "checks": checks})
    # Only hashes and verdicts leave this process; key material and signatures stay in RAM.
    del private_key, public_key, complete, tampered, incomplete, unsigned, envelopes
    return {"schema": SCHEMA, "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "evidence_class": "MEASURED", "scope": "local verifier conformance over SAMPLE fixtures",
            "source": {"repository": SOURCE_REPOSITORY, "commit": SOURCE_COMMIT,
                       "files": lock["files"], "byte_binding": "MEASURED"},
            "bundle_hashes": {name: sha256((bundle / name).read_bytes()) for name in
                              ("replay.py", "source-lock.json", "sample-input.json", "requirements.lock")},
            "runtime": runtime, "cases": cases,
            "conformance_checks": {"passed": sum(sum(item["checks"].values()) for item in cases), "total": 12},
            "conformant": all(all(item["checks"].values()) for item in cases),
            "key_generation": {"performed": True, "in_memory": True,
                               "persisted_private_key_material": False, "trust": "SAMPLE_LOCAL"},
            "effects_performed": [], "external_services_called": [],
            "production_authorization": "BLOCKED", "production_runtime_status": "UNKNOWN",
            "independent_replay": "NOT RUN", "hardware_measurement": "UNAVAILABLE", "energy_joules": "UNAVAILABLE"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True, help="Exact-byte canonical Git checkout at the locked commit")
    parser.add_argument("--output", type=Path, help="Optional local JSON report; contains no keys, signatures or local source paths")
    args = parser.parse_args()
    try:
        result = run(args.source_dir)
    except ReplayError as exc:
        result = {"schema": SCHEMA, "evidence_class": "BLOCKED", "conformant": False,
                  "reason": str(exc), "production_authorization": "BLOCKED", "independent_replay": "NOT RUN"}
    except (OSError, ValueError, KeyError, TypeError):
        result = {"schema": SCHEMA, "evidence_class": "BLOCKED", "conformant": False,
                  "reason": "local source, runtime or SAMPLE fixture configuration is unavailable or invalid",
                  "production_authorization": "BLOCKED", "independent_replay": "NOT RUN"}
    rendered = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
    if args.output:
        try:
            args.output.write_text(rendered, encoding="utf-8", newline="\n")
        except OSError:
            print(json.dumps({"schema": SCHEMA, "evidence_class": "BLOCKED", "conformant": False,
                              "reason": "report output could not be written"}))
            return 2
    print(rendered, end="")
    return 0 if result["conformant"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
