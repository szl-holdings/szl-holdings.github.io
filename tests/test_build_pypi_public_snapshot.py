"""SIMULATED contracts for the public PyPI metadata projection; no packages execute."""
from __future__ import annotations
import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib, importlib.util, io, json
from pathlib import Path
import tempfile, unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_pypi_public_snapshot", ROOT / "scripts" / "build_pypi_public_snapshot.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
SHA = "a" * 40
DIGEST = "b" * 64
STAMP = "2020-01-01T12:00:00Z"
REPO = "szl-holdings/example"

def sources(private=False):
    return [{"id": REPO, "kind": "GitHub", "revision": SHA, "private": private}]

def snapshot():
    artifact = {"filename": "example_pkg-1.2.3-py3-none-any.whl", "url": "https://files.pythonhosted.org/packages/ab/cd/123/example_pkg-1.2.3-py3-none-any.whl", "sha256": DIGEST, "bytes": 123, "package_type": "bdist_wheel", "uploaded_at": STAMP, "yanked": False, "digest_evidence_class": "DECLARED", "provenance_url": "https://pypi.org/integrity/example-pkg/1.2.3/example_pkg-1.2.3-py3-none-any.whl/provenance", "attestation_signature_verification": "UNKNOWN"}
    package = {"package_name": "example-pkg", "version": "1.2.3", "pypi_url": "https://pypi.org/project/example-pkg/1.2.3/", "source_repositories": [REPO], "source_records": [{"repository": REPO, "revision": SHA, "metadata_path": "packages/example/pyproject.toml", "metadata_sha256": DIGEST, "declared_name": "example_pkg", "declared_version": "1.2.4", "discovery": "immutable pyproject name"}], "summary": "An untrusted description <script>example</script>.", "requires_python": ">=3.10", "artifacts": [artifact], "publication_evidence_class": "MEASURED", "source_attribution_evidence_class": "DECLARED", "source_package_binding": "UNKNOWN", "observed_at": STAMP}
    return {"schema_version": 1, "generated_at": STAMP, "evidence_class": "MEASURED", "public_github_repositories": 1, "immutable_pyproject_inputs": 1, "source_http_successes": 1, "source_errors": 0, "candidate_distributions": 1, "pypi_http_successes": 1, "published_public_distributions": 1, "coverage": builder.COVERAGE, "limitations": list(builder.LIMITATIONS), "packages": [package]}

class PyPIProjectionTests(unittest.TestCase):
    def refused(self, transform, public_sources=None):
        doc = snapshot(); transform(doc)
        with self.assertRaises(ValueError):
            builder.validate_snapshot(doc, sources() if public_sources is None else public_sources)

    def test_valid_metadata_keeps_observed_source_separate_from_published_package(self):
        doc = snapshot()
        self.assertIsNone(builder.validate_snapshot(doc, sources()))
        self.assertEqual(doc["packages"][0]["source_records"][0]["declared_version"], "1.2.4")
        self.assertEqual(doc["packages"][0]["version"], "1.2.3")
        self.assertEqual(doc["packages"][0]["source_package_binding"], "UNKNOWN")
        self.assertIn("<script>", doc["packages"][0]["summary"], "Descriptions remain untrusted text for the renderer to escape")

    def test_only_literal_public_github_sources_are_admitted(self):
        for private in (True, None, "false", 0):
            with self.subTest(private=private):
                self.refused(lambda x: None, sources(private))
        self.refused(lambda x: None, [{"id": REPO, "kind": "HF Model", "private": False}])
        self.refused(lambda x: None, [{"full_name": REPO, "private": False, "visibility": "private"}])
        builder.validate_snapshot(snapshot(), [{"full_name": REPO, "private": False, "visibility": "public"}])
        self.refused(lambda x:x["packages"][0]["source_repositories"].append("szl-holdings/private-example"))
        self.refused(lambda x:None, sources()+sources())

    def test_foreign_and_malformed_repository_ids_are_refused(self):
        for repo in ("other/example", "szl-holdings/..", "szl-holdings/example?token=private"):
            self.refused(lambda x:x["packages"][0].update(source_repositories=[repo]))

    def test_closed_allowlists_reject_private_extra_fields_at_every_level(self):
        mutations=[lambda x:x.update(raw_principals=["private"]), lambda x:x["packages"][0].update(local_path="C:/private"), lambda x:x["packages"][0]["source_records"][0].update(private_key="private"), lambda x:x["packages"][0]["artifacts"][0].update(headers={"Authorization":"private"})]
        for mutate in mutations:self.refused(mutate)

    def test_names_versions_and_version_specific_urls_are_canonical(self):
        for name in ("../pkg", "pkg?key=private", "", "x\nheader"):
            self.refused(lambda x:x["packages"][0].update(package_name=name))
        for version in ("main", "1/2", "1.2.3?private", ""):
            self.refused(lambda x:x["packages"][0].update(version=version))
        for url in ("https://pypi.org/project/example-pkg/", "http://pypi.org/project/example-pkg/1.2.3/", "https://pypi.org.evil.example/project/example-pkg/1.2.3/"):
            self.refused(lambda x:x["packages"][0].update(pypi_url=url))

    def test_normalized_duplicate_package_identity_is_refused(self):
        def mutate(doc):
            row=copy.deepcopy(doc["packages"][0]);row["package_name"]="Example_Pkg";doc["packages"].append(row);doc["published_public_distributions"]=2;doc["candidate_distributions"]=2;doc["pypi_http_successes"]=2
        self.refused(mutate)

    def test_source_paths_digests_revisions_and_name_matches_are_required(self):
        for path in ("../pyproject.toml", "a/../pyproject.toml", "/pyproject.toml", "C:/private/pyproject.toml", "a\\pyproject.toml", "requirements.txt", "pyproject.toml?key=private"):
            self.refused(lambda x:x["packages"][0]["source_records"][0].update(metadata_path=path))
        for sha in ("main", "A"*40, None):
            self.refused(lambda x:x["packages"][0]["source_records"][0].update(revision=sha))
        self.refused(lambda x:x["packages"][0]["source_records"][0].update(metadata_sha256="unknown"))
        self.refused(lambda x:x["packages"][0]["source_records"][0].update(declared_name="other-package"))
        self.refused(lambda x:x["packages"][0]["source_records"][0].update(repository="szl-holdings/unbound"))
        self.refused(lambda x:x["packages"][0].update(source_records=[]))
        self.refused(lambda x:x["packages"][0]["source_records"].append(copy.deepcopy(x["packages"][0]["source_records"][0])))
        self.refused(lambda x:x["packages"][0]["source_repositories"].append("szl-holdings/unbound-public"), sources()+[{"id":"szl-holdings/unbound-public", "kind":"GitHub", "private":False}])

    def test_artifact_urls_are_exact_allowed_origin_and_filename(self):
        for url in ("https://evil.example/example_pkg-1.2.3-py3-none-any.whl", "https://files.pythonhosted.org@evil.example/x.whl", "https://files.pythonhosted.org/packages/ab/other.whl", "https://files.pythonhosted.org/packages/../example_pkg-1.2.3-py3-none-any.whl", "https://files.pythonhosted.org/packages/ab/example_pkg-1.2.3-py3-none-any.whl?secret=x", "https://files.pythonhosted.org/packages/ab/\nexample_pkg-1.2.3-py3-none-any.whl", "https://files.pythonhosted.org/packages/%0A/example_pkg-1.2.3-py3-none-any.whl"):
            self.refused(lambda x:x["packages"][0]["artifacts"][0].update(url=url))
        self.refused(lambda x:x["packages"][0]["artifacts"][0].update(sha256="C"*64))
        self.refused(lambda x:x["packages"][0]["artifacts"][0].update(filename="wrong_pkg-1.2.3-py3-none-any.whl"))
        self.refused(lambda x:x["packages"][0]["artifacts"][0].update(bytes=True))
        self.refused(lambda x:x["packages"][0]["artifacts"].append(copy.deepcopy(x["packages"][0]["artifacts"][0])))
        self.refused(lambda x:x["packages"][0].update(artifacts=[]))

    def test_absent_provenance_is_honest_and_unverified_provenance_is_not_trust(self):
        doc=snapshot();doc["packages"][0]["artifacts"][0]["provenance_url"]=None
        builder.validate_snapshot(doc,sources())
        self.refused(lambda x:x["packages"][0]["artifacts"][0].update(provenance_url="https://pypi.org/integrity/other/1.2.3/file/provenance"))
        self.refused(lambda x:x["packages"][0]["artifacts"][0].update(attestation_signature_verification="MEASURED"))

    def test_provider_hashes_and_source_binding_cannot_be_upgraded(self):
        self.refused(lambda x:x["packages"][0].update(source_package_binding="MEASURED"))
        self.refused(lambda x:x["packages"][0].update(source_attribution_evidence_class="MEASURED"))
        self.refused(lambda x:x["packages"][0]["artifacts"][0].update(digest_evidence_class="MEASURED"))
        self.refused(lambda x:x.update(limitations=[]))

    def test_counts_timestamp_and_scalar_types_fail_closed(self):
        for key in ("schema_version", "public_github_repositories", "immutable_pyproject_inputs", "source_http_successes", "source_errors", "candidate_distributions", "pypi_http_successes", "published_public_distributions"):
            self.refused(lambda x:x.update({key:True}))
        self.refused(lambda x:x.update(published_public_distributions=2))
        self.refused(lambda x:x.update(source_errors=1))
        self.refused(lambda x:x.update(generated_at="2020-01-01T12:00:00+02:00"))
        self.refused(lambda x:x["packages"][0].update(observed_at="2020-01-02T12:00:00Z"))
        self.refused(lambda x:x.update(generated_at="2999-01-01T12:00:00Z"))

class PyPILoadAndCommandTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup);self.root=Path(self.temporary.name)
        self.package_path=self.root/"pypi.json";self.sources_path=self.root/"public.json"
        self.package_path.write_text(json.dumps(snapshot()),encoding="utf-8")
        self.sources_path.write_text(json.dumps({"assets":sources()}),encoding="utf-8")

    def test_loader_checks_expected_bytes_and_parses_verified_content(self):
        digest=hashlib.sha256(self.package_path.read_bytes()).hexdigest()
        self.assertEqual(builder.load_snapshot(self.package_path,sources(),expected_sha256=digest),snapshot())
        with self.assertRaises(ValueError):builder.load_snapshot(self.package_path,sources(),expected_sha256="c"*64)
        with self.assertRaises(ValueError):builder.load_snapshot(self.package_path,sources(),expected_sha256="invalid")

    def test_duplicate_json_keys_are_not_silently_overwritten(self):
        raw=self.package_path.read_text(encoding="utf-8");self.package_path.write_text(raw.replace('"schema_version": 1','"schema_version": 999, "schema_version": 1'),encoding="utf-8")
        with self.assertRaises(ValueError):builder.load_snapshot(self.package_path,sources())

    def test_check_is_offline_and_does_not_modify_committed_input(self):
        original=self.package_path.read_bytes();out=io.StringIO()
        with redirect_stdout(out):self.assertEqual(builder.main(["--check","--snapshot",str(self.package_path),"--public-sources",str(self.sources_path)]),0)
        self.assertEqual(original,self.package_path.read_bytes());receipt=json.loads(out.getvalue())
        self.assertEqual(receipt["public_pypi_distributions"],1)
        self.assertEqual(receipt["artifact_bytes_verified"],"NOT RUN")
        self.assertEqual(receipt["source_package_binding"],"UNKNOWN")

    def test_check_fails_without_public_source_visibility_and_does_not_write(self):
        self.sources_path.write_text(json.dumps({"assets":sources(True)}),encoding="utf-8");original=self.package_path.read_bytes();err=io.StringIO()
        with redirect_stderr(err):self.assertEqual(builder.main(["--check","--snapshot",str(self.package_path),"--public-sources",str(self.sources_path)]),1)
        self.assertEqual(original,self.package_path.read_bytes());self.assertIn("stopped",err.getvalue())

    def test_reviewed_committed_catalogue_is_valid_without_loading_packages(self):
        catalog=builder.load_snapshot(ROOT/"estate"/"pypi-packages.json",json.loads((ROOT/"estate"/"public-snapshot.json").read_text(encoding="utf-8"))["assets"])
        self.assertGreater(len(catalog["packages"]),0)
        self.assertEqual(len(catalog["packages"]),catalog["published_public_distributions"])

if __name__ == "__main__":unittest.main()
