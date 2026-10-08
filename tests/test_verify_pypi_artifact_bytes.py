"""Negative controls for the public PyPI opaque-byte readback."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import verify_pypi_artifact_bytes as gate  # noqa: E402


class FakeResponse:
    def __init__(self, payload: bytes, url: str, *, status: int = 200):
        self.payload, self.url, self.status = payload, url, status
        self.headers = {"Content-Length": str(len(payload))}
        self.offset = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, size: int) -> bytes:
        block = self.payload[self.offset:self.offset + size]
        self.offset += len(block)
        return block


class PyPIByteReadbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = gate.pinned_manifest()
        cls.report = gate.parse_json(gate.REPORT.read_bytes(), "artifact byte readback")

    def test_committed_report_is_complete_and_offline(self):
        with patch.object(gate, "open_exact", side_effect=AssertionError("offline check made a request")):
            gate.validate_report(self.report, self.manifest)
        self.assertEqual((self.report["package_count"], self.report["artifact_count"],
                          self.report["matched_count"], self.report["measured_total_bytes"]),
                         (20, 40, 40, 1632195))

    def test_pinned_manifest_byte_edit_fails_before_any_provider_read(self):
        altered = gate.git_blob("estate/pypi-packages.json").replace(
            b'"published_public_distributions": 20', b'"published_public_distributions": 19', 1)
        with patch.object(gate, "git_blob", return_value=altered), patch.object(gate, "open_exact", side_effect=AssertionError("network called")):
            with self.assertRaisesRegex(ValueError, "pinned source bytes"):
                gate.pinned_manifest()

    def test_report_tamper_and_promotion_claims_fail(self):
        cases = [("matched_count", 39), ("measured_total_bytes", 1),
                 ("source_manifest_sha256", "0" * 64), ("source_package_binding", "MEASURED"),
                 ("attestation_signature_verification", "VERIFIED"), ("installation", "PASS"),
                 ("observed_at", "2026-10-06T00:00:00+00:00")]
        for key, value in cases:
            with self.subTest(key=key):
                bad = copy.deepcopy(self.report)
                bad[key] = value
                with self.assertRaises(ValueError):
                    gate.validate_report(bad, self.manifest)
        for change in (lambda r: r["artifacts"].pop(),
                       lambda r: r["artifacts"][0].update(measured_sha256="0" * 64),
                       lambda r: r["artifacts"][0].update(status="MATCH", measured_bytes=1)):
            bad = copy.deepcopy(self.report)
            change(bad)
            with self.assertRaises(ValueError):
                gate.validate_report(bad, self.manifest)

    def test_stream_hashes_bytes_and_rejects_wrong_target_or_size(self):
        payload = b"opaque archive bytes"
        row = {"package_name": "example", "version": "1.0", "filename": "example.whl",
               "url": "https://files.pythonhosted.org/packages/aa/example.whl",
               "declared_sha256": hashlib.sha256(payload).hexdigest(), "declared_bytes": len(payload)}
        with patch.object(gate, "open_exact", return_value=FakeResponse(payload, row["url"])):
            result = gate.stream_one(row)
        self.assertEqual((result["status"], result["measured_sha256"], result["measured_bytes"]),
                         ("MATCH", row["declared_sha256"], len(payload)))
        with patch.object(gate, "open_exact", return_value=FakeResponse(payload, row["url"])):
            self.assertEqual(gate.stream_one({**row, "declared_sha256": "0" * 64})["status"], "MISMATCH")
        with patch.object(gate, "open_exact", return_value=FakeResponse(payload, "https://example.com/wrong")):
            with self.assertRaisesRegex(ValueError, "target"):
                gate.stream_one(row)
        with patch.object(gate, "open_exact", return_value=FakeResponse(payload + b"x", row["url"])):
            with self.assertRaisesRegex(ValueError, "length"):
                gate.stream_one(row)

    def test_provider_unavailable_is_not_reported_as_match(self):
        one = gate.expected_rows(self.manifest)[0]
        with patch.object(gate, "expected_rows", return_value=[one]), patch.object(gate, "stream_one", side_effect=URLError("offline")):
            report = gate.collect(self.manifest)
        self.assertEqual((report["evidence_class"], report["matched_count"], report["artifacts"][0]["status"]),
                         ("UNAVAILABLE", 0, "UNAVAILABLE"))


if __name__ == "__main__":
    unittest.main()
