"""Public CSV reports must stay bound to the immutable public inventory."""
from pathlib import Path
import csv
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PublicContractReportTests(unittest.TestCase):
    def test_public_reports_match_exact_visible_repositories(self):
        snapshot = json.loads((ROOT / 'estate/public-snapshot.json').read_text(encoding='utf-8'))
        for filename, kind in [('model-contracts.csv', 'HF Model'), ('dataset-readiness.csv', 'HF Dataset')]:
            expected = {a['id']: a for a in snapshot['assets'] if a['kind'] == kind}
            with (ROOT / 'estate' / filename).open(encoding='utf-8', newline='') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), len(expected))
            self.assertEqual({r['id'] for r in rows}, set(expected))
            for row in rows:
                self.assertIs(expected[row['id']]['private'], False)
                self.assertEqual(row['visibility'], 'PUBLIC')
                self.assertEqual(row['revision'], expected[row['id']]['revision'])
                for value in row.values():
                    self.assertNotIn('C:\\Users\\', value)
                    self.assertFalse(value.lstrip().startswith(('=', '+', '-', '@')), 'spreadsheet formula prefix')
                if kind == 'HF Model':
                    for field in ['runtime_test', 'weight_byte_hash', 'signature_verification', 'independent_evaluation']:
                        self.assertEqual(row[field], 'NOT_RUN')
                    self.assertEqual(row['evidence_class_this_review'], 'MEASURED')
                else:
                    self.assertEqual(row['row_or_split_validation'], 'NOT_RUN')


if __name__ == '__main__':
    unittest.main()
