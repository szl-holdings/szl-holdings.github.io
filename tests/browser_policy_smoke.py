#!/usr/bin/env python3
"""Run the real-browser policy smoke test on a GitHub-hosted Linux CI runner.

Uses only Python's standard library and the runner's preinstalled google-chrome.
This is not a user-browser automation entry point: execution requires
GITHUB_ACTIONS=true and Linux, uses a new temporary profile, serves only on
loopback, and never relaxes Chrome's CSP or sandbox. Run --help without Chrome.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urljoin, urlsplit


ROOT = Path(__file__).resolve().parents[1]
PREFIX = "/__browser_policy_smoke__/"
ROUTES = ("root", "brain", "khipu", "frontier", "showcase", "products")
DOCUMENTS = (
    "index.html", "brain/index.html", "khipu/index.html", "frontier/index.html",
    "frontier/showcase-public.html", "products/index.html",
)
PINNED_ROUTES = ("root", "brain", "khipu")
PROBE_KINDS = ("connect", "image", "script_no_integrity", "script_wrong_integrity", "script_tampered")
SCRIPT_SENTINEL = b"window.__szlDisallowedExternalScript += 1;\n"
PIXEL = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
HARNESS = b"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>CI browser policy harness</title></head><body>
<h1>CI browser policy harness</h1><pre id="result">INCOMPLETE</pre>
<div id="fixture"></div>
<script src="/__browser_policy_smoke__/harness.js"></script></body></html>"""


class ResultParser(HTMLParser):
    """Extract exactly one result without treating arbitrary DOM text as proof."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.inside = False
        self.matches = 0
        self.fragments: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "pre" and dict(attrs).get("id") == "result":
            self.matches += 1
            self.inside = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "pre":
            self.inside = False

    def handle_data(self, data: str) -> None:
        if self.inside:
            self.fragments.append(data)


class SourceParser(HTMLParser):
    """Read policy and external-script pins independently of the policy binder."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.policies: list[str] = []
        self.scripts: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "meta" and (values.get("http-equiv") or "").lower() == "content-security-policy":
            self.policies.append(values.get("content") or "")
        if tag == "script" and "src" in values:
            self.scripts.append(values)


def verify_source_pins() -> None:
    """Require committed SRI/CSP to describe the exact local script bytes."""
    sentinel_integrity = "sha256-" + base64.b64encode(hashlib.sha256(SCRIPT_SENTINEL).digest()).decode("ascii")
    for route, relative in zip(ROUTES, DOCUMENTS, strict=True):
        page = ROOT / relative
        source = SourceParser()
        source.feed(page.read_text(encoding="utf-8"))
        if len(source.policies) != 1:
            raise RuntimeError(f"Expected one committed CSP: {relative}")
        directives = [item.split() for item in source.policies[0].split(";") if item.strip()]
        script_directives = [item[1:] for item in directives if item[0] == "script-src"]
        if len(script_directives) != 1:
            raise RuntimeError(f"Expected one explicit script-src: {relative}")
        allowed = script_directives[0]
        if not allowed or "'self'" in allowed or any(
            token != "'none'" and not (token.startswith("'sha256-") and token.endswith("'"))
            for token in allowed
        ):
            raise RuntimeError(f"Script policy is not hash-only or deny-all: {relative}")
        if "'" + sentinel_integrity + "'" in allowed:
            raise RuntimeError(f"Negative sentinel unexpectedly authorized: {relative}")
        if bool(source.scripts) != (route in PINNED_ROUTES):
            raise RuntimeError(f"Unexpected external-script source coverage: {relative}")
        for script in source.scripts:
            resolved = urlsplit(urljoin("http://127.0.0.1/" + relative, script.get("src") or ""))
            asset = (ROOT / unquote(resolved.path).lstrip("/")).resolve()
            if resolved.scheme != "http" or resolved.netloc != "127.0.0.1" or not asset.is_relative_to(ROOT.resolve()):
                raise RuntimeError(f"Nonlocal script source: {relative}: {script.get('src')}")
            expected = "sha256-" + base64.b64encode(hashlib.sha256(asset.read_bytes()).digest()).decode("ascii")
            if script.get("integrity") != expected or "'" + expected + "'" not in allowed:
                raise RuntimeError(f"Source/SRI/CSP hash mismatch: {relative}: {script.get('src')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true" or not sys.platform.startswith("linux"):
        parser.error("Chrome execution is CI-runner-only (GitHub Actions on Linux)")
    chrome = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
    if chrome is None:
        parser.error("required preinstalled google-chrome is absent; cannot skip browser proof")

    session = secrets.token_hex(16)
    observations: dict[str, dict[str, list[str | None]]] = {}
    invalid_probes: list[str] = []
    lock = threading.Lock()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(ROOT), **kwargs)

        def log_message(self, *_args: object) -> None:
            pass

        def reply(self, body: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def reject_probe(self, path: str) -> None:
            with lock:
                invalid_probes.append(path)
            self.send_error(400, "Invalid test probe")

        def do_GET(self) -> None:
            target = urlsplit(self.path)
            if not target.path.startswith(PREFIX):
                # Serve the committed page bytes: no test script or policy injection.
                super().do_GET()
                return
            if target.path == PREFIX:
                self.reply(HARNESS, "text/html; charset=utf-8")
                return
            if target.path == PREFIX + "harness.js":
                self.reply(Path(__file__).with_suffix(".js").read_bytes(), "text/javascript")
                return
            query = parse_qs(target.query)
            if query.get("session") != [session]:
                self.reject_probe(target.path)
                return
            kind = target.path.removeprefix(PREFIX)
            if kind == "observations":
                if set(query) != {"session"}:
                    self.reject_probe(target.path)
                    return
                with lock:
                    body = json.dumps(observations).encode("utf-8")
                self.reply(body, "application/json")
                return
            token = query.get("token", [""])
            if (kind not in PROBE_KINDS or set(query) != {"session", "token"}
                    or len(token) != 1 or token[0] not in (*ROUTES, "control")):
                self.reject_probe(target.path)
                return
            with lock:
                entry = observations.setdefault(token[0], {kind: [] for kind in PROBE_KINDS})
                entry[kind].append(self.headers.get("Referer"))
            if kind == "image":
                self.reply(PIXEL, "image/gif")
            elif kind.startswith("script_"):
                self.reply(SCRIPT_SENTINEL, "text/javascript; charset=utf-8")
            else:
                self.reply(b'{"sentinel":"reachable"}', "application/json")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        verify_source_pins()
        with tempfile.TemporaryDirectory(prefix="szl-browser-policy-") as profile:
            command = [
                chrome,
                "--headless=new",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-default-apps",
                "--disable-dev-shm-usage",
                "--force-prefers-reduced-motion",
                f"--user-data-dir={profile}",
                "--window-size=1100,900",
                "--dump-dom",
                "--virtual-time-budget=90000",
                f"http://127.0.0.1:{server.server_port}{PREFIX}?session={session}",
            ]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
        if completed.returncode:
            raise RuntimeError(f"Chrome failed ({completed.returncode}): {completed.stderr[-8000:]}")
        result_parser = ResultParser()
        result_parser.feed(completed.stdout)
        if result_parser.matches != 1:
            raise RuntimeError("Chrome did not return exactly one completed harness result")
        try:
            result = json.loads("".join(result_parser.fragments))
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Browser result missing or incomplete: {completed.stderr[-8000:]}") from error
        if (
            not isinstance(result, dict)
            or result.get("status") != "PASS"
            or result.get("session") != session
            or result.get("routes") != list(ROUTES)
            or not isinstance(result.get("assertions"), list)
            or not result["assertions"]
            or any(item.get("ok") is not True for item in result["assertions"])
            or result.get("script_probes") != {
                route: ["no_integrity", "wrong_integrity"] + (
                    ["approved_source_no_integrity", "tampered_bytes"] if route in PINNED_ROUTES else []
                ) for route in ROUTES
            }
        ):
            raise RuntimeError("Browser policy failure: " + json.dumps(result, ensure_ascii=True))
        # Independently validate actual HTTP observations; a rejected promise alone
        # does not demonstrate that a network request was prevented.
        with lock:
            evidence = json.loads(json.dumps(observations))
            invalid = list(invalid_probes)
        if invalid or set(evidence) != {*ROUTES, "control"}:
            raise RuntimeError("Incomplete or unexpected server-side sentinel coverage")
        control_evidence = evidence["control"]
        if (set(control_evidence) != set(PROBE_KINDS)
                or len(control_evidence["connect"]) != 1
                or len(control_evidence["script_no_integrity"]) != 1
                or any(control_evidence[kind] for kind in ("image", "script_wrong_integrity", "script_tampered"))):
            raise RuntimeError("Incomplete or unexpected unprotected-parent control requests")
        for route in ROUTES:
            expected = {kind: [] for kind in PROBE_KINDS}
            expected["image"] = [None]
            if route in PINNED_ROUTES:
                expected["script_tampered"] = [None]
            if evidence[route] != expected:
                raise RuntimeError(f"Network or referrer isolation failed: {route}: {evidence[route]}")
        print(json.dumps(result, indent=2, ensure_ascii=True))
        print("PASS: six real documents; hash-only scripts; CSP blocks unapproved external requests; "
              "SRI rejects three altered responses; approved UI runs; no Referer on allowed child requests")
        return 0
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
