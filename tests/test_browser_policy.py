"""Offline regressions for deterministic company-site browser policy."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bind_browser_policy.py"
SPEC = importlib.util.spec_from_file_location("browser_policy", SCRIPT)
assert SPEC and SPEC.loader
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


def page(body="", head=""):
    return '<!doctype html><html><head><meta charset="utf-8">\n' + head + '</head><body>' + body + '</body></html>'


class BrowserPolicy(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.asset = self.root / "app.js"
        self.asset.write_bytes(b"window.approved = true;\n")

    def bind(self, text, document="index.html"):
        return POLICY.bind(text, root=self.root, page=Path(document))

    def cli(self, *arguments):
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--root", str(self.root), *arguments],
            capture_output=True, text=True,
        )

    def test_static_page_denies_script_and_network(self):
        result = POLICY.bind(page("<main>Static pointer</main>"))
        for directive in ("default-src 'none'", "script-src 'none'", "connect-src 'none'", "form-action 'none'", "object-src 'none'", "worker-src 'none'"):
            self.assertIn(directive, result)
        self.assertIn('<meta name="referrer" content="no-referrer">', result)

    def test_inline_script_uses_exact_hash_without_trimming(self):
        script = "\n  const value = 'λ';\n"
        expected = "'sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode() + "'"
        result = POLICY.bind(page(f"<script>{script}</script>"))
        self.assertIn("script-src " + expected, result)
        self.assertNotIn("script-src 'self'", result)
        self.assertNotIn("unsafe-eval", result)

    def test_external_local_script_gets_exact_sri_and_hash_only_policy(self):
        expected = "sha256-" + base64.b64encode(hashlib.sha256(self.asset.read_bytes()).digest()).decode()
        result = self.bind(page('<script src="/app.js?v=hash" defer></script>'))
        self.assertIn("script-src '" + expected + "';", result)
        self.assertIn('<script src="/app.js?v=hash" defer integrity="' + expected + '"></script>', result)
        self.assertNotIn("script-src 'self'", result)
        self.assertNotIn("crossorigin", result)

    def test_external_scripts_require_explicit_root_and_page_context(self):
        text = page('<script src="app.js"></script>')
        for context in ({}, {"root": self.root}, {"page": self.root / "index.html"}):
            with self.subTest(context=context), self.assertRaisesRegex(ValueError, "explicit root and page"):
                POLICY.bind(text, **context)

    def test_script_source_mapping_is_relative_to_document_or_site_root(self):
        nested = self.root / "nested"
        nested.mkdir()
        (nested / "local.js").write_bytes(b"window.nested = true;\n")
        for source, target in (
            ("local.js?v=1&kind=local", nested / "local.js"),
            ("../app.js?v=2", self.asset),
            ("/app.js?version=3", self.asset),
            ("/nested/local.js", nested / "local.js"),
        ):
            with self.subTest(source=source):
                result = self.bind(page(f'<script src="{source}"></script>'), "nested/index.html")
                self.assertIn(f'src="{source}"', result)
                self.assertIn('integrity="' + POLICY.script_integrity(target) + '"', result)

    def test_only_integrity_attribute_is_changed_and_script_bodies_are_preserved(self):
        inline = "\nconst evidence = {text: 'keep < & > λ', value: 3};\n"
        raw = '<SCRIPT data-note="integrity=not-an-attribute >"\n SRC=app.js INTEGRITY = \'old\' defer></SCRIPT>'
        result = self.bind(page(raw + '<script type="application/ld+json">' + inline + '</script>'))
        expected_tag = raw.replace("INTEGRITY = 'old'", 'integrity="' + POLICY.script_integrity(self.asset) + '"')
        self.assertIn(expected_tag, result)
        self.assertIn('<script type="application/ld+json">' + inline + '</script>', result)
        self.assertIn(POLICY.script_hash(inline), result)
        self.assertEqual(self.bind(result), result)

    def test_multiple_external_script_spans_are_updated_without_reordering(self):
        text = page('<script src="app.js" defer></script>\n<!-- keep -->\n<script async src="app.js?v=2" integrity=old></script>')
        result = self.bind(text)
        integrity = POLICY.script_integrity(self.asset)
        self.assertIn(f'<script src="app.js" defer integrity="{integrity}"></script>\n<!-- keep -->\n<script async src="app.js?v=2" integrity="{integrity}"></script>', result)
        self.assertEqual(result.count("'" + integrity + "'"), 1)
        self.assertEqual(self.bind(result), result)

    def test_crlf_script_checkout_hashes_match_lf_source_but_lone_cr_fails(self):
        markup = page('<script src="app.js"></script>')
        self.asset.write_bytes(b"first();\nsecond();\n")
        lf = self.bind(markup)
        self.asset.write_bytes(b"first();\r\nsecond();\r\n")
        self.assertEqual(self.bind(markup), lf)
        self.assertEqual(POLICY.canonical_script_bytes(self.asset), b"first();\nsecond();\n")
        self.asset.write_bytes(b"first();\rsecond();\n")
        with self.assertRaisesRegex(ValueError, "lone CR"):
            self.bind(markup)

    def test_external_script_must_be_utf8(self):
        self.asset.write_bytes(b"\xff")
        with self.assertRaises(UnicodeError):
            self.bind(page('<script src="app.js"></script>'))

    def test_missing_nonregular_and_escaping_script_files_fail_closed(self):
        (self.root / "directory").mkdir()
        for source in ("missing.js", "directory", "../app.js", "../../app.js", "/../app.js"):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "regular file|escapes"):
                self.bind(page(f'<script src="{source}"></script>'))
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.bind(page('<script src="app.js"></script>'), self.root.parent / "outside.html")

    def test_ambiguous_encoded_or_malformed_script_urls_fail_closed(self):
        for source in (
            "/%2e%2e/app.js", "%2E./app.js", "/nested/%2e%2e/app.js",
            "/%2fapp.js", "/nested%5capp.js", "/%252e%252e/app.js", "app.js%00",
            "app.js:stream", "app.js#fragment", "app.js#", "?v=1", "app%Q0.js",
            "app%.js", " app.js", "app.js ", "app\t.js", "///app.js",
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.bind(page(f'<script src="{source}"></script>'))

    def test_symlink_component_is_rejected_even_when_target_would_remain_in_root(self):
        linked = self.root / "linked.js"
        linked.write_bytes(self.asset.read_bytes())
        original_is_link = POLICY.is_link
        with mock.patch.object(POLICY, "is_link", side_effect=lambda path: path == linked or original_is_link(path)):
            with self.assertRaisesRegex(ValueError, "symlinks"):
                self.bind(page('<script src="linked.js"></script>'))

    def test_windows_reparse_points_are_rejected_without_new_pathlib_helpers(self):
        path = mock.Mock()
        path.is_symlink.return_value = False
        path.is_junction.return_value = False
        path.lstat.return_value.st_file_attributes = POLICY.stat.FILE_ATTRIBUTE_REPARSE_POINT
        self.assertTrue(POLICY.is_link(path))
        path.lstat.return_value.st_file_attributes = 0
        self.assertFalse(POLICY.is_link(path))

    def test_real_file_and_directory_symlinks_are_rejected(self):
        linked = self.root / "linked.js"
        directory = self.root / "linked-directory"
        try:
            linked.symlink_to(self.asset)
            directory.symlink_to(self.root, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"Host does not permit symlink creation: {exc}")
        for source in ("linked.js", "linked-directory/app.js"):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "symlinks"):
                self.bind(page(f'<script src="{source}"></script>'))

    def test_duplicate_integrity_and_self_closing_scripts_are_rejected(self):
        for raw in (
            '<script src="app.js" integrity="one" INTEGRITY="two"></script>',
            '<script src="app.js" />',
        ):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.bind(page(raw))

    def test_cli_requires_explicit_write_to_rebind_missing_wrong_or_stale_sri(self):
        document = self.root / "index.html"
        original = page('<script src="app.js"></script>')
        document.write_text(original, encoding="utf-8", newline="\n")
        before = document.read_bytes()
        self.assertEqual(self.cli("--check").returncode, 1)
        self.assertEqual(document.read_bytes(), before)
        self.assertEqual(self.cli("--write").returncode, 0)
        bound = document.read_bytes()
        self.assertEqual(self.cli("--check").returncode, 0)
        integrity = POLICY.script_integrity(self.asset).encode()
        for altered in (
            bound.replace(b' integrity="' + integrity + b'"', b""),
            bound.replace(b'integrity="' + integrity + b'"', b'integrity="sha256-wrong"'),
        ):
            document.write_bytes(altered)
            with self.subTest(altered=altered[-100:]):
                self.assertEqual(self.cli("--check").returncode, 1)
                self.assertEqual(document.read_bytes(), altered)
                self.assertEqual(self.cli("--write").returncode, 0)
                self.assertEqual(document.read_bytes(), bound)
        self.asset.write_bytes(b"window.approved = 'changed';\n")
        self.assertEqual(self.cli("--check").returncode, 1)
        self.assertEqual(document.read_bytes(), bound)
        self.assertEqual(self.cli("--write").returncode, 0)
        self.assertNotEqual(document.read_bytes(), bound)
        self.assertEqual(self.cli("--check").returncode, 0)

    def test_cli_write_validates_every_document_before_writing_any(self):
        good = self.root / "a.html"
        bad = self.root / "z.html"
        good.write_text(page('<script src="app.js"></script>'), encoding="utf-8")
        bad.write_text(page('<script src="https://example.invalid/a.js"></script>'), encoding="utf-8")
        before = {path: path.read_bytes() for path in (good, bad, self.asset)}
        self.assertEqual(self.cli("--write").returncode, 1)
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_root_json_ld_is_hashed_and_preserved(self):
        data = '<script type="application/ld+json">{"name":"SZL"}</script>'
        result = POLICY.bind(page(head=data))
        self.assertIn(data, result)
        self.assertIn(POLICY.script_hash('{"name":"SZL"}'), result)

    def test_policy_precedes_resources_after_charset(self):
        result = self.bind(page(head='<link rel="stylesheet" href="site.css"><script src="app.js"></script>'))
        self.assertLess(result.index('charset="utf-8"'), result.index(POLICY.START))
        self.assertLess(result.index(POLICY.END), result.index('<link'))
        self.assertLess(result.index(POLICY.END), result.index('<script'))

    def test_binder_is_byte_idempotent(self):
        result = POLICY.bind(page("<script>let x=1;</script>"))
        self.assertEqual(POLICY.bind(result), result)

    def test_crlf_and_cr_match_browser_normalization(self):
        text = page("<script>\nlet x=1;\n</script>")
        self.assertEqual(POLICY.bind(text), POLICY.bind(text.replace("\n", "\r\n")))
        self.assertEqual(POLICY.bind(text), POLICY.bind(text.replace("\n", "\r")))

    def test_script_change_changes_binding(self):
        original = POLICY.bind(page("<script>let x=1;</script>"))
        changed = original.replace("let x=1;", "let x=2;")
        self.assertNotEqual(changed, POLICY.bind(changed))
        self.assertNotIn(POLICY.script_hash("let x=1;"), POLICY.bind(changed))

    def test_hashes_are_deduplicated(self):
        result = POLICY.bind(page("<script>x()</script><script>x()</script>"))
        self.assertEqual(result.count(POLICY.script_hash("x()")), 1)

    def test_remote_scripts_are_not_silently_allowlisted(self):
        for source in ("https://example.invalid/script.js", "//example.invalid/script.js", "data:text/javascript,x()", "", "\\\\example.invalid\\script.js"):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "script src"):
                POLICY.bind(page(f'<script src="{source}"></script>'))

    def test_inline_event_and_javascript_urls_fail(self):
        for markup in ('<button onclick="x()">Click</button>', '<a href="javascript:x()">Link</a>'):
            with self.subTest(markup=markup), self.assertRaises(ValueError):
                POLICY.bind(page(markup))

    def test_unmanaged_meta_is_preserved_by_refusal(self):
        for meta in ('<meta http-equiv="Content-Security-Policy" content="script-src *">', '<meta name="referrer" content="origin">'):
            with self.subTest(meta=meta), self.assertRaisesRegex(ValueError, "unmanaged"):
                POLICY.bind(page(head=meta))

    def test_duplicate_and_malformed_markers_fail(self):
        valid = POLICY.bind(page())
        for text in (valid + POLICY.START, valid + POLICY.START + POLICY.END, page(POLICY.END + POLICY.START)):
            with self.subTest(text=text), self.assertRaises(ValueError):
                POLICY.bind(text)

    def test_duplicate_policy_attributes_fail(self):
        with self.assertRaisesRegex(ValueError, "duplicate attributes"):
            POLICY.bind(page('<script src="a.js" src="b.js"></script>'))

    def test_markers_in_script_or_json_data_are_not_removed(self):
        for script_type in ("text/javascript", "application/ld+json"):
            data = POLICY.START + "keep portfolio evidence" + POLICY.END
            markup = f'<script type="{script_type}">"{data}"</script>'
            with self.subTest(script_type=script_type), self.assertRaisesRegex(ValueError, "metadata-only"):
                POLICY.bind(page(markup))

    def test_managed_markers_must_be_actual_head_comments_after_charset(self):
        bound = POLICY.bind(page())
        block = POLICY.MANAGED.search(bound).group()
        for text in (
            page(block),
            page(head="<title>Before policy</title>" + block),
            page(head="<script>const text = `" + block + "`;</script>"),
            page(head="<!-- outer " + block + " -->"),
        ):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "metadata-only"):
                POLICY.bind(text)

    def test_managed_block_cannot_silently_erase_extra_content(self):
        bound = POLICY.bind(page())
        for content in ("keep portfolio evidence", "<script>important()</script>", "<meta name=description content=important>"):
            changed = bound.replace(POLICY.END, content + POLICY.END)
            with self.subTest(content=content), self.assertRaisesRegex(ValueError, "metadata-only"):
                POLICY.bind(changed)

    def test_resources_before_charset_and_base_fail(self):
        with self.assertRaisesRegex(ValueError, "precede resources"):
            POLICY.bind('<html><head><script src="a.js"></script><meta charset="utf-8"></head><body></body></html>')
        with self.assertRaisesRegex(ValueError, "base elements"):
            POLICY.bind(page(head='<base href="/">'))

    def test_meta_does_not_claim_unsupported_header_controls(self):
        result = POLICY.bind(page())
        for token in ("frame-ancestors", "report-uri", "report-only", "sandbox", "unsafe-eval"):
            self.assertNotIn(token, result)
        self.assertIn("style-src 'self' 'unsafe-inline'", result)
        self.assertIn("script-src-attr 'none'", result)

    def test_cli_check_fails_without_writing_and_covers_nested_html(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "nested" / "index.html"
            nested.parent.mkdir()
            nested.write_text(page("<script>let x=1;</script>"), encoding="utf-8")
            before = nested.read_bytes()
            command = [sys.executable, "-B", str(SCRIPT), "--root", str(root)]
            check = subprocess.run(command + ["--check"], capture_output=True, text=True)
            self.assertEqual(check.returncode, 1)
            self.assertEqual(nested.read_bytes(), before)
            self.assertEqual(subprocess.run(command + ["--write"], capture_output=True).returncode, 0)
            bound = nested.read_bytes()
            self.assertEqual(subprocess.run(command + ["--write"], capture_output=True).returncode, 0)
            self.assertEqual(nested.read_bytes(), bound)
            self.assertEqual(subprocess.run(command + ["--check"], capture_output=True).returncode, 0)
            nested.write_bytes(bound.replace(b"let x=1;", b"let x=2;"))
            self.assertEqual(subprocess.run(command + ["--check"], capture_output=True).returncode, 1)


if __name__ == "__main__":
    unittest.main()
