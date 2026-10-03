"""Executable regressions for the complete static-site route guard."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location(
    "verify_site_links", Path(__file__).resolve().parents[1] / "scripts" / "verify_site_links.py"
)
assert SPEC and SPEC.loader
LINKS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LINKS)


class SiteLinks(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.put("index.html", '<main id="main">Company</main>')

    def put(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def check(self, expected=None):
        count, errors = LINKS.verify(self.root)
        if expected is None:
            self.assertEqual(errors, [])
        else:
            self.assertTrue(any(expected in error for error in errors), errors)
        return count

    def test_all_nested_pages_are_scanned(self):
        for route in ("products", "brain", "khipu", "console", "verify", "api/a11oy/v1/honest"):
            self.put(f"{route}/index.html", '<img src="missing.png">')
        count, errors = LINKS.verify(self.root)
        self.assertEqual(count, 7)
        self.assertEqual(len(errors), 6)

    def test_relative_and_root_assets(self):
        self.put("assets/logo.svg", "<svg/>")
        self.put("products/index.html", '<img src="../assets/logo.svg"><img src="/assets/logo.svg?v=1">')
        self.assertEqual(self.check(), 2)

    def test_directory_needs_an_index(self):
        (self.root / "empty").mkdir()
        self.put("index.html", '<a href="/empty/">Broken</a>')
        self.check("directory index not found")

    def test_cross_page_and_decoded_fragments(self):
        self.put("products/index.html", '<h1 id="product name">Products</h1>')
        self.put("index.html", '<a href="/products/?v=1#product%20name">Products</a>')
        self.check()

    def test_missing_cross_page_fragment(self):
        self.put("products/index.html", '<h1 id="real">Products</h1>')
        self.put("index.html", '<a href="products/#missing">Products</a>')
        self.check("fragment has no target")

    def test_absolute_same_origin_fragment_is_checked(self):
        self.put("index.html", '<a href="https://holdings.a-11-oy.com/#missing">Broken</a>')
        self.check("fragment has no target")

    def test_protocol_relative_same_origin_is_checked(self):
        self.put("index.html", '<img src="//holdings.a-11-oy.com/missing.png">')
        self.check("not found")

    def test_equivalent_encoded_and_idna_hosts_are_local(self):
        for hostname in ("holdings%2ea-11-oy.com", "holdings\u3002a-11-oy.com", "HOLDINGS.A-11-OY.COM."):
            with self.subTest(hostname=hostname):
                self.put("index.html", f'<a href="https://{hostname}/missing.html">Broken</a>')
                self.check("not found")

    def test_hostname_suffix_is_not_the_company_origin(self):
        self.put("index.html", '<a href="https://holdings.a-11-oy.com.example.invalid/missing">External</a>')
        self.check()

    def test_filename_with_trailing_slash_fails(self):
        self.put("products/index.html", "<main>Products</main>")
        self.put("index.html", '<a href="/products/index.html/">Broken</a>')
        self.check("trailing-slash URL")

    def test_external_and_browser_schemes_do_not_trigger_http(self):
        self.put("index.html", '<a href="//example.invalid/not-local">External</a><a href="https://a-11-oy.com/console">Product</a><a href="mailto:test@example.invalid">Mail</a><img src="data:image/png;base64,AA==">')
        self.check()

    def test_docs_exception_is_exact_and_same_origin(self):
        self.put("index.html", '<a href="/docs-site/">Docs</a><a href="https://holdings.a-11-oy.com/docs-site/">Docs</a>')
        self.check()
        self.put("index.html", '<a href="/docs-site/missing.html">Broken</a>')
        self.check("not found")

    def test_query_only_and_named_anchor(self):
        self.put("index.html", '<a name="old"></a><a href="?version=1#old">Old</a><a href="#">Top</a>')
        self.check()

    def test_text_fragment_preserves_id_requirement(self):
        self.put("index.html", '<main id="main">Hello</main><a href="#:~:text=Hello">Text</a><a href="#main:~:text=Hello">Main</a>')
        self.check()
        self.put("index.html", '<a href="#missing:~:text=Hello">Broken</a>')
        self.check("fragment has no target")

    def test_duplicate_ids_and_attributes_fail(self):
        self.put("index.html", '<p id="same"></p><p id="same"></p><a href="#same" href="#missing">Link</a>')
        self.check("duplicate HTML id")
        self.check("duplicate href attribute")

    def test_missing_social_image(self):
        self.put("products/index.html", '<meta property="og:image" content="/missing.png">')
        self.check("not found")

    def test_decoded_asset_path(self):
        self.put("assets/company logo.svg", "<svg/>")
        self.put("index.html", '<img src="/assets/company%20logo.svg">')
        self.check()

    def test_root_escape_fails(self):
        self.put("index.html", '<a href="/%2e%2e/outside.txt">Escape</a>')
        self.check("escapes the site root")

    def test_base_tag_fails_instead_of_checking_wrong_origin(self):
        self.put("index.html", '<base href="https://example.invalid/">')
        self.check("<base> is unsupported")

    def test_malformed_local_url_fails(self):
        self.put("index.html", '<a href="https://holdings.a-11-oy.com:bad/">Bad</a>')
        self.check("Port could not be cast")

    def test_generated_dependency_html_is_not_published_source(self):
        self.put("node_modules/example/index.html", '<a href="missing">Ignored</a>')
        self.assertEqual(self.check(), 1)

    def test_invalid_sitemap_fails(self):
        self.put("sitemap.xml", "<urlset>")
        self.check("invalid XML")


if __name__ == "__main__":
    unittest.main()
