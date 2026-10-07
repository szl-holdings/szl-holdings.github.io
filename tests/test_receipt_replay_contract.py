#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Negative controls for source binding and actual four-case replay."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

BUNDLE = Path(__file__).resolve().parents[1] / 'estate/receipt-replay'
SOURCE = Path(os.environ.get("SZL_REPLAY_SOURCE_DIR", str(BUNDLE / 'receipt-source'))).resolve()
spec = importlib.util.spec_from_file_location("receipt_replay_harness", BUNDLE / "replay.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


@unittest.skipUnless(SOURCE.is_dir() or '--source-dir' in sys.argv, 'Source-bound contracts run in the required receipt-replay CI job')
class ReplayContracts(unittest.TestCase):
    def copied_source(self, root: Path) -> Path:
        destination = root / "source"
        shutil.copytree(SOURCE / "src", destination / "src")
        for name in ("pyproject.toml", "LICENSE"):
            shutil.copyfile(SOURCE / name, destination / name)
        git_dir = subprocess.run(["git", "-C", str(SOURCE), "rev-parse", "--absolute-git-dir"],
                                 check=True, capture_output=True, text=True).stdout.strip()
        # Read-only Git object access; these tests never run a Git mutation.
        (destination / ".git").write_text("gitdir: " + git_dir + "\n", encoding="utf-8")
        return destination

    def copied_bundle(self, root: Path) -> Path:
        destination = root / "bundle"
        destination.mkdir()
        for name in ("replay.py", "source-lock.json", "sample-input.json", "requirements.lock"):
            shutil.copyfile(BUNDLE / name, destination / name)
        return destination

    def test_complete_source_is_accepted(self):
        lock = replay.verify_source(SOURCE)
        self.assertEqual(lock["commit"], replay.SOURCE_COMMIT)
        self.assertEqual(len(lock["files"]), 12)

    def test_changed_source_is_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.copied_source(Path(tmp))
            module = source / "src/szl_receipt/governed_action.py"
            module.write_bytes(module.read_bytes() + b"\nraise RuntimeError('unbound source executed')\n")
            with self.assertRaisesRegex(replay.ReplayError, "file bytes differ"):
                replay.verify_source(source)

    def test_extra_python_module_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.copied_source(Path(tmp))
            (source / "src/cryptography.py").write_text("raise RuntimeError('shadow module executed')\n", encoding="utf-8")
            with self.assertRaisesRegex(replay.ReplayError, "extra Python modules"):
                replay.verify_source(source)

    def test_unbound_bytecode_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.copied_source(Path(tmp))
            (source / "src/szl_receipt/governed_action.pyc").write_bytes(b"unbound cache")
            with self.assertRaisesRegex(replay.ReplayError, "unbound executable bytes"):
                replay.verify_source(source)

    def test_missing_package_module_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.copied_source(Path(tmp))
            (source / "src/szl_receipt/pci.py").unlink()
            with self.assertRaisesRegex(replay.ReplayError, "missing or extra Python modules"):
                replay.verify_source(source)

    def test_modified_lock_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self.copied_bundle(Path(tmp))
            path = bundle / "source-lock.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["files"]["src/szl_receipt/governed_action.py"] = "0" * 64
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(replay.ReplayError, "source lock bytes differ"):
                replay.verify_source(SOURCE, bundle)

    def test_changed_dependency_lock_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self.copied_bundle(Path(tmp))
            path = bundle / "requirements.lock"
            path.write_bytes(path.read_bytes() + b"\n# changed lock\n")
            with self.assertRaisesRegex(replay.ReplayError, "dependency lock bytes differ"):
                replay.verify_source(SOURCE, bundle)

    def test_wrong_source_commit_is_rejected(self):
        with mock.patch.object(replay, "git", return_value=b"0" * 40 + b"\n"):
            with self.assertRaisesRegex(replay.ReplayError, "HEAD differs"):
                replay.verify_source(SOURCE)

    def test_wrong_runtime_dependency_version_is_rejected(self):
        # This unit isolates the version gate. The ambient-path rejection is
        # separately exercised through the real, non-isolated CLI below.
        with mock.patch.object(replay.sys, 'flags', mock.Mock(isolated=True)), mock.patch.object(replay.importlib.metadata, "version", return_value="0.0.0"):
            with self.assertRaisesRegex(replay.ReplayError, "dependency version differs"):
                replay.verify_runtime()

    def test_changed_project_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.copied_source(Path(tmp))
            project = source / "pyproject.toml"
            project.write_bytes(project.read_bytes() + b"\n# changed metadata\n")
            with self.assertRaisesRegex(replay.ReplayError, "file bytes differ: pyproject.toml"):
                replay.verify_source(source)

    def test_all_cases_use_real_crypto_and_preserve_incomplete(self):
        completed = subprocess.run([sys.executable, "-I", str(BUNDLE / "replay.py"), "--source-dir", str(SOURCE)],
                                   capture_output=True, text=True, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        report = json.loads(completed.stdout)
        self.assertTrue(report["conformant"])
        self.assertEqual(report["conformance_checks"], {"passed": 12, "total": 12})
        cases = {case["id"]: case for case in report["cases"]}
        self.assertEqual(cases["complete_signed"]["status"], "PASS")
        self.assertTrue(cases["complete_signed"]["signature_valid"])
        self.assertFalse(cases["tampered_payload"]["signature_valid"])
        self.assertEqual(cases["tampered_payload"]["reasons"], ["signature-mismatch"])
        self.assertTrue(cases["incomplete_signed"]["signature_valid"])
        self.assertEqual(cases["incomplete_signed"]["status"], "INCOMPLETE")
        self.assertIn("missing-subject:runtime_witness", cases["incomplete_signed"]["reasons"])
        self.assertFalse(cases["unsigned_honest"]["signature_valid"])
        self.assertEqual(cases["unsigned_honest"]["status"], "INCOMPLETE")
        self.assertEqual(report["production_authorization"], "BLOCKED")
        self.assertEqual(report["independent_replay"], "NOT RUN")
        self.assertEqual(report["effects_performed"], [])
        self.assertEqual(report["external_services_called"], [])
        self.assertEqual(report["key_generation"], {"performed": True, "in_memory": True,
                         "persisted_private_key_material": False, "trust": "SAMPLE_LOCAL"})
        self.assertNotIn("BEGIN PRIVATE KEY", completed.stdout)
        self.assertNotIn("BEGIN PUBLIC KEY", completed.stdout)
        self.assertNotIn(str(SOURCE), completed.stdout)
        self.assertFalse(list((SOURCE / "src").rglob("*.pyc")))

    def test_changed_fixture_stops_before_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self.copied_bundle(Path(tmp))
            path = bundle / "sample-input.json"
            path.write_bytes(path.read_bytes() + b"\n")
            completed = subprocess.run([sys.executable, "-I", str(bundle / "replay.py"), "--source-dir", str(SOURCE)],
                                       capture_output=True, text=True, timeout=60)
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(json.loads(completed.stdout)["reason"], "reviewed SAMPLE fixture bytes differ")

    def test_ambient_python_import_paths_are_rejected(self):
        completed = subprocess.run([sys.executable, str(BUNDLE / "replay.py"), "--source-dir", str(SOURCE)],
                                   capture_output=True, text=True, timeout=60)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("Python -I", json.loads(completed.stdout)["reason"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path)
    args, remaining = parser.parse_known_args()
    if args.source_dir:
        SOURCE = args.source_dir.resolve()
        if not SOURCE.is_dir():
            parser.error('Required source checkout is unavailable')
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
