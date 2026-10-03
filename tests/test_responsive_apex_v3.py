#!/usr/bin/env python3
"""Offline responsive contract for the SZL Holdings static company front door."""
from __future__ import annotations

import json
import importlib.util
import re
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "assets" / "szl-responsive-apex-v3.css"
JS = ROOT / "assets" / "szl-responsive-apex-v3.js"
STATE = ROOT / "responsive-experience-v3.json"
STYLE_MARKER = 'data-szl-responsive-apex-v3="style"'
SCRIPT_MARKER = 'data-szl-responsive-apex-v3="script"'
SPEC = importlib.util.spec_from_file_location("responsive_binder", ROOT / "tools/bind_responsive_apex_v3.py")
assert SPEC and SPEC.loader
BINDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BINDER)


class ResponsiveApexV3Contract(unittest.TestCase):
    def setUp(self) -> None:
        self.css = CSS.read_text(encoding="utf-8")
        self.js = JS.read_text(encoding="utf-8")
        self.state = json.loads(STATE.read_text(encoding="utf-8"))

    def test_registered_viewports_cover_all_required_formats(self) -> None:
        viewports = {tuple(row) for row in self.state["viewports"]}
        required = {
            (320, 568), (375, 812), (430, 932), (812, 375), (768, 1024),
            (1440, 900), (1920, 1080), (2560, 1440), (3440, 1440),
        }
        self.assertTrue(required.issubset(viewports))

    def test_compact_landscape_and_theatre_composition(self) -> None:
        for token in (
            "@media (max-width: 47.999rem)",
            "orientation: landscape",
            "@media (min-width: 100rem)",
            "@media (min-width: 150rem)",
            "grid-template-columns: repeat(12",
            "container-type: inline-size",
            "@container (max-width: 28rem)",
        ):
            self.assertIn(token, self.css)

    def test_touch_keyboard_overflow_and_safe_areas(self) -> None:
        for token in (
            "--apex-touch: 44px",
            "--apex-touch-coarse: 48px",
            ":focus-visible",
            "overflow-x: clip",
            "safe-area-inset-top",
            "safe-area-inset-bottom",
            "font-size: max(16px, 1em)",
        ):
            self.assertIn(token, self.css)

    def test_dynamic_controller_is_local_bounded_and_nontracking(self) -> None:
        for token in (
            "matchMedia",
            "visualViewport",
            "requestAnimationFrame",
            "visibilitychange",
            "--apex-progress",
            "data.szlViewport".replace("data.", "dataset."),
        ):
            self.assertIn(token, self.js)
        combined = (self.css + self.js).lower()
        self.assertIsNone(re.search(r"https?://", combined))
        for prohibited in ("fetch(", "xmlhttprequest", "localstorage", "sessionstorage", "document.cookie", "sendbeacon"):
            self.assertNotIn(prohibited, combined)

    def test_accessibility_and_print_fallbacks(self) -> None:
        for token in (
            "prefers-reduced-motion",
            "prefers-contrast: more",
            "forced-colors: active",
            "@media print",
        ):
            self.assertIn(token, self.css)

    def test_origin_roles_are_honest(self) -> None:
        self.assertEqual(self.state["origin"], "https://holdings.a-11-oy.com")
        self.assertEqual(self.state["role"], "static-company-front-door")
        self.assertEqual(self.state["product_origin"], "https://a-11-oy.com")
        self.assertEqual(self.state["runtime_origin"], "https://a-11-oy.com")
        self.assertNotEqual(self.state["origin"], self.state["runtime_origin"])
        self.assertTrue(self.state["requirements"]["static_origin_never_claims_runtime_api"])

    def test_bound_state_covers_all_html_and_preserves_static_pages(self) -> None:
        self.assertIn(self.state["state"], {"ASSETS_READY", "BOUND"})
        if self.state["state"] != "BOUND":
            return
        interactive = set(self.state["interactive_documents"])
        docs = {
            path.relative_to(ROOT).as_posix()
            for path in ROOT.rglob("*.html")
            if ".github" not in path.parts and "node_modules" not in path.parts
        }
        recorded = {row["path"] for row in self.state["documents"]}
        self.assertEqual(recorded, docs)
        for rel in docs:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertEqual(text.count(STYLE_MARKER), 1, rel)
            self.assertEqual(text.count(SCRIPT_MARKER), 1 if rel in interactive else 0, rel)

    def test_css_and_javascript_are_structurally_valid(self) -> None:
        self.assertEqual(self.css.count("{"), self.css.count("}"))
        self.assertLessEqual(len(self.css.encode("utf-8")), 30000)
        self.assertLessEqual(len(self.js.encode("utf-8")), 8000)

    def test_generator_replaces_old_pin_once_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "assets").mkdir()
            (root / "assets/szl-responsive-apex-v3.js").write_bytes(b"const reviewed = true;\n")
            page = root / "index.html"
            page.write_text('<html><head></head><body>' + BINDER.SCRIPT + '</body></html>', encoding="utf-8")
            with patch.object(BINDER, "ROOT", root):
                BINDER.bind(page, {"index.html"})
                bound = page.read_bytes()
                text = bound.decode("utf-8")
                self.assertTrue(BINDER.is_bound("index.html", text, {"index.html"}))
                self.assertEqual(text.count(SCRIPT_MARKER), 1)
                self.assertIn('integrity="sha256-', text)
                BINDER.bind(page, {"index.html"})
                self.assertEqual(page.read_bytes(), bound)
                (root / "assets/szl-responsive-apex-v3.js").write_bytes(b"const reviewed = false;\n")
                self.assertFalse(BINDER.is_bound("index.html", text, {"index.html"}))
                BINDER.bind(page, {"index.html"})
                changed = page.read_text(encoding="utf-8")
                self.assertNotEqual(changed, text)
                self.assertEqual(changed.count(SCRIPT_MARKER), 1)
                self.assertTrue(BINDER.is_bound("index.html", changed, {"index.html"}))
                BINDER.bind(page, set())
                self.assertIsNone(BINDER.script_span(page.read_text(encoding="utf-8")))

    def test_managed_script_detection_ignores_script_data_and_refuses_duplicates(self) -> None:
        self.assertIsNone(BINDER.script_span('<script>const text = ' + repr(BINDER.SCRIPT.replace('</script>', '<\\/script>')) + ';</script>'))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            BINDER.script_span(BINDER.SCRIPT + BINDER.SCRIPT)

    def test_managed_script_offsets_use_only_lf_line_boundaries(self) -> None:
        for separator in ("\u2028", "\u2029", "\f", "\v", "\r"):
            with self.subTest(separator=repr(separator)):
                text = "<p>a" + separator + "b\nc</p>\n" + BINDER.SCRIPT
                start, end = BINDER.script_span(text)
                self.assertEqual(text[start:end], BINDER.SCRIPT)
                self.assertEqual(text[:start], "<p>a" + separator + "b\nc</p>\n")


if __name__ == "__main__":
    unittest.main()
