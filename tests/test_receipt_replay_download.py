"""Publication must reject missing rejection evidence and private extra fields."""
from pathlib import Path
import io
import json
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_receipt_replay_bundle as builder


class ReplayDownloadControls(unittest.TestCase):
    def mutated_report(self, change):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / builder.RELATIVE, root / builder.RELATIVE)
            path = root / builder.RELATIVE / 'measured-run.json'
            report = json.loads(path.read_text(encoding='utf-8'))
            change(report)
            path.write_text(json.dumps(report) + '\n', encoding='utf-8', newline='\n')
            with self.assertRaises(ValueError):
                builder.generate(root)

    def test_empty_or_nonboolean_checks_cannot_publish(self):
        self.mutated_report(lambda r: r['cases'][0].update(checks={}))
        self.mutated_report(lambda r: r['cases'][0]['checks'].update(expected_admission_status=1))

    def test_omitted_negative_reasons_cannot_publish(self):
        for index in (1, 2, 3):
            with self.subTest(case=index):
                self.mutated_report(lambda r: r['cases'][index].update(reasons=[]))

    def test_secret_or_signature_extension_cannot_publish(self):
        self.mutated_report(lambda r: r.update(private_key='unrecognized secret field'))
        self.mutated_report(lambda r: r['cases'][0].update(signature='unrecognized field'))
        self.mutated_report(lambda r: r['runtime'].update(local_path='private path'))

    def test_effect_or_key_persistence_promotion_cannot_publish(self):
        self.mutated_report(lambda r: r.update(effects_performed=['provider-write']))
        self.mutated_report(lambda r: r['key_generation'].update(persisted_private_key_material=True))
        self.mutated_report(lambda r: r['cases'][0].update(fixture_evidence_class='MEASURED'))

    def test_report_cannot_bind_different_runner_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / builder.RELATIVE, root / builder.RELATIVE)
            path = root / builder.RELATIVE / 'replay.py'
            path.write_bytes(path.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'current bundle bytes'):
                builder.generate(root)

    def test_download_is_deterministic_and_contains_only_reviewed_members(self):
        manifest, raw = builder.generate()
        self.assertEqual((ROOT / builder.RELATIVE / 'bundle-manifest.json').read_bytes(), manifest)
        self.assertEqual((ROOT / builder.RELATIVE / 'receipt-replay.zip').read_bytes(), raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as zipped:
            self.assertEqual(set(zipped.namelist()), set(builder.FILES) | {'bundle-manifest.json'})
            for name in builder.FILES:
                self.assertEqual(zipped.read(name), (ROOT / builder.RELATIVE / name).read_bytes())


if __name__ == '__main__': unittest.main()
