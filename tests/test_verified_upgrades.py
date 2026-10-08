"""Keep public upgrade cards bound to named evidence without leaking internal rows."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verified_upgrades", ROOT / "scripts/build_verified_upgrades.py")
assert SPEC is not None and SPEC.loader is not None
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class VerifiedUpgradesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = builder._read_json((ROOT / "estate/verified-upgrades.json").read_bytes())
        cls.page = (ROOT / "estate/index.html").read_bytes().decode("utf-8")

    def test_public_projection_and_generated_page_match_exactly(self) -> None:
        entries = builder.validate(self.document)
        self.assertEqual(len(entries), len({item["id"] for item in entries}))
        self.assertTrue(all(item["private"] is False for item in entries))
        self.assertEqual(builder.generate(self.page, self.document), self.page)
        region = self.page.split(builder.START, 1)[1].split(builder.END, 1)[0]
        self.assertIn("Production authorization: BLOCKED", region)
        self.assertIn("REPO_DECLARED", region)
        self.assertIn("Snapshot origin: DECLARED", region)
        self.assertNotIn("C:\\Users", region)
        self.assertNotIn("fetch(", region)
        self.assertNotIn("innerHTML", region)
        self.assertNotIn('data-estate-asset data-kind=', region)

    def test_private_or_missing_privacy_flag_is_rejected(self) -> None:
        for value in (True, None):
            with self.subTest(value=value):
                bad = copy.deepcopy(self.document)
                if value is None:
                    del bad["entries"][0]["private"]
                else:
                    bad["entries"][0]["private"] = value
                with self.assertRaises(ValueError):
                    builder.validate(bad)

    def test_receipt_denominators_and_source_run_cannot_be_inflated(self) -> None:
        for field, value in (("test_count", 536), ("sample_case_count", 13), ("mismatch_count", 1),
                             ("source_revision", "0" * 40), ("ci_run_id", 1)):
            with self.subTest(field=field):
                bad = copy.deepcopy(self.document)
                bad["entries"][0][field] = value
                with self.assertRaises(ValueError):
                    builder.validate(bad)

    def test_status_and_extra_fields_are_closed(self) -> None:
        for field, value in (("evidence_class", "REPORTED"), ("key_trust", "APPROVED"),
                             ("production_authorization", "AUTHORIZED"), ("private_path", "C:/private")):
            with self.subTest(field=field):
                bad = copy.deepcopy(self.document)
                bad["entries"][0][field] = value
                with self.assertRaises(ValueError):
                    builder.validate(bad)

    def test_duplicate_json_and_generated_region_tampering_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            builder._read_json(b'{"schema":"a","schema":"b"}')
        self.assertNotEqual(builder.generate(self.page.replace("535 tests", "536 tests"), self.document),
                            self.page.replace("535 tests", "536 tests"))

    def test_forge_profile_requires_exact_byte_and_blocked_promotion(self) -> None:
        base = copy.deepcopy(self.document)
        self.assertEqual(base["entries"][1]["source_revision"], builder.FORGE_SOURCE_REVISION)
        builder.validate(base)
        for field, value in (("source_revision", "0" * 40), ("adapter_sha256", "0" * 64), ("hub_revision", "0" * 40),
                             ("adapter_bytes", 0), ("signed_receipts_verified", 4),
                             ("snapshot_origin", "VERIFIED"),
                             ("publication_eligible", True), ("held_out_evaluation_replay", "PASS")):
            with self.subTest(field=field):
                bad = copy.deepcopy(base)
                bad["entries"][1][field] = value
                with self.assertRaises(ValueError):
                    builder.validate(bad)


if __name__ == "__main__":
    unittest.main()
