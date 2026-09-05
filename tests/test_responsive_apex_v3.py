#!/usr/bin/env python3
"""Offline responsive contract for the SZL Holdings static company front door."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "assets" / "szl-responsive-apex-v3.css"
JS = ROOT / "assets" / "szl-responsive-apex-v3.js"
STATE = ROOT / "responsive-experience-v3.json"
STYLE_MARKER = 'data-szl-responsive-apex-v3="style"'
SCRIPT_MARKER = 'data-szl-responsive-apex-v3="script"'


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


if __name__ == "__main__":
    unittest.main()
