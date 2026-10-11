"""Check source binding and fail-closed limits of the public byte readback."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import verify_kernel_shared_bytes as verifier  # noqa: E402


class KernelSharedByteReadbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = verifier.pinned_manifest()
        cls.report = json.loads(verifier.REPORT.read_text(encoding="utf-8"))

    def test_committed_report_is_bound_to_all_fourteen_pinned_pairs(self) -> None:
        verifier.check_committed_report(verifier.REPORT.read_bytes(), self.manifest)
        self.assertEqual(self.report["pair_count"], 14)
        self.assertEqual(self.report["measured_pair_count"], 13)
        self.assertEqual(self.report["unavailable_pair_count"], 1)
        self.assertEqual(self.report["measured_shared_count"], 125)
        self.assertEqual(self.report["unavailable_shared_count"], 33)
        self.assertEqual(self.report["matched_count"], 61)
        self.assertEqual(self.report["differing_count"], 64)
        self.assertEqual(self.report["whole_artifact_equivalence"], "UNKNOWN")
        self.assertEqual(self.report["runtime_behavior"], "NOT RUN")

    def test_committed_report_byte_tampering_is_rejected(self) -> None:
        raw = verifier.REPORT.read_bytes()
        modified = raw.replace(b'"matched_count": 61', b'"matched_count": 60', 1)
        self.assertNotEqual(modified, raw)
        with self.assertRaisesRegex(ValueError, "reviewed byte readback"):
            verifier.check_committed_report(modified, self.manifest)

    def test_gated_mirror_cannot_be_relabelled_as_measured(self) -> None:
        gated = next(item for item in self.report["pairs"] if item["id"].endswith("/szl-lambda-gate"))
        self.assertEqual(gated["model_access_gated"], "manual")
        self.assertEqual(gated["access_status"], "UNAVAILABLE")
        self.assertTrue(all(item["kernel_measured"] is None and item["mirror_measured"] is None
                            for item in gated["shared_files"]))
        bad = copy.deepcopy(self.report)
        pair = next(item for item in bad["pairs"] if item["id"].endswith("/szl-lambda-gate"))
        pair["access_status"] = "MEASURED"
        with self.assertRaises(ValueError):
            verifier.validate_report(bad, self.manifest)

    def test_inflated_counts_authority_and_source_are_rejected(self) -> None:
        for field, value in (("matched_count", 62), ("measured_pair_count", 14),
                             ("whole_artifact_equivalence", "MEASURED"),
                             ("runtime_behavior", "PASS"), ("source_revision", "0" * 40)):
            with self.subTest(field=field):
                bad = copy.deepcopy(self.report)
                bad[field] = value
                with self.assertRaises(ValueError):
                    verifier.validate_report(bad, self.manifest)

    def test_download_must_match_pinned_tree_size_and_git_blob(self) -> None:
        raw = b"pinned bytes\n"
        oid = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        row = self.manifest["distributions"][0]
        with patch.object(verifier, "get", return_value=raw):
            self.assertEqual(verifier.measure_one("kernel", row, "README.md",
                                                  {"bytes": len(raw), "git_blob_oid": oid})["sha256"],
                             hashlib.sha256(raw).hexdigest())
            for info in ({"bytes": len(raw) + 1, "git_blob_oid": oid},
                         {"bytes": len(raw), "git_blob_oid": "0" * 40}):
                with self.subTest(info=info), self.assertRaises(ValueError):
                    verifier.measure_one("kernel", row, "README.md", info)

    def test_redirect_cannot_leave_hub_host(self) -> None:
        request = Request("https://huggingface.co/api/models/SZLHOLDINGS/szl-kernels")
        with self.assertRaises(ValueError):
            verifier.SameHostRedirect().redirect_request(
                request, None, 302, "Found", {}, "https://example.com/unbound")

    def test_same_host_redirect_cannot_rebind_another_repository(self) -> None:
        class RedirectedResponse:
            status = 200
            headers = {}

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def geturl(self):
                return "https://huggingface.co/api/models/SZLHOLDINGS/other-repo"

            def read(self, *_):
                return b"{}"

        class FakeOpener:
            def open(self, *_args, **_kwargs):
                return RedirectedResponse()

        url = "https://huggingface.co/api/models/SZLHOLDINGS/szl-kernels"
        with patch.object(verifier, "build_opener", return_value=FakeOpener()):
            with self.assertRaisesRegex(ValueError, "pinned repository binding"):
                verifier.get(url, limit=100, expected_paths=("/api/models/SZLHOLDINGS/szl-kernels",))

    def test_tree_requires_terminal_pagination_and_unique_paths(self) -> None:
        row = self.manifest["distributions"][0]
        revision = row["revision"]
        next_url = (f"https://huggingface.co/api/kernels/{row['id']}/tree/{revision}"
                    "?expand=true&recursive=true&limit=50&cursor=next")

        def page(path):
            return json.dumps([{"type": "file", "path": path, "size": 1,
                                "oid": "a" * 40, "lfs": None}]).encode()

        with patch.object(verifier, "get", side_effect=[(page("a.txt"), next_url),
                                                         (page("b.txt"), None)]):
            files, _, page_count = verifier.tree("kernel", row, revision)
        self.assertEqual((set(files), page_count), ({"a.txt", "b.txt"}, 2))

        for bad_next in (next_url.replace(row["id"], "SZLHOLDINGS/other"), next_url):
            with self.subTest(bad_next=bad_next):
                second_next = next_url if bad_next == next_url else None
                with patch.object(verifier, "get", side_effect=[(page("a.txt"), bad_next),
                                                                 (page("b.txt"), second_next)]):
                    if bad_next != next_url:
                        with self.assertRaisesRegex(ValueError, "escaped pinned source"):
                            verifier.tree("kernel", row, revision)
                    else:
                        with self.assertRaisesRegex(ValueError, "repeated"):
                            verifier.tree("kernel", row, revision)
        with patch.object(verifier, "get", side_effect=[(page("a.txt"), next_url),
                                                         (page("a.txt"), None)]):
            with self.assertRaisesRegex(ValueError, "duplicate"):
                verifier.tree("kernel", row, revision)

    def test_manual_gate_remains_unavailable_without_download(self) -> None:
        row = next(item for item in self.manifest["distributions"] if item["id"].endswith("/szl-lambda-gate"))
        listing = {"shared.txt": {"bytes": 2, "git_blob_oid": "a" * 40, "lfs": False}}
        with (patch.object(verifier, "model_access", return_value=({"sha": row["modelMirrorRevision"],
                                                                     "gated": "manual"}, "b" * 64)),
              patch.object(verifier, "tree", side_effect=[(listing, "c" * 64, 1),
                                                          (listing, "d" * 64, 1)]),
              patch.object(verifier, "measure_one", side_effect=AssertionError("must not download"))):
            pair = verifier.collect_pair(row)
        self.assertEqual(pair["access_status"], "UNAVAILABLE")
        self.assertEqual((pair["shared_count"], pair["unavailable_count"], pair["measured_bytes"]), (1, 1, 0))
        self.assertIsNone(pair["shared_files"][0]["bytes_match"])


if __name__ == "__main__":
    unittest.main()
