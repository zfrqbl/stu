#!/usr/bin/env python3
"""Patch index.html to include Milestone 7 MCP frontend assets."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "static" / "index.html"

CSS_TAG = '<link rel="stylesheet" href="/static/styles-mcp.css">'
JS_TAG = '<script src="/static/mcp.js" defer></script>'

CSS_ANCHOR = '<link rel="stylesheet" href="/static/styles-security.css">'
JS_ANCHOR = '<script src="/static/security.js" defer></script>'


def main() -> int:
    if not INDEX.exists():
        print(f"Missing file: {INDEX}")
        return 1

    html = INDEX.read_text(encoding="utf-8")
    original = html

    if CSS_TAG not in html:
        if CSS_ANCHOR in html:
            html = html.replace(CSS_ANCHOR, f"{CSS_ANCHOR}\n  {CSS_TAG}", 1)
        else:
            html = html.replace("</head>", f"  {CSS_TAG}\n</head>", 1)

    if JS_TAG not in html:
        if JS_ANCHOR in html:
            html = html.replace(JS_ANCHOR, f"{JS_ANCHOR}\n  {JS_TAG}", 1)
        else:
            html = html.replace("</body>", f"  {JS_TAG}\n</body>", 1)

    if html == original:
        print("index.html already contains Milestone 7 frontend assets.")
        return 0

    INDEX.write_text(html, encoding="utf-8")
    print(f"Patched {INDEX}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
