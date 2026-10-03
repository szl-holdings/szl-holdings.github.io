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


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bind_browser_policy.py"
SPEC = importlib.util.spec_from_file_location("browser_policy", SCRIPT)
assert SPEC and SPEC.loader
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


def page(body="", head=""):
    return '<!doctype html><html><head><meta charset="utf-8">\n' + head + '</head><body>' + body + '</body></html>'


class BrowserPolicy(unittest.TestCase):
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

    def test_external_local_script_gets_self_only(self):
        result = POLICY.bind(page('<script src="/app.js?v=hash" defer></script>'))
        self.assertIn("script-src 'self';", result)
        self.assertNotIn("sha256-", result)

    def test_root_json_ld_is_hashed_and_preserved(self):
        data = '<script type="application/ld+json">{"name":"SZL"}</script>'
        result = POLICY.bind(page(head=data))
        self.assertIn(data, result)
        self.assertIn(POLICY.script_hash('{"name":"SZL"}'), result)

    def test_policy_precedes_resources_after_charset(self):
        result = POLICY.bind(page(head='<link rel="stylesheet" href="site.css"><script src="app.js"></script>'))
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
