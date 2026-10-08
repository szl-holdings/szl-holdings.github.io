"""Synthetic invariants for the reusable public estate projection builder."""
from __future__ import annotations

import importlib.util
import copy
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch


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


def exhibit_manifest():
    return {
        "schema": "szl.public-research-exhibits/v1",
        "evidence_class": "DECLARED",
        "exhibits": [{
            "id": "receipt-example", "title": "Receipt source",
            "summary": "Inspect a source-only research example.",
            "limitations": "Runtime behavior and independent replay UNKNOWN.",
            "source_ids": [{"kind": "GitHub", "id": "szl-holdings/atlas"}],
        }],
    }


def exhibit_template():
    template = (ROOT / "estate" / "index.html").read_text(encoding="utf-8")
    if '<!-- estate-exhibits:start -->' not in template:
        template = template.replace(
            '    <div class="stats"',
            '<!-- estate-exhibits:start --><!-- estate-exhibits:end -->\n    <div class="stats"',
            1,
        )
    if 'id="estate-category"' not in template:
        template = template.replace(
            '    <div class="filters"',
            '<select id="estate-category"><option value="">All categories</option></select>\n    <div class="filters"',
            1,
        )
    return template


class ScriptCapture(HTMLParser):
    """Compare parsed script elements, including mixed-case HTML tag names."""
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.scripts = []
        self.current = None
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.current = (tuple(attrs), [])

    def handle_data(self, data):
        if self.current is not None:
            self.current[1].append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.current is not None:
            self.scripts.append((self.current[0], "".join(self.current[1])))
            self.current = None


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
                hf_row("oac-advisory", files=["model.json", "ops_health.py"]),
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
                                ("oac-advisory", "Software / JSON coefficients"),
                                ("recipe", "Training recipe"),
                               ("unknown", "Artifact inventory UNKNOWN"),
                               ("stale-files", "Artifact inventory UNKNOWN")):
            self.assertEqual(result[name]["category"], category)
        self.assertIn("DECLARED", result["SZL-Khipu-1.5B"]["state"])
        self.assertIn("2/6", result["SZL-Khipu-1.5B"]["state"])
        self.assertIn("BLOCKED", result["SZL-Khipu-1.5B"]["state"])
        self.assertIn("rows NOT RUN", result["dataset"]["state"])
        self.assertIn("DECLARED RUNNING", result["space"]["state"])
        self.assertIn("source/runtime parity UNKNOWN", result["space"]["state"])

    def test_html_escaping_and_browser_policy_preserved(self):
        attack = 'Python </p><ScRiPt>alert("x")</sCrIpT> & "quoted"'
        snapshot = self.project([github_row(language=attack)],
                                reports={"szl-holdings/atlas": report()})
        template = (ROOT / "estate" / "index.html").read_text(encoding="utf-8")
        rendered = builder.render_page(template, snapshot)
        self.assertNotIn('<ScRiPt>alert("x")</sCrIpT>', rendered)
        self.assertIn("&lt;ScRiPt&gt;", rendered)
        self.assertIn("&amp;", rendered)
        self.assertIn("&quot;quoted&quot;", rendered)
        self.assertIn('datetime="' + OBSERVED + '"', rendered)
        self.assertIn("1 public assets in this snapshot", rendered)
        self.assertEqual(ScriptCapture(rendered).scripts, ScriptCapture(template).scripts)
        self.assertEqual(ScriptCapture('<ScRiPt>alert("x")</sCrIpT>').scripts,
                         [((), 'alert("x")')])
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


class ResearchExhibitTests(unittest.TestCase):
    """SIMULATED source bindings protect the reviewed public curator manifest."""

    def setUp(self):
        self.snapshot = builder.build_snapshot(
            [github_row()], {"szl-holdings/atlas": report()},
            [hf_row("SZL-Khipu-1.5B")], OBSERVED,
        )
        self.manifest = exhibit_manifest()

    def test_curated_links_are_immutable_snapshot_links_and_failed_state_is_retained(self):
        self.manifest["exhibits"][0]["source_ids"].append(
            {"kind": "HF Model", "id": "SZLHOLDINGS/SZL-Khipu-1.5B"}
        )
        rendered = builder.render_exhibits(self.manifest, self.snapshot)
        for asset in self.snapshot["assets"]:
            self.assertIn('href="' + asset["sourceUrl"] + '"', rendered)
            self.assertIn(html_escape(asset["state"]), rendered)
        self.assertIn("promotion gate BLOCKED", rendered)
        self.assertIn("publication_eligible=false", rendered)
        self.assertIn("Runtime behavior and independent replay UNKNOWN.", rendered)
        self.assertIn("DECLARED", rendered)

    def test_missing_wrong_kind_and_nonliteral_public_sources_are_refused(self):
        reference = self.manifest["exhibits"][0]["source_ids"][0]
        for update in ({"id": "szl-holdings/missing"}, {"kind": "HF Model"}):
            manifest = copy.deepcopy(self.manifest)
            manifest["exhibits"][0]["source_ids"][0].update(update)
            with self.assertRaises(ValueError):
                builder.render_exhibits(manifest, self.snapshot)
        for private in (True, None, "false", 0):
            snapshot = copy.deepcopy(self.snapshot)
            snapshot["assets"][0]["private"] = private
            with self.assertRaises(ValueError):
                builder.render_exhibits(self.manifest, snapshot)
        self.assertEqual(reference["id"], "szl-holdings/atlas")

    def test_closed_manifest_rejects_raw_fields_external_urls_and_unsupported_class(self):
        for location, key, value in (
            ("manifest", "local_path", "C:/private"),
            ("exhibit", "url", "https://untrusted.example"),
            ("source", "revision", SHA),
            ("source", "sourceUrl", "https://untrusted.example"),
        ):
            manifest = copy.deepcopy(self.manifest)
            target = {"manifest": manifest, "exhibit": manifest["exhibits"][0],
                      "source": manifest["exhibits"][0]["source_ids"][0]}[location]
            target[key] = value
            with self.subTest(location=location, key=key), self.assertRaises(ValueError):
                builder.render_exhibits(manifest, self.snapshot)
        for evidence_class in ("MEASURED", "REPORTED", None):
            manifest = copy.deepcopy(self.manifest)
            manifest["evidence_class"] = evidence_class
            with self.assertRaises(ValueError):
                builder.render_exhibits(manifest, self.snapshot)

    def test_source_url_revision_and_duplicate_bindings_are_refused(self):
        for changes in ({"sourceUrl": "https://untrusted.example"},
                        {"sourceUrl": "https://github.com/szl-holdings/atlas/tree/main"},
                        {"revision": "main"}, {"revision": OTHER_SHA}):
            snapshot = copy.deepcopy(self.snapshot)
            snapshot["assets"][0].update(changes)
            with self.assertRaises(ValueError):
                builder.render_exhibits(self.manifest, snapshot)
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["assets"].append(snapshot["assets"][0])
        with self.assertRaises(ValueError):
            builder.render_exhibits(self.manifest, snapshot)
        manifest = copy.deepcopy(self.manifest)
        manifest["exhibits"][0]["source_ids"] *= 2
        with self.assertRaises(ValueError):
            builder.render_exhibits(manifest, self.snapshot)
        manifest = copy.deepcopy(self.manifest)
        manifest["exhibits"] *= 2
        with self.assertRaises(ValueError):
            builder.render_exhibits(manifest, self.snapshot)

    def test_curator_text_is_escaped_without_adding_script_or_link_elements(self):
        manifest = copy.deepcopy(self.manifest)
        attack = '</p><ScRiPt>alert("x")</sCrIpT> & "quoted"'
        manifest["exhibits"][0]["title"] = attack
        manifest["exhibits"][0]["summary"] = attack
        manifest["exhibits"][0]["limitations"] = attack
        rendered = builder.render_exhibits(manifest, self.snapshot)
        self.assertNotIn('<ScRiPt>', rendered)
        self.assertIn("&lt;ScRiPt&gt;", rendered)
        self.assertIn("&amp;", rendered)
        self.assertIn("&quot;quoted&quot;", rendered)
        self.assertEqual(ScriptCapture(rendered).scripts, [])
        self.assertEqual(rendered.count("href="), 1)
        for value in ("", None, "control\x00text", "line\nfeed", "x" * 2001):
            manifest["exhibits"][0]["summary"] = value
            with self.assertRaises(ValueError):
                builder.render_exhibits(manifest, self.snapshot)

    def test_rendering_preserves_scripts_and_requires_unique_exhibit_boundaries(self):
        template = exhibit_template()
        rendered = builder.render_page(template, self.snapshot, exhibits=self.manifest)
        self.assertIn('id="exhibit-receipt-example"', rendered)
        self.assertEqual(ScriptCapture(rendered).scripts, ScriptCapture(template).scripts)
        self.assertEqual(rendered, builder.render_page(rendered, self.snapshot, exhibits=self.manifest))
        for changed in (template.replace('<!-- estate-exhibits:start -->', ''),
                        template.replace('<!-- estate-exhibits:end -->', ''),
                        template + '<!-- estate-exhibits:start -->'):
            with self.assertRaises(ValueError):
                builder.render_page(changed, self.snapshot, exhibits=self.manifest)

    def test_category_options_and_card_attributes_escape_and_regenerate(self):
        template = exhibit_template()
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["assets"][0]["category"] = 'Kernel / "software" & <review>'
        snapshot["assets"][1]["category"] = snapshot["assets"][0]["category"]
        rendered = builder.render_page(template, snapshot)
        category = html_escape(snapshot["assets"][0]["category"])
        self.assertEqual(rendered.count('data-category="' + category + '"'), 2)
        self.assertEqual(rendered.count('<option value="' + category + '">'), 1)
        self.assertNotIn('<review>', rendered)
        snapshot["assets"][0]["category"] = "A category"
        snapshot["assets"][1]["category"] = "Z category"
        updated = builder.render_page(rendered, snapshot)
        self.assertNotIn('<option value="' + category + '">', updated)
        self.assertLess(updated.index('<option value="A category">'),
                        updated.index('<option value="Z category">'))
        self.assertEqual(updated, builder.render_page(updated, snapshot))

    def test_manifest_loader_rejects_ambiguous_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "exhibits.json"
            path.write_text(json.dumps(self.manifest), encoding="utf-8")
            self.assertEqual(builder.load_exhibits(path), self.manifest)
            for text in ('{"schema":"one","schema":"two"}', "[]", "{broken"):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    builder.load_exhibits(path)


def html_escape(value):
    import html
    return html.escape(value, quote=True)


class BoundAuditTests(unittest.TestCase):
    """SIMULATED collector assertions exercise the unsigned source contract."""
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.audit = Path(self.temporary.name) / "audit"
        self.site = Path(self.temporary.name) / "site"
        (self.audit / "audit-data").mkdir(parents=True)
        (self.audit / "execution").mkdir()
        (self.site / "estate").mkdir(parents=True)
        self.template = exhibit_template()
        (self.site / "estate" / "index.html").write_text(self.template, encoding="utf-8")
        (self.site / "estate" / "exhibits.json").write_text(json.dumps(exhibit_manifest()), encoding="utf-8")
        self.observed = "2020-01-01T12:45:00Z"
        github = [github_row(), github_row("private-fixture", private=True)]
        self.write("audit-data/github-repositories.json", github)
        self.write("audit-data/huggingface-repositories.json", [hf_row()])
        for row in github:
            self.write("audit-data/repo--" + row["full_name"].replace("/", "--") + ".json",
                       report(full_name=row["full_name"]))
        self.counts = {"GitHub": 2, "HF Model": 1, "HF Dataset": 0, "HF Space": 0}
        self.summary = {"generated_at": self.observed,
                        "coverage": {"github": 2, "github_inspected": 2, "hf": 1}}
        self.write("audit-data/estate-summary.json", self.summary)
        self.receipt = {"schema": "szl.local-estate-audit/v1", "signed": False,
                        "generated_at": self.observed, "counts": self.counts,
                        "source_summary_sha256": self.digest("audit-data/estate-summary.json")}
        self.write("audit-receipt.json", self.receipt)
        for name in builder.EXECUTION_NAMES:
            (self.audit / "execution" / name).write_bytes(b"# SIMULATED fixture\n")
        self.write("execution-source-binding.json", {
            "schema": "szl.audit-execution-source-binding/v1", "scope": builder.SCOPE,
            "files": [{"name": name, "execution_sha256": self.digest("execution/" + name)}
                      for name in sorted(builder.EXECUTION_NAMES - {"audit_guard.py"})],
            "guard_sha256": self.digest("execution/audit_guard.py")})
        self.write("github-request-ledger.jsonl", {
            "at": self.observed, "path": "orgs/szl-holdings/repos?type=all&per_page=100&page=1",
            "status": 200, "returncode": 0, "rate_failure": False})
        self.binding = {"schema": builder.BINDING_SCHEMA, "signed": False,
                        "scope": builder.SCOPE, "observed_at": self.observed,
                        "counts": {"raw": self.counts, "public": {**self.counts, "GitHub": 1}},
                        "completion": {
                            "collector": {"completed": True, "exit_code": 0, "evidence_class": "DECLARED",
                                          "command": "estate_agent.py all --output ."},
                            "github": {"enumeration_complete": True, "inspection_complete": True,
                                       "pagination": {"per_page": 100, "terminal_page": 1, "terminal_rows": 2}},
                            "huggingface": {"enumeration_complete": True,
                                            "iterators_exhausted": ["model", "dataset", "space"]}}}
        self.rebind()

    def write(self, name, value):
        (self.audit / name).write_text(json.dumps(value) + "\n", encoding="utf-8")

    def digest(self, name):
        return hashlib.sha256((self.audit / name).read_bytes()).hexdigest()

    def rebind(self):
        self.binding["input_sha256"] = {
            path.relative_to(self.audit).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.audit.rglob("*") if path.is_file() and path.name != "public-source-binding.json"}
        self.write("public-source-binding.json", self.binding)

    def cli(self, *extra):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return builder.main(["--audit-dir", str(self.audit), "--site-dir", str(self.site), *extra])

    def assert_refused_without_output(self, *extra):
        self.assertEqual(self.cli(*extra), 1)
        self.assertFalse((self.site / "estate" / "public-snapshot.json").exists())
        self.assertEqual((self.site / "estate" / "index.html").read_text(encoding="utf-8"), self.template)

    def test_cli_derives_time_and_retains_public_only_projection(self):
        self.assertEqual(self.cli(), 0)
        snapshot = json.loads((self.site / "estate" / "public-snapshot.json").read_bytes())
        self.assertEqual(snapshot["observed_at"], self.observed)
        self.assertEqual(snapshot["counts"], self.binding["counts"]["public"])
        self.assertNotIn("private-fixture", json.dumps(snapshot))
        self.assertNotIn("input_sha256", snapshot)
        self.assertEqual(builder.load_bound_audit(self.audit / "audit-data")[-1], self.observed)

    def test_missing_manifest_refuses_partial_input(self):
        (self.audit / "public-source-binding.json").unlink()
        self.assert_refused_without_output("--observed-at", self.observed)

    def test_missing_or_invalid_curator_manifest_refuses_before_either_output(self):
        manifest_path = self.site / "estate" / "exhibits.json"
        manifest_path.unlink()
        self.assert_refused_without_output()
        invalid = exhibit_manifest()
        invalid["exhibits"][0]["source_ids"][0]["id"] = "szl-holdings/missing"
        manifest_path.write_text(json.dumps(invalid), encoding="utf-8")
        self.assert_refused_without_output()

    def test_incomplete_collection_and_failed_collector_are_refused(self):
        for section, key, value in [("collector", "completed", False), ("collector", "exit_code", 1),
                                    ("collector", "exit_code", False), ("github", "enumeration_complete", False),
                                    ("github", "inspection_complete", False),
                                    ("huggingface", "iterators_exhausted", ["model", "dataset"])]:
            with self.subTest(section=section, key=key):
                original = self.binding["completion"][section][key]
                self.binding["completion"][section][key] = value
                self.rebind()
                self.assert_refused_without_output()
                self.binding["completion"][section][key] = original

    def test_hash_mismatch_is_refused_before_output(self):
        self.write("audit-data/github-repositories.json", [])
        self.assert_refused_without_output()

    def test_partial_census_cannot_pass_with_rehashed_inputs(self):
        self.write("audit-data/github-repositories.json", [github_row()])
        self.rebind()
        self.assert_refused_without_output()

    def test_scope_and_inspection_count_mismatch_are_refused(self):
        self.binding["scope"] = {"github": ["other-org"], "huggingface": ["SZLHOLDINGS"]}
        self.rebind()
        self.assert_refused_without_output()
        self.binding["scope"] = builder.SCOPE
        self.summary["coverage"]["github_inspected"] = 1
        self.write("audit-data/estate-summary.json", self.summary)
        self.receipt["source_summary_sha256"] = self.digest("audit-data/estate-summary.json")
        self.write("audit-receipt.json", self.receipt)
        self.rebind()
        self.assert_refused_without_output()

    def test_override_and_receipt_timestamp_conflicts_are_refused(self):
        self.assert_refused_without_output("--observed-at", "2020-01-01T12:45:01Z")
        self.receipt["generated_at"] = "2020-01-01T12:45:01Z"
        self.write("audit-receipt.json", self.receipt)
        self.rebind()
        self.assert_refused_without_output()

    def test_future_audit_date_is_refused_even_when_all_bindings_agree(self):
        self.observed = "2099-01-01T12:45:00Z"
        self.summary["generated_at"] = self.observed
        self.write("audit-data/estate-summary.json", self.summary)
        self.receipt.update(generated_at=self.observed,
                            source_summary_sha256=self.digest("audit-data/estate-summary.json"))
        self.write("audit-receipt.json", self.receipt)
        self.binding["observed_at"] = self.observed
        self.rebind()
        self.assert_refused_without_output()

    def test_pagination_failure_and_nonterminal_page_are_refused(self):
        self.write("github-request-ledger.jsonl", {"at": self.observed,
                   "path": "orgs/szl-holdings/repos?type=all&per_page=100&page=1",
                   "status": 403, "returncode": 1, "rate_failure": True})
        self.rebind()
        self.assert_refused_without_output()
        self.binding["completion"]["github"]["pagination"]["terminal_rows"] = 100
        self.rebind()
        self.assert_refused_without_output()

    def test_verified_inputs_are_read_once_and_parsed_from_cached_bytes(self):
        reads = []
        original_read = Path.read_bytes
        def read_once(path):
            reads.append(path.resolve())
            self.assertEqual(reads.count(path.resolve()), 1, "Input reread after hash verification")
            return original_read(path)
        with patch.object(Path, "read_bytes", read_once):
            github, reports, hf, stamp = builder.load_bound_audit(
                self.audit, now=datetime(2020, 1, 2, tzinfo=timezone.utc))
        self.assertEqual((len(github), len(reports), len(hf), stamp), (2, 1, 1, self.observed))


if __name__ == "__main__":
    unittest.main()
