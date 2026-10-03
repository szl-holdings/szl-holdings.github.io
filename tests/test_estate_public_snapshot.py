"""Public-only, source-bound estate snapshot and filter contract.

The raw audit stays outside this repository. These checks guard the committed
projection and page against accidental private rows, mutable source links, and
HTML/JSON drift.
"""

from __future__ import annotations

import json
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
    "GitHub": 127,
    "HF Model": 47,
    "HF Dataset": 36,
    "HF Space": 34,
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
        cls.html = PAGE.read_text(encoding="utf-8")

    def test_only_allowlisted_public_assets_and_counts(self) -> None:
        data = self.snapshot
        self.assertEqual(set(data), {
            "schema", "observed_at", "counts", "limitations", "assets",
        })
        self.assertEqual(data["schema"], "szl.public-estate-snapshot/v1")
        self.assertEqual(data["observed_at"], "2026-10-03T05:19:29Z")
        self.assertEqual(data["counts"], EXPECTED_COUNTS)
        self.assertEqual(len(data["assets"]), 244)
        self.assertEqual(Counter(a["kind"] for a in data["assets"]), EXPECTED_COUNTS)
        self.assertEqual(
            len({(a["kind"], a["id"]) for a in data["assets"]}), 244
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

    def test_page_cards_equal_snapshot_and_keep_browser_policy(self) -> None:
        parser = CardParser()
        parser.feed(self.html)
        expected = [
            {
                "kind": a["kind"],
                "id": a["id"],
                "sourceUrl": a["sourceUrl"],
                "search": " ".join(
                    str(a[key]) for key in ("id", "kind", "category", "state", "ci")
                ).lower(),
            }
            for a in self.snapshot["assets"]
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

    def test_filter_behavior_without_a_network_or_browser_dependency(self) -> None:
        match = re.search(r'<script id="estate-filter">(.*?)</script>', self.html, re.S)
        self.assertIsNotNone(match)
        probe = r"""
const assert = require('node:assert/strict');
const vm = require('node:vm');
const script = JSON.parse(require('node:fs').readFileSync(0, 'utf8')).script;
const search = {value: '', handlers: {}, addEventListener(k, f) {this.handlers[k] = f;}};
const kind = {value: '', handlers: {}, addEventListener(k, f) {this.handlers[k] = f;}};
const count = {textContent: ''};
const cards = [
  {dataset: {kind: 'GitHub', search: 'immune security failure'}, hidden: false},
  {dataset: {kind: 'HF Model', search: 'forge receipt agent'}, hidden: false},
  {dataset: {kind: 'HF Dataset', search: 'training corpus'}, hidden: false},
];
const elements = {'estate-search': search, 'estate-kind': kind, 'estate-count': count};
const document = {
  getElementById(id) {return elements[id];},
  querySelectorAll(selector) {
    assert.equal(selector, '[data-estate-asset]');
    return cards;
  },
};
vm.runInNewContext(script, {document});
assert.deepEqual(cards.map(c => c.hidden), [false, false, false]);
assert.match(count.textContent, /^3 matching/);
search.value = 'immUNE'; search.handlers.input();
assert.deepEqual(cards.map(c => c.hidden), [false, true, true]);
kind.value = 'HF Model'; kind.handlers.change();
assert.deepEqual(cards.map(c => c.hidden), [true, true, true]);
search.value = ''; search.handlers.input();
assert.deepEqual(cards.map(c => c.hidden), [true, false, true]);
assert.match(count.textContent, /^1 matching/);
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
