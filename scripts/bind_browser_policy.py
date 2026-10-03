#!/usr/bin/env python3
"""Bind exact script SRI, CSP and referrer policy to static company HTML.

Run --write after reviewing script changes; CI uses --check and never repairs
its own input. This is an HTML meta policy, not an HTTP response-header policy.
External script hashes describe LF-canonical Git source: CRLF text checkouts
are normalized, but lone CR is rejected. Deploy those canonical bytes; browsers
check the actual response bytes for SRI and do not perform this normalization.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
from html.parser import HTMLParser
import os
from pathlib import Path
import re
import stat
from urllib.parse import unquote, urlsplit


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
ATTRIBUTE = re.compile(
    r'''[ \t\n\f\r]+(?P<name>[^\s/=>"'`]+)'''
    r'''(?:[ \t\n\f\r]*=[ \t\n\f\r]*(?:"[^"]*"|'[^']*'|[^\s"'`=<>]+))?'''
)


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def script_hash(text: str) -> str:
    digest = hashlib.sha256(normalize_newlines(text).encode("utf-8")).digest()
    return "'sha256-" + base64.b64encode(digest).decode("ascii") + "'"


def canonical_script_bytes(path: Path) -> bytes:
    """Read LF Git-source bytes, not a claim about bytes served by a provider."""
    data = path.read_bytes().replace(b"\r\n", b"\n")
    if b"\r" in data:
        raise ValueError("external script contains a lone CR; LF source is required")
    data.decode("utf-8")
    return data


def script_integrity(path: Path) -> str:
    """Return the single unquoted SRI token for a reviewed local script file."""
    digest = hashlib.sha256(canonical_script_bytes(path)).digest()
    return "sha256-" + base64.b64encode(digest).decode("ascii")


def local_url_path(source: str) -> str:
    """Accept unambiguous local URLs only; queries do not select source bytes."""
    if not source or re.search(r"[\x00-\x20\x7f\\]", source):
        raise ValueError("script src must be a nonempty local URL without whitespace or backslashes")
    parsed = urlsplit(source)
    if parsed.scheme or parsed.netloc or source.startswith("//") or not parsed.path or "#" in source:
        raise ValueError("script src must be a local path without an origin or fragment")
    if re.search(r"%(?![0-9a-fA-F]{2})", parsed.path):
        raise ValueError("script src contains a malformed percent escape")
    path = unquote(parsed.path, errors="strict")
    if (
        re.search(r"[\x00-\x1f\x7f\\:%]", path)
        or re.search(r"%(?:2f|5c)", parsed.path, re.IGNORECASE)
        or (path != parsed.path and any(part in {".", ".."} for part in path.split("/")))
    ):
        raise ValueError("script src contains an encoded traversal or prohibited path character")
    return path


def is_link(path: Path) -> bool:
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        return True
    # Python 3.11 on Windows has no Path.is_junction(). Reject reparse points
    # there too rather than allowing an in-root junction to bypass the check.
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def contained_path(path: Path, root: Path) -> Path:
    """Reject symlinks/junctions and escapes before resolving a local path."""
    try:
        parts = path.relative_to(root).parts
    except ValueError as exc:
        raise ValueError("script path escapes the site root") from exc
    current = root
    for part in parts:
        current = current.parent if part == ".." else current / part
        if not current.is_relative_to(root):
            raise ValueError("script path escapes the site root")
        if is_link(current):
            raise ValueError("script and document paths must not contain symlinks or junctions")
    resolved = current.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("script path escapes the site root")
    return resolved


def script_path(source: str, *, root: Path | None, page: Path | None) -> Path:
    path = local_url_path(source)
    if root is None or page is None:
        raise ValueError("external script src requires explicit root and page context")
    root = Path(root).absolute()
    if is_link(root) or not root.is_dir() or root.resolve() != root:
        raise ValueError("site root must be a real directory without symlinks or junctions")
    page = Path(page)
    document = contained_path(page if page.is_absolute() else root / page, root)
    target = root / path.lstrip("/") if path.startswith("/") else document.parent / path
    target = contained_path(target, root)
    if not target.is_file():
        raise ValueError("script src must resolve to an existing regular file")
    return target


def bind_integrity_tag(tag: str, integrity: str) -> str:
    """Replace only the integrity attribute, preserving all other source text."""
    opening = re.match(r"<script\b", tag, re.IGNORECASE)
    if opening is None:
        raise ValueError("script source span does not identify a script start tag")
    position = opening.end()
    integrity_span = None
    while not re.fullmatch(r"[ \t\n\f\r]*>", tag[position:]):
        match = ATTRIBUTE.match(tag, position)
        if match is None:
            raise ValueError("unsupported or malformed script start-tag syntax")
        if match.group("name").lower() == "integrity":
            if integrity_span is not None:
                raise ValueError("duplicate script integrity attributes")
            integrity_span = (match.start("name"), match.end())
        position = match.end()
    attribute = 'integrity="' + integrity + '"'
    if integrity_span is None:
        return tag[:position] + " " + attribute + tag[position:]
    start, end = integrity_span
    return tag[:start] + attribute + tag[end:]


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
        self.script_tags: list[tuple[int, int, str, str]] = []
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
        if tag in {"script", "style", "link"} and not self.charset_ends:
            self.errors.append("charset and browser policy must precede resources")
        if tag == "script":
            if "src" in values:
                source = values.get("src") or ""
                try:
                    local_url_path(source)
                except (UnicodeError, ValueError) as exc:
                    self.errors.append(str(exc))
                self.script_sources.append(source)
                line, column = self.getpos()
                start = self.line_offsets[line - 1] + column
                raw = self.get_starttag_text()
                self.script_tags.append((start, start + len(raw), raw, source))
                self.pending_script = None
            else:
                self.pending_script = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self.errors.append("self-closing script tags are unsupported")
        super().handle_startendtag(tag, attrs)

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


def policy_for(document: Document, external_integrities: list[str]) -> str:
    if len(external_integrities) != len(document.script_sources):
        raise ValueError("every external script requires an exact integrity binding")
    sources = sorted(
        {script_hash(script) for script in document.inline_scripts}
        | {"'" + integrity + "'" for integrity in external_integrities}
    )
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


def bind(text: str, *, root: Path | None = None, page: Path | None = None) -> str:
    """Return reviewed source with regenerated pins; never write to the site."""
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
    replacements = []
    integrities = []
    for start, end, raw, source in document.script_tags:
        integrity = script_integrity(script_path(source, root=root, page=page))
        integrities.append(integrity)
        replacements.append((start, end, bind_integrity_tag(raw, integrity)))
    # Offsets refer to the unchanged source. Reverse edits preserve later spans.
    for start, end, replacement in reversed(replacements):
        clean = clean[:start] + replacement + clean[end:]
    position = document.charset_ends[0]
    block = (
        START + '\n<meta http-equiv="Content-Security-Policy" content="'
        + policy_for(document, integrities) + '">\n<meta name="referrer" content="no-referrer">\n'
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
    root = args.root.absolute()
    paths = documents(root)
    errors = []
    updates = []
    for path in paths:
        try:
            if path.is_symlink():
                raise ValueError("HTML symlinks are not supported")
            original = path.read_text(encoding="utf-8")
            expected = bind(original, root=root, page=path)
            if original != expected:
                updates.append((path, expected))
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"{path.relative_to(root).as_posix()}: {exc}")
    if not paths:
        errors.append("no HTML documents found")
    if args.check:
        errors.extend(f"{path.relative_to(root).as_posix()}: browser policy or script integrity missing or stale" for path, _ in updates)
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
