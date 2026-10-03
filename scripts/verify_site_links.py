#!/usr/bin/env python3
"""Offline link/asset checks for every published HTML page in this Pages tree.

External URLs and the separately published docs root are not availability
checks. This guard verifies committed files and HTML fragment targets only.
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import os
from pathlib import Path
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


LOCAL_HOSTS = {"holdings.a-11-oy.com", "szl-holdings.github.io"}
SEPARATE_ROUTES = {"/docs-site/"}
IGNORED_DIRECTORIES = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}


def normalized_hostname(hostname: str) -> str:
    """Recognize encoded local DNS names before classifying a URL as external."""
    hostname = unquote(hostname, errors="strict")
    if any(character.isspace() or ord(character) < 32 or character in "%/\\?#@" for character in hostname):
        raise ValueError("URL hostname has a prohibited character")
    if ":" in hostname:  # urlsplit has already parsed an IPv6 literal.
        return hostname.lower()
    return hostname.encode("idna").decode("ascii").lower().rstrip(".")


class Document(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.refs: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        for name in ("href", "src", "id"):
            if sum(key == name for key, _ in attrs) > 1:
                self.errors.append(f"duplicate {name} attribute on <{tag}>")
        identifier = values.get("id")
        if identifier:
            if identifier in self.ids:
                self.errors.append(f"duplicate HTML id: {identifier}")
            self.ids.add(identifier)
        # Named anchors remain valid HTML fragment destinations.
        if tag == "a" and values.get("name"):
            self.ids.add(values["name"])
        if tag == "base":
            self.errors.append("<base> is unsupported: local routes must resolve from their page")
        for name in ("href", "src"):
            if values.get(name):
                self.refs.append(values[name])
        if tag == "meta":
            identity = values.get("property") or values.get("name") or ""
            if identity in {"og:image", "twitter:image"} and values.get("content"):
                self.refs.append(values["content"])


def html_files(root: Path) -> list[Path]:
    result = []
    for directory, names, files in os.walk(root, followlinks=False):
        names[:] = sorted(name for name in names if name not in IGNORED_DIRECTORIES)
        result.extend(Path(directory, name) for name in sorted(files) if name.endswith(".html"))
    return sorted(result)


def verify(root: Path) -> tuple[int, list[str]]:
    root = root.resolve()
    errors: list[str] = []
    documents: dict[Path, Document] = {}
    for page in html_files(root):
        label = page.relative_to(root).as_posix()
        if page.is_symlink():
            errors.append(f"{label}: published HTML must not be a symlink")
            continue
        document = Document()
        try:
            document.feed(page.read_text(encoding="utf-8"))
            document.close()
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"{label}: cannot parse HTML: {exc}")
            continue
        documents[page.resolve()] = document
        errors.extend(f"{label}: {message}" for message in document.errors)

    if not documents:
        errors.append("no HTML pages found")

    for page, document in documents.items():
        label = page.relative_to(root).as_posix()
        for reference in document.refs:
            try:
                parsed = urlsplit(reference)
                if parsed.scheme and parsed.scheme not in {"http", "https"}:
                    continue
                if parsed.netloc:
                    hostname = normalized_hostname(parsed.hostname or "")
                    if hostname not in LOCAL_HOSTS:
                        continue
                    # Validate rather than silently accepting a malformed local URL.
                    parsed.port
                    if parsed.username is not None or parsed.password is not None:
                        raise ValueError("local URL must not contain user information")
                elif parsed.scheme:
                    raise ValueError("HTTP URL must include a host")
                path = unquote(parsed.path, errors="strict")
                if "\\" in path or "\x00" in path:
                    raise ValueError("local URL has a prohibited path character")
                if path in SEPARATE_ROUTES and (parsed.netloc or path.startswith("/")):
                    continue
                if parsed.netloc or path.startswith("/"):
                    target = root / path.lstrip("/")
                elif path:
                    target = page.parent / path
                else:
                    target = page
                target = target.resolve()
                if not target.is_relative_to(root):
                    raise ValueError("local URL escapes the site root")
                if path.endswith("/") and not target.is_dir():
                    raise ValueError("trailing-slash URL must resolve to a directory")
                if target.is_dir():
                    target = (target / "index.html").resolve()
                    if not target.is_relative_to(root):
                        raise ValueError("directory index escapes the site root")
                if not target.is_file():
                    raise ValueError("local file or directory index not found")
                fragment = unquote(parsed.fragment, errors="strict").split(":~:text=", 1)[0]
                if fragment and target.suffix == ".html":
                    destination = documents.get(target)
                    if destination is None:
                        raise ValueError("HTML fragment destination was not parsed")
                    if fragment not in destination.ids:
                        raise ValueError(f"HTML fragment has no target: #{fragment}")
            except (OSError, UnicodeError, ValueError) as exc:
                errors.append(f"{label}: {reference!r}: {exc}")

    sitemap = root / "sitemap.xml"
    if sitemap.exists():
        try:
            ET.parse(sitemap)
        except (OSError, ET.ParseError) as exc:
            errors.append(f"sitemap.xml: invalid XML: {exc}")
    return len(documents), errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    count, errors = verify(args.root)
    if errors:
        print("Link/asset check FAILED:")
        for error in errors:
            print(f" - {error}")
        return 1
    print(f"OK: {count} HTML pages; committed local links/assets and HTML fragments resolve.")
    print("External HTTP availability and separately published /docs-site/ are not tested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
