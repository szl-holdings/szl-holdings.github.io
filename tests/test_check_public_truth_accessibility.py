"""The public truth and accessibility contract passes on this tree and fails closed."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_public_truth_accessibility.py"
WORKFLOW = ROOT / ".github" / "workflows" / "link-check.yml"
STEP = "      - name: Check public truth and accessibility contract"
# Every file the contract reads, relative to the directory it runs in.
INPUTS = (
    "CNAME",
    "app.js",
    "brain/index.html",
    "estate/public-catalog.json",
    "index.html",
    "khipu/index.html",
    "origin-authority.json",
    "origin-status.json",
    "products/catalog.json",
    "products/index.html",
    "robots.txt",
    "sitemap.xml",
    "styles.css",
)
JSON_LD = re.compile(r'(<script type="application/ld\+json">)(.*?)(</script>)', re.DOTALL)


def run_contract(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=cwd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )


class PublicTruthAccessibilityContract(unittest.TestCase):
    def test_committed_tree_passes(self):
        result = run_contract(ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout, "OK: 16 required and 7 prohibited truth checks passed.\n"
        )

    def test_missing_organization_node_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            for name in INPUTS:
                target = fixture / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            page = fixture / "index.html"
            html_text = page.read_bytes().decode("utf-8")
            blocks = JSON_LD.findall(html_text)
            self.assertEqual(len(blocks), 1)
            document = json.loads(blocks[0][1])
            graph = document["@graph"]
            document["@graph"] = [
                node for node in graph if node.get("@type") != "Organization"
            ]
            self.assertEqual(len(document["@graph"]), len(graph) - 1)
            page.write_bytes(
                JSON_LD.sub(
                    lambda match: match.group(1) + json.dumps(document, indent=2) + match.group(3),
                    html_text,
                    count=1,
                ).encode("utf-8")
            )
            result = run_contract(fixture)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "Public truth contract FAILED:\n"
            " - JSON-LD must contain exactly one Organization; observed 0\n"
            " - JSON-LD Organization identity must bind to the canonical origin\n"
            " - JSON-LD Organization sameAs must retain the separate A11oy product origin\n",
        )

    def test_link_check_step_runs_the_script(self):
        lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines.count(STEP), 1)
        commands = []
        for line in lines[lines.index(STEP) + 1:]:
            if line.strip() and len(line) - len(line.lstrip(" ")) < 8:
                break
            commands.append(line.strip())
        self.assertIn("python3 scripts/check_public_truth_accessibility.py", commands)
        self.assertFalse([command for command in commands if "<<" in command])


if __name__ == "__main__":
    unittest.main()
