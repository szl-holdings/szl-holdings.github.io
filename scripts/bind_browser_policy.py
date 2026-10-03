#!/usr/bin/env python3
"""Bind an exact CSP and referrer policy to the static company HTML documents.

Run --write after reviewing script changes; CI uses --check and never repairs
its own input. This is an HTML meta policy, not an HTTP response-header policy.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
from html.parser import HTMLParser
import os
from pathlib import Path
import re
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
START = "<!-- szl:browser-policy v1 -->"
END = "<!-- /szl:browser-policy -->"
MANAGED = re.compile(
    re.escape(START)
    + r'\n<meta http-equiv="Content-Security-Policy" content="[^"<>\n]*">'
    + r'\n<meta name="referrer" content="no-referrer">\n'
    + re.escape(END) + r"\n"
)
EXCLUDED = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def script_hash(text: str) -> str:
    digest = hashlib.sha256(normalize_newlines(text).encode("utf-8")).digest()
    return "'sha256-" + base64.b64encode(digest).decode("ascii") + "'"


class Document(HTMLParser):
    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=False)
        self.text = text
        self.line_offsets = [0]
        self.line_offsets.extend(match.end() for match in re.finditer("\n", text))
        self.head_count = 0
        self.in_head = False
        self.charset_ends: list[int] = []
        self.policy_metas: list[str] = []
        self.head_comments: list[tuple[int, str]] = []
        self.script_sources: list[str] = []
        self.inline_scripts: list[str] = []
        self.pending_script: list[str] | None = None
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        names = [name for name, _ in attrs]
        if len(names) != len(set(names)):
            self.errors.append(f"duplicate attributes on <{tag}>")
        if tag == "head":
            self.head_count += 1
            self.in_head = True
        if tag == "meta":
            if values.get("charset"):
                if not self.in_head or values["charset"].lower() != "utf-8":
                    self.errors.append("charset must be UTF-8 in the head")
                line, column = self.getpos()
                self.charset_ends.append(self.line_offsets[line - 1] + column + len(self.get_starttag_text()))
            identity = (values.get("http-equiv") or "").lower()
            name = (values.get("name") or "").lower()
            if identity.startswith("content-security-policy") or name == "referrer":
                self.policy_metas.append(identity or name)
        if tag == "base":
            self.errors.append("base elements conflict with the browser policy")
        for name, value in attrs:
            if name.startswith("on"):
                self.errors.append(f"HTML event attribute {name} is prohibited")
            if name in {"href", "src", "action"} and value:
                if urlsplit(value.strip()).scheme.lower() == "javascript":
                    self.errors.append("javascript URLs are prohibited")
        if tag in {"script", "style", "link"} and self.in_head and not self.charset_ends:
            self.errors.append("charset and browser policy must precede resources")
        if tag == "script":
            if "src" in values:
                source = values.get("src") or ""
                parsed = urlsplit(source)
                if not source or parsed.scheme or parsed.netloc or "\\" in source:
                    self.errors.append("script src must be a nonempty local relative URL")
                self.script_sources.append(source)
                self.pending_script = None
            else:
                self.pending_script = []

    def handle_data(self, data: str) -> None:
        if self.pending_script is not None:
            self.pending_script.append(data)

    def handle_comment(self, data: str) -> None:
        if self.in_head:
            line, column = self.getpos()
            self.head_comments.append((self.line_offsets[line - 1] + column, data))

    def handle_endtag(self, tag: str) -> None:
        if tag == "head":
            self.in_head = False
        if tag == "script" and self.pending_script is not None:
            self.inline_scripts.append("".join(self.pending_script))
            self.pending_script = None


def policy_for(document: Document) -> str:
    sources = ["'self'"] if document.script_sources else []
    sources.extend(sorted({script_hash(script) for script in document.inline_scripts}))
    return "; ".join([
        "default-src 'none'",
        "base-uri 'none'",
        "object-src 'none'",
        "frame-src 'none'",
        "worker-src 'none'",
        "form-action 'none'",
        "connect-src 'none'",
        "script-src " + " ".join(sources or ["'none'"]),
        "script-src-attr 'none'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self'",
        "font-src 'self'",
        "media-src 'none'",
        "manifest-src 'self'",
    ])


def bind(text: str) -> str:
    text = normalize_newlines(text)
    if text.count(START) != text.count(END) or text.count(START) > 1:
        raise ValueError("browser policy markers must be one balanced pair")
    clean = text
    if START in text:
        original = Document(text)
        original.feed(text)
        original.close()
        if original.head_count != 1 or len(original.charset_ends) != 1:
            raise ValueError("managed policy requires exactly one head and UTF-8 charset")
        position = original.charset_ends[0]
        if text[position:position + 1] == "\n":
            position += 1
        match = MANAGED.match(text, position)
        if (
            match is None
            or (position, START[4:-3]) not in original.head_comments
            or (match.end() - len(END) - 1, END[4:-3]) not in original.head_comments
        ):
            raise ValueError("managed policy must be metadata-only head comments immediately after charset")
        # Remove only our verified head metadata; never erase script/catalog text.
        clean = text[:position] + text[match.end():]
    document = Document(clean)
    document.feed(clean)
    document.close()
    if document.head_count != 1 or len(document.charset_ends) != 1:
        document.errors.append("exactly one head and UTF-8 charset are required")
    if document.pending_script is not None:
        document.errors.append("unterminated inline script")
    if document.policy_metas:
        document.errors.append("unmanaged CSP or referrer policy: refuse to overwrite")
    if document.errors:
        raise ValueError("; ".join(document.errors))
    position = document.charset_ends[0]
    block = (
        START + '\n<meta http-equiv="Content-Security-Policy" content="'
        + policy_for(document) + '">\n<meta name="referrer" content="no-referrer">\n'
        + END + "\n"
    )
    # Reuse the existing newline after charset so re-running is byte-idempotent.
    if clean[position:position + 1] == "\n":
        position += 1
        return clean[:position] + block + clean[position:]
    return clean[:position] + "\n" + block + clean[position:]


def documents(root: Path) -> list[Path]:
    result = []
    for directory, names, files in os.walk(root, followlinks=False):
        names[:] = sorted(name for name in names if name not in EXCLUDED)
        result.extend(Path(directory, name) for name in sorted(files) if name.endswith(".html"))
    return sorted(result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="bind reviewed source into generated policy meta")
    mode.add_argument("--check", action="store_true", help="read-only check; fail for missing or stale policy")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    paths = documents(root)
    errors = []
    updates = []
    for path in paths:
        try:
            if path.is_symlink():
                raise ValueError("HTML symlinks are not supported")
            original = path.read_text(encoding="utf-8")
            expected = bind(original)
            if original != expected:
                updates.append((path, expected))
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"{path.relative_to(root).as_posix()}: {exc}")
    if not paths:
        errors.append("no HTML documents found")
    if args.check:
        errors.extend(f"{path.relative_to(root).as_posix()}: browser policy missing or stale" for path, _ in updates)
    if errors:
        print("Browser policy FAILED:\n - " + "\n - ".join(errors))
        return 1
    if args.write:
        for path, expected in updates:
            path.write_text(expected, encoding="utf-8", newline="\n")
    print(f"Browser policy: {len(paths)} HTML documents checked; {len(updates) if args.write else 0} updated.")
    print("Meta CSP + no-referrer; HTTP frame-ancestors/headers and separately published docs are not covered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
