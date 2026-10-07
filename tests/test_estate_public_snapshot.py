"""Public-only, source-bound estate snapshot and filter contract.

The raw audit stays outside this repository. These checks guard the committed
projection and page against accidental private rows, mutable source links, and
HTML/JSON drift.
"""

from __future__ import annotations

import json
import html
import re
import subprocess
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "estate" / "public-snapshot.json"
PAGE = ROOT / "estate" / "index.html"
EXPECTED_COUNTS = {
    "GitHub": 128,
    "HF Model": 47,
    "HF Dataset": 37,
    "HF Space": 36,
}
ASSET_FIELDS = {
    "id", "kind", "url", "revision", "archived", "category", "ci",
    "state", "sourceUrl", "ciUrl", "private",
}


class CardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.cards: list[dict[str, str]] = []
        self.current: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "article" and "data-estate-asset" in values:
            self.current = {
                "kind": values.get("data-kind") or "",
                "id": values.get("data-id") or "",
                "search": values.get("data-search") or "",
                "category": values.get("data-category") or "",
            }
        if tag == "a" and self.current is not None:
            classes = (values.get("class") or "").split()
            if "source-link" in classes:
                self.current["sourceUrl"] = values.get("href") or ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "article" and self.current is not None:
            self.cards.append(self.current)
            self.current = None


class PublicSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        cls.catalog = json.loads((ROOT / "estate/public-catalog.json").read_text(encoding="utf-8"))
        cls.html = PAGE.read_text(encoding="utf-8")

    def test_only_allowlisted_public_assets_and_counts(self) -> None:
        data = self.snapshot
        self.assertEqual(set(data), {
            "schema", "observed_at", "counts", "limitations", "assets",
        })
        self.assertEqual(data["schema"], "szl.public-estate-snapshot/v1")
        self.assertEqual(data["observed_at"], "2026-10-06T03:50:43.441667+00:00")
        self.assertEqual(data["counts"], EXPECTED_COUNTS)
        self.assertEqual(len(data["assets"]), 248)
        self.assertEqual(Counter(a["kind"] for a in data["assets"]), EXPECTED_COUNTS)
        self.assertEqual(
            len({(a["kind"], a["id"]) for a in data["assets"]}), 248
        )
        self.assertTrue(all(set(a) == ASSET_FIELDS for a in data["assets"]))
        self.assertTrue(all(a["private"] is False for a in data["assets"]))
        self.assertNotIn("C:\\Users\\", SNAPSHOT.read_text(encoding="utf-8"))

    def test_canonical_immutable_source_and_ci_urls(self) -> None:
        for asset in self.snapshot["assets"]:
            with self.subTest(kind=asset["kind"], asset=asset["id"]):
                revision = asset["revision"]
                self.assertRegex(revision, r"\A[0-9a-f]{40}\Z")
                self.assertIsInstance(asset["archived"], bool)
                if asset["kind"] == "GitHub":
                    self.assertRegex(asset["id"], r"\Aszl-holdings/[A-Za-z0-9_.-]+\Z")
                    base = "https://github.com/" + asset["id"]
                    self.assertEqual(asset["url"], base)
                    if asset["ciUrl"]:
                        self.assertRegex(
                            asset["ciUrl"],
                            re.escape(base) + r"/actions/runs/[1-9][0-9]*\Z",
                        )
                else:
                    self.assertIn(asset["kind"], {"HF Model", "HF Dataset", "HF Space"})
                    self.assertRegex(asset["id"], r"\ASZLHOLDINGS/[A-Za-z0-9_.-]+\Z")
                    prefix = {
                        "HF Model": "",
                        "HF Dataset": "datasets/",
                        "HF Space": "spaces/",
                    }[asset["kind"]]
                    base = "https://huggingface.co/" + prefix + asset["id"]
                    self.assertEqual(asset["url"], base)
                    self.assertEqual(asset["ciUrl"], "")
                self.assertEqual(asset["sourceUrl"], base + "/tree/" + revision)

    def test_page_cards_equal_public_catalog_and_keep_browser_policy(self) -> None:
        parser = CardParser()
        parser.feed(self.html)
        expected = [
            {
                "kind": a["kind"],
                "id": a["id"],
                "sourceUrl": a["sourceUrl"],
                "category": a["category"],
                "search": " ".join(
                    str(a[key]) for key in ("id", "kind", "category", "state", "summary")
                ).lower(),
            }
            for a in self.catalog["assets"]
        ]
        self.assertEqual(parser.cards, expected)
        self.assertIn('href="public-snapshot.json"', self.html)
        self.assertIn('href="/estate/"', (ROOT / "index.html").read_text(encoding="utf-8"))
        self.assertIn('id="estate-search"', self.html)
        self.assertIn('id="estate-kind"', self.html)
        self.assertIn('id="estate-count" role="status" aria-live="polite"', self.html)
        self.assertIn("connect-src 'none'", self.html)
        self.assertIn("script-src 'sha256-", self.html)
        self.assertNotIn("fetch(", self.html)
        self.assertNotIn("innerHTML", self.html)

    def test_artifact_category_selector_covers_public_snapshot(self) -> None:
        selector = re.search(r'<select id="estate-category">(.*?)</select>', self.html, re.S)
        self.assertIsNotNone(selector)
        values = [html.unescape(value) for value in re.findall(r'<option value="([^"]*)">', selector.group(1))]
        self.assertEqual(values, [""] + sorted({a["category"] for a in self.catalog["assets"]}, key=str.casefold))
        parser = CardParser()
        parser.feed(self.html)
        self.assertEqual([c["category"] for c in parser.cards], [a["category"] for a in self.catalog["assets"]])

    def test_committed_kernel_registry_is_public_and_does_not_inflate_inventory(self) -> None:
        kernels = json.loads((ROOT / 'estate/kernel-distributions.json').read_text(encoding='utf-8'))
        self.assertEqual(set(kernels), {'schema', 'observed_at', 'limitations', 'distributions'})
        self.assertEqual(kernels['schema'], 'szl.public-kernel-distributions/v1')
        self.assertEqual(kernels['observed_at'], '2026-10-06T03:55:21.332428+00:00')
        self.assertEqual(len(kernels['distributions']), 14)
        mirrors = {a['id']: a for a in self.snapshot['assets'] if a['kind'] == 'HF Model'}
        links = []
        for row in kernels['distributions']:
            self.assertEqual(set(row), {'id', 'revision', 'private', 'url', 'sourceUrl',
                                       'modelMirrorRevision', 'modelMirrorSourceUrl', 'parity'})
            self.assertIs(row['private'], False)
            self.assertEqual(row['parity'], 'UNKNOWN')
            self.assertRegex(row['id'], r'\ASZLHOLDINGS/[A-Za-z0-9_.-]+\Z')
            self.assertRegex(row['revision'], r'\A[0-9a-f]{40}\Z')
            self.assertEqual(row['url'], 'https://huggingface.co/kernels/' + row['id'])
            self.assertEqual(row['sourceUrl'], row['url'] + '/tree/' + row['revision'])
            self.assertEqual(row['modelMirrorRevision'], mirrors[row['id']]['revision'])
            self.assertEqual(row['modelMirrorSourceUrl'], mirrors[row['id']]['sourceUrl'])
            links.append(row['sourceUrl'])
        self.assertEqual(len(set(links)), 14)
        self.assertEqual(re.findall(r'<a class="source-link kernel-source" href="([^"]+)"', self.html), links)
        region = self.html.split('<!-- estate-kernels:start -->')[1].split('<!-- estate-kernels:end -->')[0]
        self.assertNotIn('data-estate-asset', region)
        self.assertNotIn('<script', region)

    def test_committed_exhibits_remain_source_only_and_preserve_failed_states(self) -> None:
        manifest = json.loads((ROOT / 'estate/exhibits.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['evidence_class'], 'DECLARED')
        self.assertEqual(len(manifest['exhibits']), 3)
        by_id = {(a['kind'], a['id']): a for a in self.snapshot['assets']}
        region = self.html.split('<!-- estate-exhibits:start -->')[1].split('<!-- estate-exhibits:end -->')[0]
        self.assertEqual(region.count('class="asset research-exhibit"'), 3)
        for exhibit in manifest['exhibits']:
            for ref in exhibit['source_ids']:
                asset = by_id[(ref['kind'], ref['id'])]
                self.assertIs(asset['private'], False)
                self.assertIn(html.escape(asset['sourceUrl'], quote=True), region)
                self.assertIn(html.escape(asset['state'], quote=True), region)
        self.assertNotIn('data-estate-asset', region)

    def test_filter_behavior_without_a_network_or_browser_dependency(self) -> None:
        match = re.search(r'<script id="estate-filter">(.*?)</script>', self.html, re.S)
        self.assertIsNotNone(match)
        probe = r"""
const assert = require('node:assert/strict');
const vm = require('node:vm');
const script = JSON.parse(require('node:fs').readFileSync(0, 'utf8')).script;
const search = {value: '', handlers: {}, addEventListener(k, f) {this.handlers[k] = f;}};
const kind = {value: '', handlers: {}, addEventListener(k, f) {this.handlers[k] = f;}};
const category = {value: '', handlers: {}, addEventListener(k, f) {this.handlers[k] = f;}};
const count = {textContent: ''};
const cards = [
  {dataset: {kind: 'GitHub', category: 'Python', search: 'immune security failure'}, hidden: false},
  {dataset: {kind: 'HF Model', category: 'Tensor / GGUF artifact', search: 'forge receipt agent'}, hidden: false},
  {dataset: {kind: 'HF Dataset', category: 'Dataset repository', search: 'training corpus'}, hidden: false},
  {dataset: {kind: 'HF Model', category: 'Kernel / software', search: 'kernel source'}, hidden: false},
];
const elements = {'estate-search': search, 'estate-kind': kind, 'estate-category': category, 'estate-count': count};
const document = {
  getElementById(id) {return elements[id];},
  querySelectorAll(selector) {
    assert.equal(selector, '[data-estate-asset]');
    return cards;
  },
};
vm.runInNewContext(script, {document});
assert.deepEqual(cards.map(c => c.hidden), [false, false, false, false]);
assert.match(count.textContent, /^4 matching/);
search.value = 'immUNE'; search.handlers.input();
assert.deepEqual(cards.map(c => c.hidden), [false, true, true, true]);
kind.value = 'HF Model'; kind.handlers.change();
assert.deepEqual(cards.map(c => c.hidden), [true, true, true, true]);
search.value = ''; search.handlers.input();
assert.deepEqual(cards.map(c => c.hidden), [true, false, true, false]);
assert.match(count.textContent, /^2 matching/);
category.value = 'Kernel / software'; category.handlers.change();
assert.deepEqual(cards.map(c => c.hidden), [true, true, true, false]);
assert.match(count.textContent, /^1 matching/);
search.value = 'receipt'; search.handlers.input();
assert.deepEqual(cards.map(c => c.hidden), [true, true, true, true]);
assert.match(count.textContent, /^0 matching/);
category.value = ''; category.handlers.change();
assert.deepEqual(cards.map(c => c.hidden), [true, false, true, true]);
"""
        result = subprocess.run(
            ["node", "-e", probe],
            input=json.dumps({"script": match.group(1)}),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
