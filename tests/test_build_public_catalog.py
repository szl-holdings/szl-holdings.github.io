"""Catalog controls: complete public membership, safe links and no claim upgrade."""
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_public_catalog as builder


class PublicCatalogTests(unittest.TestCase):
    def setUp(self):
        self.raw = {name: (ROOT / 'estate' / name).read_bytes() for name in builder.INPUTS}
        self.inputs = [builder.read_json(self.raw[name]) for name in builder.INPUTS]
        self.hashes = {name: hashlib.sha256(value).hexdigest() for name, value in self.raw.items()}

    def build(self):
        return builder.build_catalog(*self.inputs, self.hashes)

    def test_current_public_membership_is_covered_once_without_model_inflation(self):
        catalog = self.build()
        keys = {(r['kind'], r['id']) for r in catalog['assets'] if r['kind'] != 'PyPI'}
        self.assertEqual(keys, builder.membership_keys(self.inputs[3]))
        self.assertEqual(catalog['counts']['HF Model'], 47)
        self.assertEqual(catalog['counts']['HF Kernel'], 14)
        self.assertEqual(catalog['counts']['PyPI'], 20)
        self.assertEqual(len(catalog['assets']), 282)
        self.assertTrue(all(r['private'] is False for r in catalog['assets']))
        self.assertEqual(catalog['source_snapshot_observed_at'], self.inputs[0]['observed_at'])
        self.assertNotEqual(catalog['observed_at'], catalog['source_snapshot_observed_at'])

    def test_new_public_identity_without_source_binding_stops_complete_build(self):
        self.inputs[3]['assets'].append({'kind':'HF Model','id':'SZLHOLDINGS/new-unbound-candidate','private':False})
        with self.assertRaisesRegex(ValueError, 'without an exact dated source'):
            self.build()

    def test_future_membership_source_and_kernel_observations_are_rejected(self):
        original = copy.deepcopy(self.inputs)
        for index in (0, 1, 3):
            with self.subTest(index=index):
                self.inputs = copy.deepcopy(original)
                self.inputs[index]['observed_at'] = '2999-01-01T00:00:00Z'
                with self.assertRaisesRegex(ValueError, 'future'): self.build()

    def test_entirely_yanked_release_retains_metadata_without_install_recipe(self):
        name = self.inputs[2]['packages'][0]['package_name']
        for artifact in self.inputs[2]['packages'][0]['artifacts']: artifact['yanked'] = True
        row = next(r for r in self.build()['assets'] if r['kind']=='PyPI' and r['id']==name)
        self.assertIsNone(row['installCommand'])
        self.assertIn('all artifacts yanked', row['state'])
        self.assertIn('installation NOT RUN', row['state'])

    def test_unknown_private_or_extra_membership_fields_fail_closed(self):
        original = copy.deepcopy(self.inputs[3])
        for private in (True, None, 0, 'false'):
            with self.subTest(private=private):
                self.inputs[3] = copy.deepcopy(original)
                self.inputs[3]['assets'][0]['private'] = private
                with self.assertRaises(ValueError): self.build()
        self.inputs[3] = original
        self.inputs[3]['assets'][0]['local_path'] = 'do-not-publish'
        with self.assertRaises(ValueError): self.build()

    def test_mutable_and_untrusted_source_links_fail_closed(self):
        self.inputs[0]['assets'][0]['sourceUrl'] = 'https://github.com/szl-holdings/a11oy/tree/main'
        with self.assertRaisesRegex(ValueError, 'source link'): self.build()

    def test_duplicate_namespace_identity_and_missing_hash_fail_closed(self):
        self.inputs[3]['assets'].append(dict(self.inputs[3]['assets'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate'): self.build()
        self.inputs[3]['assets'].pop()
        del self.hashes['pypi-packages.json']
        with self.assertRaisesRegex(ValueError, 'input byte hashes'): self.build()

    def test_pypi_is_pinned_without_claiming_execution_or_source_equivalence(self):
        packages = [r for r in self.build()['assets'] if r['kind']=='PyPI']
        for row in packages:
            self.assertEqual(row['sourcePackageBinding'], 'UNKNOWN')
            self.assertIn('installation NOT RUN', row['state'])
            self.assertRegex(row['installCommand'], r'^py -m pip install [a-z0-9-]+==[A-Za-z0-9.!+_-]+$')
            self.assertIn('/blob/' + row['revision'] + '/', row['sourceUrl'])
            self.assertRegex(row['url'], r'^https://pypi.org/project/[a-z0-9-]+/[^/]+/$')

    def test_untrusted_text_is_escaped_and_served_script_stays_byte_identical(self):
        catalog = self.build()
        row = copy.deepcopy(catalog['assets'][0])
        row['summary'] = '<img src=x onerror=alert(1)>'
        rendered = builder.card(row)
        self.assertNotIn('<img', rendered)
        self.assertIn('&lt;img', rendered)
        template = (ROOT / 'estate/index.html').read_text(encoding='utf-8')
        page = builder.render_page(template, catalog)
        self.assertEqual(re.findall(r'<script.*?</script>', template, re.S), re.findall(r'<script.*?</script>', page, re.S))
        self.assertEqual(re.findall(r'<meta http-equiv="Content-Security-Policy"[^>]+>', template), re.findall(r'<meta http-equiv="Content-Security-Policy"[^>]+>', page))
        self.assertEqual(page.count('data-estate-asset '), 282)

    def test_committed_catalog_is_reproducible_from_validated_input_bytes(self):
        catalog, page = builder.generate(ROOT)
        self.assertEqual(catalog, json.loads((ROOT / 'estate/public-catalog.json').read_bytes()))
        self.assertEqual(page, (ROOT / 'estate/index.html').read_text(encoding='utf-8'))

    def test_crlf_input_fails_before_a_normalized_git_blob_can_change_its_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'estate').mkdir()
            for name, value in self.raw.items():
                (root / 'estate' / name).write_bytes(value.replace(b'\r\n', b'\n'))
            name = 'catalog-membership.json'
            target = root / 'estate' / name
            target.write_bytes(target.read_bytes().replace(b'\n', b'\r\n'))
            with self.assertRaisesRegex(ValueError, 'LF line endings'):
                builder.generate(root)


if __name__ == '__main__': unittest.main()
