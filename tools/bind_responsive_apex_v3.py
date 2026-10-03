#!/usr/bin/env python3
"""Bind the local responsive layer to every published company-front-door document.

All HTML receives the local stylesheet. Only the explicit interactive-document
allowlist receives the progressive JavaScript viewport controller. Static
pointer and error documents stay scriptless and keep their honest role.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "responsive-experience-v3.json"
STYLE = '<link rel="stylesheet" href="/assets/szl-responsive-apex-v3.css" data-szl-responsive-apex-v3="style" />'
SCRIPT = '<script src="/assets/szl-responsive-apex-v3.js" defer data-szl-responsive-apex-v3="script"></script>'
EXCLUDE_PARTS = {".git", ".github", "node_modules", "vendor", "archive", "archives", "fixtures"}


def pinned_script() -> str:
    data = (ROOT / "assets/szl-responsive-apex-v3.js").read_bytes().replace(b"\r\n", b"\n")
    if b"\r" in data:
        raise ValueError("responsive script requires canonical LF source bytes")
    integrity = "sha256-" + base64.b64encode(hashlib.sha256(data).digest()).decode("ascii")
    return SCRIPT.replace("></script>", f' integrity="{integrity}"></script>')


def script_span(text: str) -> tuple[int, int] | None:
    """Find the real managed element, never marker-like text inside script data."""
    class Bindings(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=False)
            self.rows = []
            # HTMLParser positions count LF, not every Unicode line separator.
            self.line_offsets = [0] + [match.end() for match in re.finditer("\n", text)]

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag != "script" or values.get("data-szl-responsive-apex-v3") != "script":
                return
            if len(attrs) != len(values) or values.get("src") != "/assets/szl-responsive-apex-v3.js" or "defer" not in values:
                raise ValueError("malformed responsive script binding")
            line, column = self.getpos()
            start = self.line_offsets[line - 1] + column
            end = start + len(self.get_starttag_text())
            if text[end:end + len("</script>")] != "</script>":
                raise ValueError("responsive external script must have an empty body")
            self.rows.append((start, end + len("</script>")))

    parser = Bindings()
    parser.feed(text)
    parser.close()
    if len(parser.rows) > 1:
        raise ValueError("duplicate responsive script binding")
    return parser.rows[0] if parser.rows else None


def documents() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.html")
        if path.is_file() and not (set(path.relative_to(ROOT).parts) & EXCLUDE_PARTS)
    )


def interactive_set() -> set[str]:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    return set(state.get("interactive_documents", []))


def is_bound(rel: str, text: str, interactive: set[str]) -> bool:
    if STYLE not in text:
        return False
    span = script_span(text)
    if rel not in interactive:
        return span is None
    return span is not None and text[span[0]:span[1]] == pinned_script()


def bind(path: Path, interactive: set[str]) -> str:
    rel = path.relative_to(ROOT).as_posix()
    text = path.read_text(encoding="utf-8")
    if "</head>" not in text.lower() or "</body>" not in text.lower():
        return "not-document"
    if text.count('data-szl-responsive-apex-v3="style"') > 1 or text.count('data-szl-responsive-apex-v3="script"') > 1:
        raise RuntimeError(f"duplicate responsive binding in {rel}")
    original = text
    if STYLE not in text:
        index = text.lower().rfind("</head>")
        text = text[:index] + "  " + STYLE + "\n" + text[index:]
    span = script_span(text)
    if rel in interactive:
        expected = pinned_script()
        if span is not None:
            text = text[:span[0]] + expected + text[span[1]:]
        else:
            index = text.lower().rfind("</body>")
            text = text[:index] + "  " + expected + "\n" + text[index:]
    elif span is not None:
        text = text[:span[0]] + text[span[1]:]
    if text != original:
        path.write_text(text, encoding="utf-8", newline="\n")
        return "bound"
    return "present"


def verify() -> None:
    interactive = interactive_set()
    docs = documents()
    known = {path.relative_to(ROOT).as_posix() for path in docs}
    missing_allowlist = interactive - known
    if missing_allowlist:
        raise RuntimeError("interactive documents are missing: " + ", ".join(sorted(missing_allowlist)))
    failures = []
    for path in docs:
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        if not is_bound(rel, text, interactive):
            failures.append(rel)
    if failures:
        raise RuntimeError("responsive company-front-door binding missing: " + ", ".join(failures))
    state = json.loads(STATE.read_text(encoding="utf-8"))
    if state.get("state") != "BOUND":
        raise RuntimeError("responsive company-front-door state is not BOUND")


def apply() -> None:
    interactive = interactive_set()
    rows = []
    for path in documents():
        rel = path.relative_to(ROOT).as_posix()
        rows.append({"path": rel, "result": bind(path, interactive), "mode": "INTERACTIVE" if rel in interactive else "STATIC"})
    state = json.loads(STATE.read_text(encoding="utf-8"))
    state["state"] = "BOUND"
    state["documents"] = rows
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verify()
    print(json.dumps({"examined": len(rows), "interactive": len(interactive), "rows": rows}, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        verify()
        print("responsive-company-front-door-v3: BOUND")
    else:
        apply()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
