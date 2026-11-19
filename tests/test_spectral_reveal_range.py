"""Tall sections must be fully revealed while their top is in reading position.

/assets/szl-spectral-v2.css is a hash-pinned product asset whose scroll-driven reveal
ends at "cover 28%"; that range scales with section height, so tall sections stayed at
~0.8 opacity with a blur while being read. styles.css overrides only the range so the
reveal completes inside the entry phase, and keeps reduced-motion users animation-free.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLES = (ROOT / "styles.css").read_text(encoding="utf-8")
SPECTRAL = (ROOT / "assets/szl-spectral-v2.css").read_text(encoding="utf-8")

SELECTOR = 'body[data-szl-spectral="product"] :is(main > section,main > article,[data-szl-reveal="true"])'


class SpectralRevealRangeTest(unittest.TestCase):
    def test_override_targets_the_spectral_reveal_selectors(self):
        self.assertIn("animation-timeline: view()", SPECTRAL)
        for part in ("main > section", "main > article", '[data-szl-reveal="true"]'):
            self.assertIn(part, SPECTRAL)
        self.assertIn(SELECTOR, STYLES)

    def test_reveal_ends_within_entry_range(self):
        block = STYLES[STYLES.index(SELECTOR):]
        block = block[: block.index("}") + 1]
        match = re.search(r"animation-range:\s*entry\s+(\d+)%\s+entry\s+(\d+)%", block)
        self.assertIsNotNone(match, block)
        start, end = map(int, match.groups())
        self.assertLessEqual(start, end)
        # The section must be sharp once its top edge reaches mid-viewport.
        self.assertLessEqual(end, 50)
        self.assertNotIn("cover", block)

    def test_reduced_motion_still_disables_all_animation(self):
        reduced = STYLES[STYLES.index("@media(prefers-reduced-motion:reduce)"):]
        self.assertIn("*{animation:none!important}", reduced[:400])


if __name__ == "__main__":
    unittest.main()
