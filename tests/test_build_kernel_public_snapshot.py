"""SIMULATED invariants for the separate public Kernel Hub surface census."""
from __future__ import annotations

import copy
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_kernel_public_snapshot", ROOT / "scripts" / "build_kernel_public_snapshot.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
SHA = "a" * 40
MODEL_SHA = "b" * 40
STAMP = "2020-01-01T12:45:00Z"
FIELDS = {"id", "revision", "private", "url", "sourceUrl", "modelMirrorRevision",
          "modelMirrorSourceUrl", "parity"}


def kernel(name="example", **extra):
    return {"id": "SZLHOLDINGS/" + name, "sha": SHA, "private": False, **extra}


def mirror(name="example", **extra):
    return {"id": "SZLHOLDINGS/" + name, "kind": "HF Model", "revision": MODEL_SHA,
            "private": False, **extra}


class KernelProjectionTests(unittest.TestCase):
    def project(self, rows=None, mirrors=None):
        return builder.build_snapshot(rows if rows is not None else [kernel()],
                                      mirrors if mirrors is not None else [mirror()], STAMP)

    def test_literal_public_only_closed_projection_and_independent_surface_count(self):
        rows = [kernel(local_path="C:/private", owner="private principal", files=["private.bin"])]
        for index, private in enumerate((True, None, "false", 0)):
            rows.append(kernel("excluded" + str(index), private=private))
        rows.append({"id": "SZLHOLDINGS/missing-privacy", "sha": SHA})
        snapshot = self.project(rows)
        self.assertEqual(set(snapshot), {"schema", "observed_at", "limitations", "distributions"})
        self.assertEqual(snapshot["schema"], "szl.public-kernel-distributions/v1")
        self.assertEqual(snapshot["observed_at"], STAMP)
        self.assertEqual(len(snapshot["distributions"]), 1)
        self.assertEqual(set(snapshot["distributions"][0]), FIELDS)
        self.assertIs(snapshot["distributions"][0]["private"], False)
        self.assertNotIn("excluded", json.dumps(snapshot))
        self.assertNotIn("private principal", json.dumps(snapshot))
        self.assertNotIn("C:/", json.dumps(snapshot))
        self.assertNotIn("models", snapshot)

    def test_kernel_and_model_urls_are_constructed_at_their_distinct_revisions(self):
        row = self.project()["distributions"][0]
        self.assertEqual(row["url"], "https://huggingface.co/kernels/SZLHOLDINGS/example")
        self.assertEqual(row["sourceUrl"], row["url"] + "/tree/" + SHA)
        self.assertEqual(row["modelMirrorRevision"], MODEL_SHA)
        self.assertEqual(row["modelMirrorSourceUrl"],
                         "https://huggingface.co/SZLHOLDINGS/example/tree/" + MODEL_SHA)
        self.assertEqual(row["parity"], "UNKNOWN")
        self.assertEqual(self.project(mirrors=[mirror(revision=SHA)])["distributions"][0]["parity"],
                         "UNKNOWN", "Matching revision metadata must not certify byte parity")

    def test_absent_nonpublic_and_wrong_repository_type_mirrors_do_not_leak(self):
        for mirrors in ([], [mirror(private=True)], [mirror(private=None)],
                        [mirror(private="false")], [mirror(private=0)],
                        [mirror(kind="HF Dataset")]):
            with self.subTest(mirrors=mirrors):
                row = self.project(mirrors=mirrors)["distributions"][0]
                self.assertIsNone(row["modelMirrorRevision"])
                self.assertIsNone(row["modelMirrorSourceUrl"])
                self.assertEqual(row["parity"], "UNKNOWN")

    def test_invalid_public_identifiers_revisions_and_duplicate_rows_are_refused(self):
        for update in ({"id": "other/example"}, {"id": "SZLHOLDINGS/.."},
                       {"id": 'SZLHOLDINGS/x" onclick="alert(1)'}, {"sha": None},
                       {"sha": "main"}, {"sha": "A" * 40}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.project([kernel(**update)])
        with self.assertRaises(ValueError):
            self.project([kernel(), kernel()])
        with self.assertRaises(ValueError):
            self.project(mirrors=[mirror(revision="main")])
        with self.assertRaises(ValueError):
            self.project(mirrors=[mirror(), mirror()])
        for stamp in ("", "2020-01-01", "2020-01-01T12:45:00", "2020-01-01T12:45:00+02:00"):
            with self.assertRaises(ValueError):
                builder.build_snapshot([kernel()], [mirror()], stamp)

    def test_raw_metadata_cannot_supply_links_parity_or_claims(self):
        row = kernel(url="javascript:alert(1)", sourceUrl="https://untrusted.example",
                     parity="MEASURED", description='<script>alert("x")</script>')
        snapshot = self.project([row])
        rendered = builder.render_distributions(snapshot)
        self.assertNotIn("javascript:", rendered)
        self.assertNotIn("untrusted.example", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("data-estate-asset", rendered)
        self.assertIn("1 public Kernel Hub distribution", rendered)
        self.assertIn("UNKNOWN", rendered)
        self.assertIn("separate", rendered)
        self.assertIn(STAMP, rendered)

    def test_renderer_refuses_corrupt_projection_and_unattested_parity_upgrade(self):
        snapshot = self.project()
        for changes in ({"sourceUrl": "https://untrusted.example"}, {"private": True},
                        {"modelMirrorSourceUrl": "https://untrusted.example"},
                        {"modelMirrorRevision": SHA}, {"parity": "MEASURED"},
                        {"raw_errors": "private"}):
            broken = copy.deepcopy(snapshot)
            broken["distributions"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                builder.render_distributions(broken)

    def test_unique_marker_region_is_required_and_outside_template_is_preserved(self):
        start, end = '<!-- estate-kernels:start -->', '<!-- estate-kernels:end -->'
        before = '<div data-estate-asset data-id="existing">Existing public asset</div>'
        after = '<script id="reviewed">const x = 1;</script>'
        template = before + start + "old" + end + after
        rendered = builder.render_page(template, self.project())
        self.assertTrue(rendered.startswith(before + start))
        self.assertTrue(rendered.endswith(end + after))
        self.assertEqual(rendered.count("data-estate-asset"), 1)
        self.assertEqual(rendered.count("<script"), 1)
        self.assertEqual(rendered, builder.render_page(rendered, self.project()))
        for broken in (template.replace(start, ""), template.replace(end, ""), template + start):
            with self.assertRaises(ValueError):
                builder.render_page(broken, self.project())


class BoundKernelNamespaceTests(unittest.TestCase):
    """SIMULATED enumeration receipts guard bytes, pagination and mirror mapping."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.audit = Path(self.temporary.name) / "audit"
        self.site = Path(self.temporary.name) / "site"
        self.audit.mkdir()
        (self.site / "estate").mkdir(parents=True)
        self.raw = self.audit / "kernels.json"
        self.mirrors = self.audit / "mirrors.json"
        self.receipt_path = self.audit / "receipt.json"
        self.template = '<!-- estate-kernels:start -->old<!-- estate-kernels:end --><script>const x=1;</script>'
        (self.site / "estate" / "index.html").write_text(self.template, encoding="utf-8")
        self.raw.write_text(json.dumps([kernel()]), encoding="utf-8")
        self.mirrors.write_text(json.dumps([
            {"id": "SZLHOLDINGS/example", "type": "model", "sha": MODEL_SHA, "private": False},
            {"id": "SZLHOLDINGS/private-source", "type": "model", "sha": SHA, "private": True},
        ]), encoding="utf-8")
        self.receipt = {
            "schema": "szl.hf-public-kernel-enumeration-receipt/v1", "observed_at": STAMP,
            "evidence_class": "MEASURED", "authentication": "ANONYMOUS",
            "request_url": "https://huggingface.co/api/kernels?author=SZLHOLDINGS&limit=100&full=true",
            "http_status": 200, "rows": 1, "pagination_complete": True,
            "terminal_link_header": None, "next": None,
            "raw_inventory_path": str(self.raw), "raw_inventory_sha256": "",
            "raw_inventory_bytes": 0,
            "model_mirror_inventory_path": str(self.mirrors), "model_mirror_inventory_sha256": "",
            "same_id_revision_mapping": [{
                "id": "SZLHOLDINGS/example", "kernel_revision": SHA, "private": False,
                "model_mirror_revision": MODEL_SHA, "model_mirror_private": False, "parity": "UNKNOWN",
            }],
        }
        self.rebind()

    def rebind(self):
        raw = self.raw.read_bytes()
        self.receipt.update(raw_inventory_sha256=hashlib.sha256(raw).hexdigest(), raw_inventory_bytes=len(raw),
                            model_mirror_inventory_sha256=hashlib.sha256(self.mirrors.read_bytes()).hexdigest())
        self.receipt_path.write_text(json.dumps(self.receipt), encoding="utf-8")
        self.receipt_sha256 = hashlib.sha256(self.receipt_path.read_bytes()).hexdigest()

    def load(self, **extra):
        return builder.load_bound_namespace(self.audit, receipt_path=self.receipt_path,
                                            receipt_sha256=self.receipt_sha256, **extra)

    def cli(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return builder.main(["--audit-dir", str(self.audit), "--namespace-receipt", str(self.receipt_path),
                                 "--receipt-sha256", self.receipt_sha256, "--site-dir", str(self.site)])

    def assert_refused_without_output(self):
        self.assertEqual(self.cli(), 1)
        self.assertFalse((self.site / "estate" / "kernel-distributions.json").exists())
        self.assertEqual((self.site / "estate" / "index.html").read_text(encoding="utf-8"), self.template)

    def test_cli_publishes_only_closed_projection_and_separate_kernel_surface_region(self):
        self.assertEqual(self.cli(), 0)
        snapshot = json.loads((self.site / "estate" / "kernel-distributions.json").read_bytes())
        self.assertEqual(snapshot, self.load())
        self.assertEqual(len(snapshot["distributions"]), 1)
        self.assertNotIn("private-source", json.dumps(snapshot))
        self.assertNotIn("raw_inventory_path", json.dumps(snapshot))
        self.assertNotIn(str(self.audit), json.dumps(snapshot))
        page = (self.site / "estate" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(page.count("<script>"), 1)
        self.assertNotIn("data-estate-asset", page)

    def test_missing_and_mismatched_receipt_or_source_bytes_are_refused(self):
        self.receipt_sha256 = "f" * 64
        self.assert_refused_without_output()
        self.rebind()
        self.raw.write_bytes(self.raw.read_bytes() + b" ")
        self.assert_refused_without_output()
        self.rebind()
        self.mirrors.write_bytes(self.mirrors.read_bytes() + b" ")
        self.assert_refused_without_output()
        self.rebind()
        self.receipt_path.unlink()
        self.assert_refused_without_output()

    def test_incomplete_wrong_scope_and_ambiguous_terminal_pagination_are_refused(self):
        for key, value in (("pagination_complete", False), ("http_status", 403),
                           ("http_status", "200"), ("rows", True), ("rows", 2),
                           ("terminal_link_header", '<next page>'), ("next", "more"),
                           ("request_url", "https://untrusted.example/kernels"),
                           ("evidence_class", "DECLARED"), ("authentication", "TOKEN")):
            original = self.receipt[key]
            self.receipt[key] = value
            self.rebind()
            with self.subTest(key=key, value=value):
                self.assert_refused_without_output()
            self.receipt[key] = original
        self.rebind()
        del self.receipt["terminal_link_header"]
        self.rebind()
        self.assert_refused_without_output()

    def test_future_timestamp_mapping_revision_and_parity_conflicts_are_refused(self):
        self.receipt["observed_at"] = "2099-01-01T12:45:00Z"
        self.rebind()
        self.assert_refused_without_output()
        self.receipt["observed_at"] = STAMP
        mapping = self.receipt["same_id_revision_mapping"][0]
        for key, value in (("id", "SZLHOLDINGS/missing"), ("kernel_revision", MODEL_SHA),
                           ("model_mirror_revision", SHA), ("model_mirror_private", True),
                           ("private", None), ("parity", "MEASURED")):
            original = mapping[key]
            mapping[key] = value
            self.rebind()
            with self.subTest(key=key):
                self.assert_refused_without_output()
            mapping[key] = original

    def test_bound_paths_must_stay_inside_audit_root_and_bytes_are_read_once(self):
        outside = Path(self.temporary.name) / "outside.json"
        outside.write_bytes(self.raw.read_bytes())
        original_path = self.receipt["raw_inventory_path"]
        self.receipt["raw_inventory_path"] = str(outside)
        self.rebind()
        self.assert_refused_without_output()
        self.receipt["raw_inventory_path"] = original_path
        self.rebind()
        reads = []
        original_read = Path.read_bytes
        def once(path):
            reads.append(path.resolve())
            self.assertEqual(reads.count(path.resolve()), 1, "Verified input was reread")
            return original_read(path)
        with patch.object(Path, "read_bytes", once):
            snapshot = self.load(now=datetime(2020, 1, 2, tzinfo=timezone.utc))
        self.assertEqual(len(reads), 3)
        self.assertEqual(len(snapshot["distributions"]), 1)

    def test_corrupt_json_and_missing_markers_are_refused_before_either_write(self):
        self.raw.write_text('[{"id":"one","id":"two"}]', encoding="utf-8")
        self.rebind()
        self.assert_refused_without_output()
        self.raw.write_text(json.dumps([kernel()]), encoding="utf-8")
        self.rebind()
        self.template = self.template.replace('<!-- estate-kernels:end -->', '')
        (self.site / "estate" / "index.html").write_text(self.template, encoding="utf-8")
        self.assert_refused_without_output()


if __name__ == "__main__":
    unittest.main()
