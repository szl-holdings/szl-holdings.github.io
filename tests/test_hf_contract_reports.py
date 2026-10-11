"""Public CSV reports must stay bound to the immutable public inventory."""
from pathlib import Path
import csv
import hashlib
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_REPORTS = {
    'model-contracts.csv': (
        'HF Model', '6ff4f0e9ac9dd27017d9a568f4a1ebcaa326d624f84a832c4ef9cb652d056523'),
    'dataset-readiness.csv': (
        'HF Dataset', '926d322383554819dacb59cf33177b8ea1ec5f4c2915b021ab425978e6dfccc4'),
}


class PublicContractReportTests(unittest.TestCase):
    def test_historical_public_reports_cover_visible_repositories_at_pinned_revisions(self):
        snapshot = json.loads((ROOT / 'estate/public-snapshot.json').read_text(encoding='utf-8'))
        for filename, (kind, digest) in HISTORICAL_REPORTS.items():
            expected = {a['id']: a for a in snapshot['assets'] if a['kind'] == kind}
            report = ROOT / 'estate' / filename
            canonical = report.read_bytes().replace(b'\r\n', b'\n')
            self.assertNotIn(b'\r', canonical)
            self.assertEqual(hashlib.sha256(canonical).hexdigest(), digest)
            with report.open(encoding='utf-8', newline='') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), len(expected))
            self.assertEqual({r['id'] for r in rows}, set(expected))
            historical_revisions = 0
            for row in rows:
                self.assertIs(expected[row['id']]['private'], False)
                self.assertEqual(row['visibility'], 'PUBLIC')
                self.assertRegex(row['revision'], r'\A[0-9a-f]{40}\Z')
                historical_revisions += row['revision'] != expected[row['id']]['revision']
                if kind == 'HF Model':
                    self.assertEqual(
                        row['card_url'],
                        f"https://huggingface.co/{row['id']}/blob/{row['revision']}/README.md")
                else:
                    self.assertEqual(
                        row['url'],
                        f"https://huggingface.co/datasets/{row['id']}/tree/{row['revision']}")
                for value in row.values():
                    self.assertNotIn('C:\\Users\\', value)
                    self.assertFalse(value.lstrip().startswith(('=', '+', '-', '@')), 'spreadsheet formula prefix')
                if kind == 'HF Model':
                    for field in ['runtime_test', 'weight_byte_hash', 'signature_verification', 'independent_evaluation']:
                        self.assertEqual(row[field], 'NOT_RUN')
                    self.assertEqual(row['evidence_class_this_review'], 'MEASURED')
                else:
                    self.assertEqual(row['row_or_split_validation'], 'NOT_RUN')
            expected_historical = 3 if kind == 'HF Model' else 4
            self.assertEqual(
                historical_revisions, expected_historical,
                'report scope changed; refresh or redate the CSV review')
            if kind == 'HF Model':
                advisory = next(row for row in rows if row['id'] == 'SZLHOLDINGS/oac-ops-health-v2')
                self.assertEqual(advisory['artifact_class'], 'custom_json_coefficients_plus_kernel_software')
                self.assertEqual(advisory['disposition'], 'SYNTHETIC_OPERATIONAL_ADVISORY')
                self.assertEqual(advisory['forge_binding'], 'NOT_IN_CURRENT_FORGE_ARTIFACT_BINDING')
                self.assertIn('REPORTED', advisory['published_evidence'])
                self.assertIn('unsigned', advisory['remaining_gate'])


if __name__ == '__main__':
    unittest.main()
