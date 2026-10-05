"""Synthetic invariants for the reusable public estate projection builder."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_estate_public_snapshot", ROOT / "scripts" / "build_estate_public_snapshot.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
SHA = "a" * 40
OTHER_SHA = "b" * 40
OBSERVED = "2026-10-05T12:45:00Z"
FIELDS = {
    "id", "kind", "url", "revision", "archived", "category", "ci",
    "state", "sourceUrl", "ciUrl", "private",
}


def github_row(name="atlas", **extra):
    return {"full_name": "szl-holdings/" + name, "private": False,
            "language": "Python", "archived": False, **extra}


def hf_row(name="atlas", **extra):
    return {"id": "SZLHOLDINGS/" + name, "private": False, "type": "model",
            "sha": SHA, "files": ["config.json"], "files_coverage": "LISTED",
            "files_revision": SHA, "card": {}, **extra}


def report(**extra):
    return {"commit_sha": SHA, "latest_by_workflow": [],
            "workflow_history_window": 0, **extra}


class PublicBuilderTests(unittest.TestCase):
    def project(self, github=(), hf=(), reports=None):
        return builder.build_snapshot(list(github), reports or {}, list(hf), OBSERVED)

    def test_literal_public_only_and_closed_field_allowlist(self):
        github = [github_row("public")]
        hf = [hf_row("public")]
        for index, private in enumerate((True, None, "false", 0)):
            github.append(github_row("excluded" + str(index), private=private))
            hf.append(hf_row("excluded" + str(index), private=private))
        github.append({"full_name": "szl-holdings/missing-private"})
        hf.append({"id": "SZLHOLDINGS/missing-private", "type": "model"})
        github[0].update(local_path="C:/private", principal="secret", errors=["secret"])
        hf[0].update(local_path="C:/private", principal="secret", errors=["secret"])
        result = self.project(github, hf, {"szl-holdings/public": report()})
        self.assertEqual(len(result["assets"]), 2)
        self.assertTrue(all(a["private"] is False for a in result["assets"]))
        self.assertTrue(all(set(a) == FIELDS for a in result["assets"]))
        self.assertNotIn("secret", json.dumps(result))
        self.assertNotIn("C:/private", json.dumps(result))
        self.assertEqual(result["counts"], {"GitHub": 1, "HF Model": 1,
                                            "HF Dataset": 0, "HF Space": 0})

    def test_scope_is_canonical_and_links_are_constructed(self):
        gh = github_row(html_url="https://untrusted.example")
        hf = hf_row(url="javascript:alert(1)")
        result = self.project([gh, {**gh, "full_name": "other-org/atlas"}],
                              [hf, {**hf, "id": "other-owner/atlas"}],
                              {"szl-holdings/atlas": report()})
        self.assertEqual(len(result["assets"]), 2)
        self.assertEqual(result["assets"][0]["sourceUrl"],
                         "https://github.com/szl-holdings/atlas/tree/" + SHA)
        self.assertEqual(result["assets"][1]["sourceUrl"],
                         "https://huggingface.co/SZLHOLDINGS/atlas/tree/" + SHA)

    def test_public_missing_or_mutable_revision_stops_build(self):
        for revision in (None, "", "main", "refs/heads/main", "a" * 12,
                         "A" * 40, "a" * 40 + "/README.md"):
            with self.subTest(revision=revision):
                with self.assertRaises(ValueError):
                    self.project([github_row()], reports={"szl-holdings/atlas": report(commit_sha=revision)})
                with self.assertRaises(ValueError):
                    self.project(hf=[hf_row(sha=revision)])
        with self.assertRaises(ValueError):
            self.project([github_row()])

    def test_duplicate_public_rows_and_invalid_names_stop_build(self):
        with self.assertRaises(ValueError):
            self.project(hf=[hf_row(), hf_row()])
        with self.assertRaises(ValueError):
            self.project(hf=[hf_row(id='SZLHOLDINGS/atlas" onclick="alert(1)')])

    def test_ci_only_exact_head_bounded_metadata(self):
        base = "https://github.com/szl-holdings/atlas/actions/runs/"
        runs = [
            {"head_sha": SHA, "status": "completed", "conclusion": "success", "html_url": base + "12"},
            {"head_sha": SHA, "status": "completed", "conclusion": "failure", "html_url": base + "13"},
            {"head_sha": SHA, "status": "in_progress", "conclusion": None, "html_url": base + "14"},
            {"head_sha": SHA, "status": "completed", "conclusion": None, "html_url": "https://untrusted.example"},
            {"head_sha": OTHER_SHA, "status": "completed", "conclusion": "success", "html_url": base + "15"},
        ]
        ci, url = builder.summarize_ci("szl-holdings/atlas", SHA,
                                       report(latest_by_workflow=runs, workflow_history_window=100))
        for expected in ("1 SUCCESS", "1 FAILURE", "1 IN_PROGRESS", "1 UNKNOWN",
                         "1 older", "bounded latest 100", "absent workflows UNKNOWN"):
            self.assertIn(expected, ci)
        self.assertNotIn("2 SUCCESS", ci)
        self.assertRegex(url, re.escape(base) + r"(?:12|13|14)$")
        ci, url = builder.summarize_ci("szl-holdings/atlas", SHA,
                                       report(latest_by_workflow=[runs[-1]]))
        self.assertIn("UNKNOWN at collected SHA", ci)
        self.assertEqual(url, "")
        ci, url = builder.summarize_ci("szl-holdings/atlas", SHA,
                                       {"errors": ["actions: credential details must stay local"]})
        self.assertIn("UNAVAILABLE", ci)
        self.assertNotIn("credential", ci)
        self.assertEqual(url, "")

    def test_hf_categories_gates_and_runtime_limits(self):
        rows = [hf_row("kernel", is_kernel=True),
                hf_row("weights", files=["adapter.safetensors"]),
                hf_row("numeric", files=["fixture.npz"]),
                hf_row("recipe", files=["scripts/train.py"]),
                hf_row("unknown", files_coverage="UNKNOWN", files=["model.gguf"]),
                hf_row("stale-files", files_revision=OTHER_SHA, files=["model.gguf"]),
                hf_row("SZL-Khipu-1.5B", card={"szl": {"publication_eligible": False}}),
                hf_row("dataset", type="dataset"),
                hf_row("space", type="space", sdk="gradio",
                       runtime={"stage": "RUNNING", "hardware": "cpu-basic"})]
        result = {a["id"].split("/")[1]: a for a in self.project(hf=rows)["assets"]}
        for name, category in (("kernel", "Kernel / software"),
                               ("weights", "Tensor / GGUF artifact"),
                               ("numeric", "Numeric archive / fixture"),
                               ("recipe", "Training recipe"),
                               ("unknown", "Artifact inventory UNKNOWN"),
                               ("stale-files", "Artifact inventory UNKNOWN")):
            self.assertEqual(result[name]["category"], category)
        self.assertIn("DECLARED", result["SZL-Khipu-1.5B"]["state"])
        self.assertIn("2/6", result["SZL-Khipu-1.5B"]["state"])
        self.assertIn("BLOCKED", result["SZL-Khipu-1.5B"]["state"])
        self.assertIn("rows NOT RUN", result["dataset"]["state"])
        self.assertIn("REPORTED RUNNING", result["space"]["state"])
        self.assertIn("source/runtime parity UNKNOWN", result["space"]["state"])

    def test_html_escaping_and_browser_policy_preserved(self):
        attack = 'Python </p><script>alert("x")</script> & "quoted"'
        snapshot = self.project([github_row(language=attack)],
                                reports={"szl-holdings/atlas": report()})
        template = (ROOT / "estate" / "index.html").read_text(encoding="utf-8")
        rendered = builder.render_page(template, snapshot)
        self.assertNotIn('<script>alert("x")</script>', rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("&amp;", rendered)
        self.assertIn("&quot;quoted&quot;", rendered)
        self.assertIn('datetime="' + OBSERVED + '"', rendered)
        self.assertIn("1 public assets in this snapshot", rendered)
        self.assertEqual(re.findall(r'<script.*?</script>', rendered, re.S),
                         re.findall(r'<script.*?</script>', template, re.S))
        self.assertEqual(rendered.split('</head>')[0], template.split('</head>')[0])
        self.assertNotIn("fetch(", rendered)
        self.assertNotIn("innerHTML", rendered)
        with self.assertRaises(ValueError):
            builder.render_page(template.replace('id="estate-grid"', 'id="missing-grid"'), snapshot)

    def test_explicit_observed_at_and_raw_directory_contract(self):
        for timestamp in ("", "2026-10-05", "2026-10-05T12:45:00", "2026-10-05T12:45:00+02:00"):
            with self.assertRaises(ValueError):
                builder.build_snapshot([], {}, [], timestamp)
        with tempfile.TemporaryDirectory() as temporary:
            audit_dir = Path(temporary)
            data_dir = audit_dir / "audit-data"
            data_dir.mkdir()
            (data_dir / "github-repositories.json").write_text("[]", encoding="utf-8")
            with self.assertRaises(ValueError):
                builder.load_audit(audit_dir)
            (data_dir / "huggingface-repositories.json").write_text("[]", encoding="utf-8")
            self.assertEqual(builder.load_audit(audit_dir), ([], {}, []))


if __name__ == "__main__":
    unittest.main()
