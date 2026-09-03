#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Network-free contracts for product-front-door asset materialization."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "materialize_product_frontdoor_assets.py"
SPEC = importlib.util.spec_from_file_location("materialize_product_frontdoor_assets", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def fixture() -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    target = root / "target"
    source = root / "source"
    (target / "assets").mkdir(parents=True)
    (source / "console/assets").mkdir(parents=True)
    (target / "index.html").write_text(
        "<!doctype html><html><head><title>A11oy</title></head><body>Command</body></html>\n",
        encoding="utf-8",
    )
    (source / "console/assets/szl-holo-v2.css").write_text(
        ":root{--szl-accent:#3af4c8} body{min-width:0}\n", encoding="utf-8"
    )
    (source / "console/assets/szl-flow.js").write_text(
        "document.documentElement.dataset.szlFlow='true';\n", encoding="utf-8"
    )
    return temp, target, source


def test_materialization_binds_source_sha_assets_and_root() -> None:
    temp, target, source = fixture()
    with temp:
        sha = "a" * 40
        manifest = module.materialize(target, source, sha)
        verified = module.validate(target)
        index = (target / "index.html").read_text(encoding="utf-8")
        assert manifest == verified
        assert verified["source_revision"] == sha
        assert index.count(module.START) == 1
        assert index.count(module.END) == 1
        assert "/assets/szl-spectral-v2.css" in index
        assert "/assets/szl-flow-v2.js" in index
        assert (target / module.CSS_DEST).read_text(encoding="utf-8").startswith(":root")
        assert (target / module.JS_DEST).read_text(encoding="utf-8").startswith("document")


def test_second_apply_is_idempotent_except_manifest_clock() -> None:
    temp, target, source = fixture()
    with temp:
        sha = "b" * 40
        module.materialize(target, source, sha)
        first_index = (target / "index.html").read_bytes()
        first_css = (target / module.CSS_DEST).read_bytes()
        first_js = (target / module.JS_DEST).read_bytes()
        module.materialize(target, source, sha)
        final_index = (target / "index.html").read_bytes()
        assert final_index == first_index
        assert (target / module.CSS_DEST).read_bytes() == first_css
        assert (target / module.JS_DEST).read_bytes() == first_js
        assert final_index.count(module.START.encode()) == 1
        assert b"    <!-- SZL-PRODUCT-FRONTDOOR-ASSETS-V2:START -->" not in final_index


def test_invalid_source_sha_fails_closed() -> None:
    temp, target, source = fixture()
    with temp:
        try:
            module.materialize(target, source, "main")
        except module.MaterializeError as exc:
            assert "40-character" in str(exc)
        else:
            raise AssertionError("mutable source ref was accepted")


def test_missing_assets_fail_closed() -> None:
    temp, target, source = fixture()
    with temp:
        (source / "console/assets/szl-holo-v2.css").unlink()
        try:
            module.materialize(target, source, "c" * 40)
        except module.MaterializeError as exc:
            assert "no reviewed Spectral CSS candidate" in str(exc)
        else:
            raise AssertionError("missing CSS was accepted")


def test_external_runtime_dependencies_are_rejected() -> None:
    temp, target, source = fixture()
    with temp:
        (source / "console/assets/szl-holo-v2.css").write_text(
            '@import url("https://cdn.example.invalid/theme.css");\n', encoding="utf-8"
        )
        try:
            module.materialize(target, source, "d" * 40)
        except module.MaterializeError as exc:
            assert "external runtime dependency" in str(exc)
        else:
            raise AssertionError("external CSS dependency was accepted")


def test_digest_tampering_breaks_validation() -> None:
    temp, target, source = fixture()
    with temp:
        module.materialize(target, source, "e" * 40)
        (target / module.JS_DEST).write_text("tampered\n", encoding="utf-8")
        try:
            module.validate(target)
        except module.MaterializeError as exc:
            assert "digest mismatch" in str(exc)
        else:
            raise AssertionError("tampered asset passed")


def test_manifest_makes_no_runtime_or_dns_claim() -> None:
    temp, target, source = fixture()
    with temp:
        manifest = module.materialize(target, source, "f" * 40)
        assert manifest["claims"] == {
            "static_asset_materialized": True,
            "runtime_health": "NOT_CLAIMED",
            "dns_or_edge_changed": False,
            "token_value_recorded": False,
        }
        encoded = json.dumps(manifest)
        assert "secret" not in encoded.casefold()
